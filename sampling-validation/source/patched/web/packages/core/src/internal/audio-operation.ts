/** Source-bound audio operation reporting; no retry, reload or prototype hooks. */
export type AudioPhase = "bind" | "release" | "core-play" | "core-pause" | "visibility" | "unmute";
export interface AudioStatus {
    readonly schema: 1;
    readonly contextId: number;
    readonly operationId: number;
    readonly intentId: number;
    readonly phase: AudioPhase;
    readonly operation: "none" | "resume" | "suspend";
    readonly status: "bound" | "released" | "pending" | "fulfilled" | "rejected";
    readonly state: string;
    readonly current: boolean;
    readonly retryEligible: boolean;
    readonly errorName?: string;
    readonly errorMessage?: string;
}
interface ContextRecord {
    id: number;
    operation: number;
    intent: number;
    active: boolean;
    everBound: boolean;
    listener: ((status: Readonly<AudioStatus>) => void) | null;
}
const records = new WeakMap<AudioContext, ContextRecord>();
let nextContextId = 0;
function increment(value: number): number {
    if (!Number.isSafeInteger(value) || value >= Number.MAX_SAFE_INTEGER) {
        throw new RangeError("Ruffle audio operation counter exhausted");
    }
    return value + 1;
}
function record(context: AudioContext): ContextRecord {
    let value = records.get(context);
    if (!value) {
        nextContextId = increment(nextContextId);
        value = { id: nextContextId, operation: 0, intent: 0, active: false,
            everBound: false, listener: null };
        records.set(context, value);
    }
    return value;
}
function emit(value: ContextRecord, status: AudioStatus): void {
    value.listener?.(Object.freeze(status));
}
function state(context: AudioContext): string {
    return String(context.state).slice(0, 32);
}
function describe(error: unknown): { errorName: string; errorMessage: string } {
    try {
        if (error instanceof Error || error instanceof DOMException) {
            return { errorName: String(error.name).slice(0, 128),
                errorMessage: String(error.message).slice(0, 512) };
        }
        return { errorName: "Unknown", errorMessage: String(error).slice(0, 512) };
    } catch {
        // Hostile diagnostic getters must not replace the original fatal error.
        return { errorName: "Unknown", errorMessage: "Unavailable" };
    }
}
function isDeviceStartFailure(error: unknown): boolean {
    try {
        return error instanceof DOMException && error.name === "InvalidStateError" &&
            error.message === "Failed to start the audio device";
    } catch {
        return false;
    }
}

/** Bind the real instance context before its first play/autoplay request. */
export function bindAudioContext(context: AudioContext,
    listener: (status: Readonly<AudioStatus>) => void): () => void {
    const value = record(context);
    if (value.everBound) {
        throw new Error("Ruffle AudioContext cannot be rebound");
    }
    value.everBound = true;
    value.active = true;
    value.listener = listener;
    emit(value, { schema: 1, contextId: value.id, operationId: value.operation,
        intentId: value.intent, phase: "bind", operation: "none", status: "bound",
        state: state(context), current: true, retryEligible: false });
    return () => {
        if (!value.active) { return; }
        value.active = false;
        value.intent = increment(value.intent);
        try {
            emit(value, { schema: 1, contextId: value.id, operationId: value.operation,
                intentId: value.intent, phase: "release", operation: "none", status: "released",
                state: state(context), current: false, retryEligible: false });
        } finally {
            // Pending settlements retain metadata, never a retired player subscriber.
            value.listener = null;
        }
    };
}

/**
 * Invoke exactly one native operation. Legacy callers intentionally ignore this
 * void result. Unknown rejection is propagated once, with its original object,
 * through an intentionally unhandled child Promise (the host's fatal route).
 */
export function requestAudioOperation(context: AudioContext,
    operation: "resume" | "suspend", phase: AudioPhase): void {
    const value = record(context);
    value.operation = increment(value.operation);
    value.intent = increment(value.intent);
    const operationId = value.operation, intentId = value.intent;
    const ownedAtRequest = value.active;
    const base = { schema: 1 as const, contextId: value.id, operationId,
        intentId, phase, operation };
    emit(value, { ...base, status: "pending", state: state(context),
        current: ownedAtRequest, retryEligible: false });
    let original: Promise<void>;
    try {
        original = context[operation]();
    } catch (error) {
        // A synchronous exception is not a native rejected resume Promise and
        // is never retry-eligible. Preserve its identity on one fatal path.
        void Promise.reject(error);
        return;
    }
    void original.then(() => {
        emit(value, { ...base, status: "fulfilled", state: state(context),
            current: ownedAtRequest && value.active && value.intent === intentId,
            retryEligible: false });
    }, (error: unknown) => {
        const current = ownedAtRequest && value.active && value.intent === intentId;
        const currentState = state(context);
        // Name alone is insufficient: WebKit also uses InvalidStateError for
        // uninitialized destinations and closed contexts. Never match strings
        // from unrelated errors or from a global unhandledrejection listener.
        const knownDeviceStart = ownedAtRequest && operation === "resume" &&
            isDeviceStartFailure(error);
        const retryEligible = knownDeviceStart && current && currentState !== "closed";
        emit(value, { ...base, status: "rejected", state: currentState, current,
            retryEligible, ...describe(error) });
        if (retryEligible) { return; }
        if (knownDeviceStart && !current) {
            // A retired/superseded owned request cannot replace a newer warning.
            console.debug("Ruffle stale audio-device start rejection", {
                contextId: value.id, operationId, intentId, phase });
            return;
        }
        throw error;
    });
}

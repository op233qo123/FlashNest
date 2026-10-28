import { strict as assert } from "assert";
import { configureBuilder } from "../src/internal/builder";
import { DEFAULT_CONFIG } from "../src/public/config/default";
import type { BaseLoadOptions } from "../src/public/config/index";

function apply(options: Record<string, unknown>) {
    const calls: [string, unknown][] = [];
    const builder = {
        setQuality: (value: string) => calls.push(["quality", value]),
        setRenderScale: (value: number) => calls.push(["renderScale", value]),
        setScale: (value: string) => calls.push(["scale", value]),
        setForceScale: (value: boolean) => calls.push(["forceScale", value]),
    };
    configureBuilder(builder as unknown as Parameters<typeof configureBuilder>[0],
        { quality: "high", ...options } as BaseLoadOptions);
    return calls;
}

describe("FlashNest onscreen rendering density", function () {
    it("does not call the new setter when the option is omitted", function () {
        assert.equal(DEFAULT_CONFIG.renderScale, null);
        assert.deepEqual(apply({}), [["quality", "high"]]);
        assert.deepEqual(apply({ renderScale: DEFAULT_CONFIG.renderScale }),
            [["quality", "high"]]);
    });
    it("passes exactly the four supported numeric tiers", function () {
        for (const value of [1, 0.75, 0.5, 0.25]) {
            assert.deepEqual(apply({ renderScale: value }),
                [["quality", "high"], ["renderScale", value]]);
        }
    });
    it("does not coerce or forward invalid values", function () {
        for (const value of [null, undefined, "0.5", true, false, 0, -1, 0.3,
            1.01, NaN, Infinity, -Infinity, {}, []]) {
            assert.deepEqual(apply({ renderScale: value }), [["quality", "high"]]);
        }
    });
    it("does not substitute quality or force a Stage scale mode", function () {
        assert.deepEqual(apply({ renderScale: 0.25, scale: "noScale", forceScale: false }),
            [["quality", "high"], ["renderScale", 0.25],
             ["scale", "noscale"], ["forceScale", false]]);
    });
});

import Foundation

struct ImportProgress: Sendable {
    var phase = "import.waiting"
    var file = ""
    var bytes: UInt64 = 0
}

/// One import operation owns this token. File-provider waiting and byte-copy
/// work can both be cancelled without blocking the main actor.
final class ImportControl: @unchecked Sendable {
    private let lock = NSLock()
    private var cancelled = false
    private var coordinator: NSFileCoordinator?
    private var progress = ImportProgress()
    private var lastReport = Date.distantPast
    private let report: @Sendable (ImportProgress) -> Void

    init(report: @escaping @Sendable (ImportProgress) -> Void = { _ in }) { self.report = report }

    func cancel() {
        lock.lock(); cancelled = true; let current = coordinator; lock.unlock()
        current?.cancel()
    }

    func coordinate(with coordinator: NSFileCoordinator?) {
        lock.lock(); self.coordinator = coordinator; let cancelNow = cancelled; lock.unlock()
        if cancelNow { coordinator?.cancel() }
    }

    func checkpoint(phase: String? = nil, file: String? = nil, addingBytes: UInt64 = 0) throws {
        lock.lock()
        if cancelled { lock.unlock(); throw CancellationError() }
        let changed = (phase != nil && phase != progress.phase) || (file != nil && file != progress.file)
        if let phase { progress.phase = phase }
        if let file { progress.file = file }
        let (bytes, overflow) = progress.bytes.addingReportingOverflow(addingBytes)
        guard !overflow else { lock.unlock(); throw PackageError.limit("progress bytes overflow") }
        progress.bytes = bytes
        let now = Date()
        let shouldReport = changed || now.timeIntervalSince(lastReport) >= 0.15
        let value = progress
        if shouldReport { lastReport = now }
        lock.unlock()
        if shouldReport { report(value) }
    }
}

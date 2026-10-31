import Foundation

/// Presentation identity is distinct from source approval and import operation.
/// Neither a dismissed alert nor a late button may approve a newer request.
struct ImportSizeConfirmation: Identifiable {
    let id = UUID()
    let operation: UUID
    let warning: ImportSizeWarning

    var message: String {
        L10n.format("Import size: %@ total; largest file: %@. Warning thresholds: %@ per file or %@ total.",
                    Self.bytes(warning.totalBytes), Self.bytes(warning.largestFileBytes),
                    Self.bytes(warning.fileThreshold), Self.bytes(warning.totalThreshold)) + "\n\n" +
        L10n.text("Large imports need additional free storage and may take a long time. Importing or running this game may fail because of available storage or memory. The original files are not changed. Continue importing?")
    }

    private static func bytes(_ value: Int64) -> String {
        // Exact bytes avoid rounding a boundary warning down to its threshold.
        L10n.format("%lld bytes", value)
    }
}

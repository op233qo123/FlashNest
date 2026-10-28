import Foundation

/// ZIPFoundation's Sequence stops rather than throwing if a later header cannot be read.
/// Validate bounded central-directory framing first, then require exactly this many yields.
/// ZIP64 and split archives are intentionally unsupported by this first-release importer.
struct ZIPIntegrity {
    static func expectedEntryCount(at url: URL, maximumEntries: Int) throws -> Int {
        let input = try FileHandle(forReadingFrom: url)
        defer { try? input.close() }
        let size = try input.seekToEnd()
        guard size >= 22 else { throw corrupt() }
        let tailSize = Int(min(size, 65_557)) // EOCD plus maximum UInt16 comment.
        let tail = try read(input, offset: size - UInt64(tailSize), count: tailSize)
        var endIndex: Int?
        for index in stride(from: tail.count - 22, through: 0, by: -1) {
            if u32(tail, index) == 0x06054b50,
               index + 22 + Int(u16(tail, index + 20)) == tail.count {
                endIndex = index
                break
            }
        }
        guard let endIndex else { throw corrupt() }
        let eocdOffset = size - UInt64(tailSize) + UInt64(endIndex)
        let disk = u16(tail, endIndex + 4)
        let directoryDisk = u16(tail, endIndex + 6)
        let diskCount = u16(tail, endIndex + 8)
        let count = u16(tail, endIndex + 10)
        let directorySize = u32(tail, endIndex + 12)
        let directoryOffset = u32(tail, endIndex + 16)
        guard disk == 0, directoryDisk == 0, diskCount == count,
              count != UInt16.max, directorySize != UInt32.max, directoryOffset != UInt32.max else {
            throw PackageError.unsupported("Split or ZIP64 archive. Repack as a standard ZIP under the import limits.")
        }
        guard Int(count) <= maximumEntries else { throw PackageError.limit("file count") }
        let start = UInt64(directoryOffset)
        let end = start + UInt64(directorySize)
        guard end == eocdOffset else { throw corrupt() }
        var position = start
        for _ in 0..<Int(count) {
            guard position <= end, end - position >= 46 else { throw corrupt() }
            let header = try read(input, offset: position, count: 46)
            guard u32(header, 0) == 0x02014b50 else { throw corrupt() }
            let compressed = u32(header, 20), expanded = u32(header, 24)
            let filenameLength = u16(header, 28)
            let extraLength = u16(header, 30), commentLength = u16(header, 32)
            let entryDisk = u16(header, 34), localOffset = u32(header, 42)
            guard entryDisk == 0, compressed != UInt32.max, expanded != UInt32.max,
                  localOffset != UInt32.max else { throw PackageError.unsupported("Split or ZIP64 entry") }
            guard u16(header, 8) & 1 == 0 else { throw PackageError.unsupported("Encrypted ZIP entry") }
            let length = UInt64(46) + UInt64(filenameLength) + UInt64(extraLength) + UInt64(commentLength)
            guard filenameLength > 0, length <= end - position,
                  UInt64(localOffset) < start, start - UInt64(localOffset) >= 30 else { throw corrupt() }
            position += length
        }
        guard position == end else { throw corrupt() }
        return Int(count)
    }

    private static func read(_ input: FileHandle, offset: UInt64, count: Int) throws -> Data {
        try input.seek(toOffset: offset)
        let bytes = try input.read(upToCount: count) ?? Data()
        guard bytes.count == count else { throw corrupt() }
        return bytes
    }
    private static func u16(_ data: Data, _ offset: Int) -> UInt16 {
        UInt16(data[offset]) | UInt16(data[offset + 1]) << 8
    }
    private static func u32(_ data: Data, _ offset: Int) -> UInt32 {
        UInt32(data[offset]) | UInt32(data[offset + 1]) << 8 |
            UInt32(data[offset + 2]) << 16 | UInt32(data[offset + 3]) << 24
    }
    private static func corrupt() -> PackageError { .corrupt("Incomplete or inconsistent ZIP directory") }
}

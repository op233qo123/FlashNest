import Foundation

/// Deliberately small HTTP/1.1 parser: one bodyless request per connection.
struct LocalHTTPRequest {
    let method: String
    let target: String
    let headers: [String: String]
    static let maximumHeaderBytes = 16_384

    static func parse(_ data: Data, expectedHost: String) throws -> LocalHTTPRequest {
        guard data.count <= maximumHeaderBytes,
              let text = String(data: data, encoding: .utf8),
              text.hasSuffix("\r\n\r\n") else { throw LocalHTTPError.badRequest }
        let lines = text.components(separatedBy: "\r\n")
        let words = lines[0].split(separator: " ", omittingEmptySubsequences: false)
        guard words.count == 3, words[2] == "HTTP/1.1",
              words[1].hasPrefix("/"), !words[1].hasPrefix("//") else { throw LocalHTTPError.badRequest }
        let method = String(words[0])
        guard method == "GET" || method == "HEAD" else { throw LocalHTTPError.methodNotAllowed }
        var headers: [String: String] = [:]
        for line in lines.dropFirst() where !line.isEmpty {
            guard !line.hasPrefix(" "), !line.hasPrefix("\t"), let colon = line.firstIndex(of: ":") else { throw LocalHTTPError.badRequest }
            let key = String(line[..<colon]).lowercased()
            guard !key.isEmpty, key.utf8.allSatisfy({ ($0 >= 97 && $0 <= 122) || ($0 >= 48 && $0 <= 57) || $0 == 45 }), headers[key] == nil else { throw LocalHTTPError.badRequest }
            let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
            guard !value.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) else { throw LocalHTTPError.badRequest }
            headers[key] = value
        }
        guard headers["host"] == expectedHost else { throw LocalHTTPError.forbidden }
        guard headers["transfer-encoding"] == nil,
              headers["content-length"] == nil || headers["content-length"] == "0" else { throw LocalHTTPError.badRequest }
        return LocalHTTPRequest(method: method, target: String(words[1]), headers: headers)
    }
}

enum LocalHTTPError: Error {
    case badRequest, forbidden, notFound, methodNotAllowed, rangeNotSatisfiable, stopped, alreadyStarted
    var status: Int {
        switch self {
        case .badRequest: return 400
        case .forbidden: return 403
        case .notFound: return 404
        case .methodNotAllowed: return 405
        case .rangeNotSatisfiable: return 416
        case .stopped, .alreadyStarted: return 503
        }
    }
}

struct LocalHTTPPath {
    static func components(_ target: String) throws -> [String] {
        let raw = String(target.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)[0])
        guard let decoded = raw.removingPercentEncoding, decoded.hasPrefix("/"),
              !decoded.contains("\\"), !decoded.contains("\0"), !decoded.contains("#"),
              !decoded.unicodeScalars.contains(where: { $0.value < 32 || $0.value == 127 }) else { throw LocalHTTPError.forbidden }
        let parts = decoded.split(separator: "/", omittingEmptySubsequences: false).dropFirst().map(String.init)
        guard !parts.isEmpty, parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else { throw LocalHTTPError.forbidden }
        return parts
    }

    /// Also checks each component: canonical-prefix checks alone permit internal symlinks.
    static func file(root: URL, components: [String]) throws -> URL {
        let canonicalRoot = root.standardizedFileURL.resolvingSymlinksInPath()
        var candidate = canonicalRoot
        for part in components {
            guard part != ".", part != "..", !part.contains("/"), !part.contains("\\"), !part.isEmpty else { throw LocalHTTPError.forbidden }
            candidate.appendPathComponent(part)
            let values = try candidate.resourceValues(forKeys: [.isSymbolicLinkKey])
            guard values.isSymbolicLink != true else { throw LocalHTTPError.forbidden }
        }
        let resolved = candidate.standardizedFileURL.resolvingSymlinksInPath()
        guard resolved.path.hasPrefix(canonicalRoot.path + "/"),
              try resolved.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else { throw LocalHTTPError.notFound }
        return resolved
    }

    static func byteRange(_ header: String?, size: UInt64) throws -> Range<UInt64> {
        guard let header = header else { return 0..<size }
        guard header.hasPrefix("bytes="), !header.contains(","), size > 0 else { throw LocalHTTPError.rangeNotSatisfiable }
        let values = header.dropFirst(6).split(separator: "-", omittingEmptySubsequences: false)
        guard values.count == 2 else { throw LocalHTTPError.rangeNotSatisfiable }
        if values[0].isEmpty {
            guard let suffix = UInt64(values[1]), suffix > 0 else { throw LocalHTTPError.rangeNotSatisfiable }
            return (size - min(suffix, size))..<size
        }
        guard let start = UInt64(values[0]), start < size else { throw LocalHTTPError.rangeNotSatisfiable }
        if values[1].isEmpty { return start..<size }
        guard let end = UInt64(values[1]), end >= start else { throw LocalHTTPError.rangeNotSatisfiable }
        return start..<(min(end, size - 1) + 1)
    }
}

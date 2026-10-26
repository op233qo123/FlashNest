import Foundation
import Network

/// Owns a single loopback listener. All mutable state is confined to `queue`.
/// Keep port and capability stable across launches to preserve Flash SharedObject identity.
final class LoopbackServer {
    let port: UInt16
    let capability: String
    let webRoot: URL
    var onDiagnostic: ((String) -> Void)?
    private let queue = DispatchQueue(label: "FlashNest.loopback")
    private var listener: NWListener?
    private var connections: [ObjectIdentifier: NWConnection] = [:]
    private var activePackage: (id: UUID, root: URL)?
    private var startup: CheckedContinuation<Void, Error>?
    private var ready = false
    // Retain cancelled endpoints until Network.framework confirms teardown.
    // A restart must not rebind the stable port while the old listener owns it.
    private var stopping = false
    private var restart: CheckedContinuation<Void, Error>?

    init(port: UInt16, capability: String, webRoot: URL) {
        precondition(port > 1024)
        precondition(capability.count >= 32 && capability.utf8.allSatisfy { ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 122) || $0 == 45 })
        self.port = port
        self.capability = capability
        self.webRoot = webRoot
    }

    var origin: URL { URL(string: "http://127.0.0.1:\(port)")! }
    var shellURL: URL { origin.appendingPathComponent(capability).appendingPathComponent("web/index.html") }
    func gameURL(packageID: UUID, relativePath: String) -> URL {
        relativePath.split(separator: "/").reduce(origin.appendingPathComponent(capability).appendingPathComponent("games").appendingPathComponent(packageID.uuidString)) { $0.appendingPathComponent(String($1)) }
    }

    func activate(packageID: UUID, root: URL) {
        queue.async { self.activePackage = (packageID, root) }
    }

    func start() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async { self.beginStart(continuation) }
        }
    }

    private func beginStart(_ continuation: CheckedContinuation<Void, Error>) {
        if stopping {
            guard restart == nil else { continuation.resume(throwing: LocalHTTPError.alreadyStarted); return }
            restart = continuation
            return
        }
        guard self.listener == nil else {
            if self.ready { continuation.resume() }
            else { continuation.resume(throwing: LocalHTTPError.alreadyStarted) }
            return
        }
        do {
            let parameters = NWParameters.tcp
            let endpointPort = NWEndpoint.Port(rawValue: self.port)!
            parameters.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: endpointPort)
            parameters.requiredInterfaceType = .loopback
            parameters.allowLocalEndpointReuse = true
            // requiredLocalEndpoint already specifies both bind address
            // and stable port. Passing `on:` as well attempts a second
            // port override and Network.framework rejects it with EINVAL.
            let listener = try NWListener(using: parameters)
            self.listener = listener
            self.startup = continuation
            listener.stateUpdateHandler = { [weak self, weak listener] state in
                guard let self = self, self.listener === listener else { return }
                switch state {
                case .ready:
                    guard !self.stopping else { return }
                    self.ready = true
                    self.startup?.resume()
                    self.startup = nil
                case .failed(let error):
                    self.failStart(error)
                    self.shutdown()
                case .cancelled:
                    self.failStart(LocalHTTPError.stopped)
                    self.listener = nil
                    self.finishStopIfDrained()
                default: break
                }
            }
            listener.newConnectionHandler = { [weak self] connection in self?.accept(connection) }
            listener.start(queue: self.queue)
            self.queue.asyncAfter(deadline: .now() + 10) { [weak self, weak listener] in
                guard let self = self, self.listener === listener, !self.ready, !self.stopping else { return }
                self.failStart(LocalHTTPError.stopped)
                self.shutdown()
            }
        } catch { continuation.resume(throwing: error) }
    }

    func stop() { queue.async { self.shutdown() } }
    private func failStart(_ error: Error) {
        startup?.resume(throwing: error)
        startup = nil
    }
    private func shutdown() {
        failStart(LocalHTTPError.stopped)
        restart?.resume(throwing: LocalHTTPError.stopped)
        restart = nil
        stopping = true
        ready = false
        activePackage = nil
        listener?.cancel()
        connections.values.forEach { $0.cancel() }
        finishStopIfDrained()
    }

    private func finishStopIfDrained() {
        guard stopping, listener == nil, connections.isEmpty else { return }
        stopping = false
        if let pending = restart {
            restart = nil
            // Let the final cancellation callback unwind before rebinding.
            queue.async { self.beginStart(pending) }
        }
    }

    private func accept(_ connection: NWConnection) {
        guard !stopping, connections.count < 24 else { connection.cancel(); return }
        connections[ObjectIdentifier(connection)] = connection
        connection.stateUpdateHandler = { [weak self, weak connection] state in
            guard let self = self, let connection = connection else { return }
            switch state {
            case .cancelled, .failed:
                self.connections.removeValue(forKey: ObjectIdentifier(connection))
                self.finishStopIfDrained()
            default: break
            }
        }
        connection.start(queue: queue)
        receive(connection, accumulated: Data())
        queue.asyncAfter(deadline: .now() + 60) { [weak self, weak connection] in
            guard let self, let connection,
                  self.connections[ObjectIdentifier(connection)] != nil else { return }
            self.onDiagnostic?("Local HTTP connection timed out after 60 seconds")
            connection.cancel()
        }
    }

    private func receive(_ connection: NWConnection, accumulated: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] chunk, _, complete, error in
            guard let self = self else { connection.cancel(); return }
            var data = accumulated
            if let chunk = chunk { data.append(chunk) }
            guard data.count <= LocalHTTPRequest.maximumHeaderBytes else { self.failure(connection, status: 431); return }
            if let end = data.range(of: Data("\r\n\r\n".utf8)) {
                // No pipelining/request body is supported.
                guard end.upperBound == data.endIndex else { self.failure(connection, status: 400); return }
                self.respond(connection, requestBytes: data)
            } else if complete || error != nil { connection.cancel() }
            else { self.receive(connection, accumulated: data) }
        }
    }

    private func respond(_ connection: NWConnection, requestBytes: Data) {
        var request: LocalHTTPRequest?
        do {
            let parsed = try LocalHTTPRequest.parse(requestBytes, expectedHost: "127.0.0.1:\(port)")
            request = parsed
            let parts = try LocalHTTPPath.components(parsed.target)
            guard parts.first == capability, parts.count >= 3 else { throw LocalHTTPError.forbidden }
            let file: URL
            let isWeb = parts[1] == "web"
            if isWeb {
                file = try LocalHTTPPath.file(root: webRoot, components: Array(parts.dropFirst(2)))
            } else {
                guard parts[1] == "games", parts.count >= 4,
                      let active = activePackage, parts[2] == active.id.uuidString else { throw LocalHTTPError.forbidden }
                file = try LocalHTTPPath.file(root: active.root, components: Array(parts.dropFirst(3)))
                guard !["html", "htm", "js", "mjs", "xhtml", "wasm"].contains(file.pathExtension.lowercased()) else { throw LocalHTTPError.forbidden }
            }
            let values = try file.resourceValues(forKeys: [.fileSizeKey])
            guard let count = values.fileSize, count >= 0, count <= 536_870_912 else { throw LocalHTTPError.forbidden }
            let size = UInt64(count)
            let range: Range<UInt64>
            do { range = try LocalHTTPPath.byteRange(parsed.headers["range"], size: size) }
            catch { failure(connection, status: 416, head: parsed.method == "HEAD", extra: "Content-Range: bytes */\(size)\r\n"); return }
            let status = parsed.headers["range"] == nil ? 200 : 206
            if !isWeb, file.pathExtension.lowercased() == "swf" {
                // Numeric transport evidence only: never include capability URLs.
                onDiagnostic?("SWF HTTP response: status=\(status), bytes=\(range.count), method=\(parsed.method)")
            }
            var extra = "Content-Type: \(Self.mime(file.pathExtension))\r\nAccept-Ranges: bytes\r\n"
            if status == 206 { extra += "Content-Range: bytes \(range.lowerBound)-\(range.upperBound - 1)/\(size)\r\n" }
            // Imported content is data, never an executable document.
            extra += "Content-Security-Policy: \(isWeb ? Self.shellCSP : "sandbox; default-src 'none'")\r\n"
            let header = headers(status: status, length: range.count, extra: extra)
            if parsed.method == "HEAD" || range.isEmpty {
                connection.send(content: header, completion: .contentProcessed { _ in connection.cancel() })
                return
            }
            let handle = try FileHandle(forReadingFrom: file)
            try handle.seek(toOffset: range.lowerBound)
            connection.send(content: header, completion: .contentProcessed { [weak self] error in
                guard error == nil, let self = self else { try? handle.close(); connection.cancel(); return }
                self.stream(handle, remaining: UInt64(range.count), to: connection)
            })
        } catch {
            let status = (error as? LocalHTTPError)?.status ?? 404
            if status == 404, let request = request {
                // Do not expose the capability token in diagnostics.
                let sanitized = request.target.replacingOccurrences(of: "/\(capability)/", with: "/")
                onDiagnostic?("Missing local asset: \(String(sanitized.prefix(300)))")
            }
            failure(connection, status: status, head: request?.method == "HEAD")
        }
    }

    private func stream(_ handle: FileHandle, remaining: UInt64, to connection: NWConnection) {
        do {
            guard remaining > 0 else { try? handle.close(); connection.cancel(); return }
            let data = try handle.read(upToCount: Int(min(remaining, 262_144))) ?? Data()
            guard !data.isEmpty else {
                onDiagnostic?("Local HTTP stream ended early: remaining=\(remaining)")
                try? handle.close(); connection.cancel(); return
            }
            connection.send(content: data, completion: .contentProcessed { [weak self] error in
                guard error == nil, let self = self else {
                    self?.onDiagnostic?("Local HTTP stream send failed: remaining=\(remaining)")
                    try? handle.close(); connection.cancel(); return
                }
                self.stream(handle, remaining: remaining - UInt64(data.count), to: connection)
            })
        } catch {
            onDiagnostic?("Local HTTP stream read failed: remaining=\(remaining)")
            try? handle.close(); connection.cancel()
        }
    }

    private func failure(_ connection: NWConnection, status: Int, head: Bool = false, extra: String = "") {
        onDiagnostic?("Local HTTP failure: status=\(status)")
        let body = Data("Local resource request failed (\(status)).".utf8)
        var data = headers(status: status, length: body.count, extra: extra + "Content-Type: text/plain; charset=utf-8\r\n")
        if !head { data.append(body) }
        connection.send(content: data, completion: .contentProcessed { _ in connection.cancel() })
    }
    private func headers(status: Int, length: Int, extra: String) -> Data {
        Data("HTTP/1.1 \(status) \(status == 200 ? "OK" : "Response")\r\nContent-Length: \(length)\r\nConnection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n\(extra)\r\n".utf8)
    }
    static let shellCSP = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; worker-src 'self' blob:; font-src 'self' data:; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
    static func mime(_ ext: String) -> String {
        switch ext.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "js", "mjs": return "text/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "wasm": return "application/wasm"
        case "swf": return "application/x-shockwave-flash"
        case "json": return "application/json"
        case "xml": return "application/xml"
        case "txt": return "text/plain; charset=utf-8"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "svg": return "image/svg+xml"
        case "mp3": return "audio/mpeg"
        case "wav": return "audio/wav"
        case "ogg": return "audio/ogg"
        case "mp4": return "video/mp4"
        default: return "application/octet-stream"
        }
    }
}

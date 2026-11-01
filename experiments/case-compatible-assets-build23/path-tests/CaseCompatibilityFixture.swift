import Foundation
#if canImport(FlashNest)
@testable import FlashNest
#endif

// Standalone native regression harness: compiled alongside the exact candidate
// HTTPProtocol.swift. No private games, runtime rewriting, or network needed.
func runCaseCompatibilityFixture(root: URL) throws -> [String: Any] {
let fm = FileManager.default
var passed: [String] = []
func check(_ name: String, _ body: () throws -> Void) rethrows {
    try body(); passed.append(name)
}
func require(_ value: @autoclosure () throws -> Bool, _ message: String) throws {
    if try !value() { throw NSError(domain: "CaseCompatibilityTest", code: 1,
                                userInfo: [NSLocalizedDescriptionKey: message]) }
}
func write(_ path: String, _ value: String = "fixture") throws {
    let url = root.appendingPathComponent(path)
    try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try Data(value.utf8).write(to: url)
}
func load(_ path: [String], fallback: Bool = true) throws -> String {
    let url = try LocalHTTPPath.file(root: root, components: path, allowUniqueCaseFallback: fallback)
    return try String(contentsOf: url, encoding: .utf8)
}
func rejected(_ body: () throws -> Void) throws {
    var failed = false
    do { try body() } catch { failed = true }
    try require(failed, "Expected rejection")
}
func forbidden(_ body: () throws -> Void) throws {
    do { try body() } catch let error as LocalHTTPError {
        try require(error.status == 403, "Expected forbidden, not another status"); return
    }
    throw NSError(domain: "CaseCompatibilityTest", code: 2)
}

    try fm.createDirectory(at: root, withIntermediateDirectories: true)
    try write("CaseProbe", "upper"); try write("caseprobe", "lower")
    try require(try String(contentsOf: root.appendingPathComponent("CaseProbe"), encoding: .utf8) == "upper",
                "Fixture filesystem is not case sensitive")
    try require(try String(contentsOf: root.appendingPathComponent("caseprobe"), encoding: .utf8) == "lower",
                "Fixture filesystem is not case sensitive")
    try write("Data/List_Op.xml", "upper exact")
    try write("Data/List_op.xml", "lower exact")
    try check("exact_wins_over_case_collision") {
        try require(try load(["Data", "List_Op.xml"]) == "upper exact", "Exact did not win")
    }
    try check("ambiguous_case_fallback_rejected") {
        try rejected { _ = try load(["Data", "LIST_OP.XML"]) }
    }
    try write("Content/UI/Chapter_One.xml", "unique")
    try check("unique_multicomponent_fallback") {
        try require(try load(["content", "ui", "chapter_one.XML"]) == "unique", "Fallback failed")
    }
    try check("strict_default_has_no_fallback") {
        try rejected { _ = try LocalHTTPPath.file(root: root, components: ["content", "ui", "chapter_one.XML"]) }
    }
    try check("missing_rejected") { try rejected { _ = try load(["Content", "absent.xml"]) } }
    try check("no_cross_directory_basename_guess") { try rejected { _ = try load(["Chapter_One.xml"]) } }
    try write("ExactParent/other.xml"); try write("exactparent/target.xml")
    try check("exact_parent_is_not_backtracked") {
        try rejected { _ = try load(["ExactParent", "target.xml"]) }
    }
    try check("ambiguous_directory_rejected") { try rejected { _ = try load(["EXACTPARENT", "target.xml"]) } }
    try write("Unicode/Café.xml", "unicode")
    try check("unicode_normalization_matches_import_registry") {
        try require(try load(["unicode", "CAFE\u{301}.XML"]) == "unicode", "Unicode match failed")
    }
    try check("diacritic_not_folded") { try rejected { _ = try load(["Unicode", "Cafe.xml"]) } }
    try write("Encoded/percent%2Fname.xml", "literal")
    try check("url_decode_once_not_twice") {
        let parts = try LocalHTTPPath.components("/Encoded/percent%252Fname.xml?ignored=1")
        try require(try load(parts) == "literal", "Double decoding or query handling changed")
    }
    try check("encoded_unicode_case_fallback") {
        let parts = try LocalHTTPPath.components("/unicode/CAF%C3%89.XML")
        try require(try load(parts) == "unicode", "Encoded Unicode mismatch")
    }
    try check("traversal_and_invalid_url_rejected") {
        for target in ["/../secret", "/%2e%2e/secret", "/Content/%2E/secret", "/Content/%5csecret", "/Content/%00secret", "/Content/%23secret", "/Content//secret", "/Content/%ZZ"] {
            try forbidden { _ = try LocalHTTPPath.components(target) }
        }
        for part in ["..", ".", "", "a/b", "a\\b"] {
            try forbidden { _ = try load([part]) }
        }
    }
    try check("root_or_directory_not_a_regular_file") {
        try rejected { _ = try load([]) }
        try rejected { _ = try load(["Content"]) }
    }
    let outside = root.deletingLastPathComponent().appendingPathComponent("outside-" + UUID().uuidString)
    try fm.createDirectory(at: outside, withIntermediateDirectories: true)
    defer { try? fm.removeItem(at: outside) }
    try Data("outside".utf8).write(to: outside.appendingPathComponent("secret.xml"))
    try fm.createSymbolicLink(at: root.appendingPathComponent("Link"), withDestinationURL: outside)
    try fm.createSymbolicLink(at: root.appendingPathComponent("InsideLink"), withDestinationURL: root.appendingPathComponent("Content"))
    try fm.createSymbolicLink(at: root.appendingPathComponent("FileLink.xml"), withDestinationURL: outside.appendingPathComponent("secret.xml"))
    try check("symlink_exact_and_case_fallback_forbidden") {
        for parts in [["Link", "secret.xml"], ["link", "SECRET.XML"], ["InsideLink", "UI", "Chapter_One.xml"], ["insidelink", "ui", "chapter_one.xml"], ["FileLink.xml"], ["filelink.XML"]] {
            try forbidden { _ = try load(parts) }
        }
    }
    try fm.createSymbolicLink(at: root.appendingPathComponent("Dangling.xml"), withDestinationURL: outside.appendingPathComponent("absent.xml"))
    try check("dangling_symlink_exact_and_fallback_rejected") {
        for parts in [["Dangling.xml"], ["dangling.XML"]] {
            // Foundation may classify dangling links as missing before returning
            // metadata; either missing or forbidden must fail closed.
            try rejected { _ = try load(parts) }
        }
    }
    try check("regular_file_cannot_be_intermediate_directory") {
        try rejected { _ = try load(["Content", "UI", "Chapter_One.xml", "child.xml"]) }
        try rejected { _ = try load(["content", "ui", "chapter_one.XML", "child.xml"]) }
    }
    try check("nested_entry_base_and_sibling_content") {
        try write("Nested/Main.swf"); try write("Nested/Content/Scene_Op.xml", "nested sibling")
        // Mirrors shell.js's base: new URL('./', entryURL), then relative asset.
        let entry = URL(string: "http://127.0.0.1:1234/cap/games/id/Nested/Main.swf")!
        let base = URL(string: "./", relativeTo: entry)!.absoluteURL
        let asset = URL(string: "content/scene_op.xml", relativeTo: base)!.absoluteURL
        let parts = try LocalHTTPPath.components(asset.path)
        try require(try load(Array(parts.dropFirst(3))) == "nested sibling", "Nested entry base changed")
    }
    let result: [String: Any] = ["schema": "flashnest-casecompat-native-v1", "caseSensitiveFilesystemVerified": true,
        "passed": true, "count": passed.count, "tests": passed,
        "scope": "Native Foundation resolver on case-sensitive fixture filesystem; not iOS device/network certification"]
    return result
}

import Foundation

do {
    let result = try runCaseCompatibilityFixture(root: URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true))
    let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch {
    fputs("Case compatibility test failure: \(error)\n", stderr)
    exit(1)
}

import SwiftUI

struct LibrarySettingsView: View {
    @Binding var language: String
    @ObservedObject var nativeImporter: NativeImportController
    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        NavigationStack {
            Form {
                Section(L10n.text("Language")) {
                    languageControl
                }
                Section(L10n.text("Help and diagnostics")) {
                    Text(L10n.text("Open the game folder, then tap Open. Keep the main SWF and subfolders together."))
                        .font(.footnote).foregroundStyle(.secondary)
                    NavigationLink { LibraryImportDiagnosticsView(nativeImporter: nativeImporter) } label: {
                        Label(L10n.text("Import diagnostics"), systemImage: "doc.text.magnifyingglass")
                    }.accessibilityIdentifier("settings-import-diagnostics")
                    NavigationLink { LibraryAcknowledgmentsView() } label: {
                        Label(L10n.text("Runtime and acknowledgments"), systemImage: "info.circle")
                    }.accessibilityIdentifier("settings-acknowledgments")
                }
                Section {
                    Text(L10n.text("Offline by default. Ruffle compatibility varies by game. Saves are kept separately from imported game copies."))
                        .font(.footnote).foregroundStyle(.secondary)
                    Text("FlashNest \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?") (\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"))")
                        .font(.caption).foregroundStyle(.secondary).accessibilityIdentifier("app-version")
                }
            }
            .navigationTitle(L10n.text("Settings"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) {
                Button(L10n.text("Done")) { dismiss() }.accessibilityIdentifier("settings-done")
            } }
        }
        .environment(\.locale, Locale(identifier: L10n.languageCode))
    }

    @ViewBuilder private var languageControl: some View {
        if typeSize.isAccessibilitySize {
            languageLabel
            NavigationLink {
                LibraryLanguageSelectionView(language: $language)
            } label: {
                Text(languageTitle(language))
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            }.accessibilityIdentifier("settings-language")
        } else {
            Picker(selection: $language) {
                Text(L10n.text("System default")).tag("system")
                Text("English").tag("en")
                Text("简体中文").tag("zh-Hans")
            } label: { languageLabel }
                .accessibilityIdentifier("settings-language")
        }
    }

    private var languageLabel: some View {
        Text(L10n.text("Language")).accessibilityIdentifier("settings-language-label")
    }
}

private struct LibraryLanguageSelectionView: View {
    @Binding var language: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        List {
            ForEach(["system", "en", "zh-Hans"], id: \.self) { code in
                Button {
                    language = code
                    dismiss()
                } label: {
                    HStack(spacing: 12) {
                        Text(languageTitle(code))
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 8)
                        if language == code {
                            Image(systemName: "checkmark").accessibilityHidden(true)
                        }
                    }.frame(minHeight: 44).padding(.vertical, 4)
                }
                .accessibilityIdentifier("settings-language-option-" + code)
                .accessibilityAddTraits(language == code ? .isSelected : [])
            }
        }
        .navigationTitle(L10n.text("Language"))
        .navigationBarTitleDisplayMode(.inline)
    }
}

private func languageTitle(_ code: String) -> String {
    switch code {
    case "en": return "English"
    case "zh-Hans": return "简体中文"
    default: return L10n.text("System default")
    }
}

struct LibraryImportDiagnosticsView: View {
    @ObservedObject var nativeImporter: NativeImportController
    var body: some View {
        ScrollView {
            Text(nativeImporter.diagnosticText).font(.system(.caption, design: .monospaced))
                .textSelection(.enabled).padding().frame(maxWidth: .infinity, alignment: .leading)
        }
        .navigationTitle(L10n.text("Import diagnostics"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ShareLink(L10n.text("Share diagnostics"), item: nativeImporter.diagnosticText) }
    }
}

private struct LibraryAcknowledgmentsView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("FlashNest").font(.title.bold())
                Text(L10n.text("Ruffle — Flash Player emulator, MIT OR Apache-2.0. ZIPFoundation 0.9.20 — MIT. Runtime version and license details are bundled below."))
                Text(notices).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
            }.padding()
        }.navigationTitle(L10n.text("Acknowledgments"))
    }
    private var notices: String {
        guard let root = Bundle.main.url(forResource: "Web", withExtension: nil) else {
            return L10n.text("Runtime resources missing — build is incomplete.")
        }
        guard let manifestData = try? Data(contentsOf: root.appendingPathComponent("licenses.manifest.json")),
              let manifest = try? JSONDecoder().decode([String: String].self, from: manifestData) else {
            return L10n.text("Runtime resources missing — build is incomplete.")
        }
        let files = ["runtime/package.json", "THIRD_PARTY_NOTICES.md"] + manifest.keys.sorted()
        return files.map { file in
            let text = (try? String(contentsOf: root.appendingPathComponent(file), encoding: .utf8))
                ?? L10n.text("Runtime resources missing — build is incomplete.")
            return "— \(file) —\n\(text)"
        }.joined(separator: "\n\n")
    }
}

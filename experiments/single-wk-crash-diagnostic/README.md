# One synthetic WK crash diagnostic — no product changes or IPA

Run only the existing ZIP runtime selector in a fresh iPhone SE3 iOS18.2 simulator,
with the unchanged 120-second method allowance and exact original 207 App source
files / 12 runtime assets. No overlay, UI test, extra fixture, engine build or full
16-method run. The workflow limit is 20 minutes including setup; a setup timeout
is failure, not evidence the underlying test passed.

PID evidence is extracted only from the exact WebKit/GPU crash-reason log line.
No PID is guessed from other lines. At test completion wait at most 15 seconds
for matching DiagnosticReports. The collector checks the precise process kind,
PID and timezone-qualified capture timestamp in the test/report window. It reads
at most three candidate IPS files, 2 MiB each / 6 MiB total. Missing, unsupported,
or omitted evidence is explicit and nonzero, not a diagnosis of no crash.

Raw test logs, xcresult, summaries and IPS files stay runner-local. Uploaded
artifacts contain only the sanitized JSON receipt and allowlisted crash structure:
exception type/signal/numeric codes, termination namespace/numeric codes, faulting
thread frames with safe symbols, image basename/UUID and offsets. No raw report,
thread names/registers, machine/user identifiers, URLs, source paths, contents or
simulator container is uploaded. Symbols with path/URL/quoted-data, dotted-hostname or UUID markers are
omitted rather than copied; unknown exception/termination enums are omitted.
Without an exact correlated crash PID, no IPS content is read. Frame count is capped at128; omissions are recorded.

The original formal release gate is untouched and still not satisfied by this
experiment. Even a passing isolated test only means that this run did not reproduce
the failure; it does not exclude sequence-dependent failures or memory pressure.
No release/IPA is created. Dispatch defaults disabled pending exact-scope review.

IPS structure reference: Apple, Interpreting the JSON format of a crash report,
https://developer.apple.com/documentation/xcode/interpreting-the-json-format-of-a-crash-report

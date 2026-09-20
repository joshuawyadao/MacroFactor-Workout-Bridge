# GUI regression validation — September 20, 2026

The recent regression scan reviewed main at `7d8a91c64e9210aeae58899f5534ea75fc952263`, but did not collect a terminal result for the complete GUI suite. A command tool returning after 30 seconds is not evidence that the test process timed out. Complete validation requires following the running session through its unittest summary and process exit status.

## Confirmed test cleanup defect

The GUI fixtures shared one `QApplication` and called `close()` on their windows without destroying their underlying Qt objects. A four-window probe retained 687, 1,374, 2,061 and 2,748 widgets after closure, Python garbage collection and event processing. Each subsequent `BridgeWindow` reapplies the application-wide theme, so retained widgets make later tests increasingly expensive.

The fixtures now use `tests.gui_support.dispose_widget`: close to stop managed refresh, wait up to 15 seconds for the shared Qt thread pool, then request and deliver deferred deletion. A timeout fails explicitly before deleting a widget whose workers may still be active. Cleanup also tolerates parents or children already destroyed by earlier cleanup. Production window behavior, background loading and workbook safety are unchanged.

Four new regressions cover repeated window/child/dialog destruction, repeated cleanup, active-worker completion before destruction, and the bounded timeout. Against the original close-only behavior, the repeated-window and worker-order tests produced four expected failures. All four pass with the helper. An independent check also confirmed that representative comparison, managed-refresh and timeline-dialog tests each left zero Qt widgets after cleanup.

## Verification

Environment: macOS arm64, Python 3.11.2, PySide6 6.11.2, `QT_QPA_PLATFORM=offscreen`, with the existing fingerprinted dependency environment selected by `scripts/test.sh`.

- Original baseline at `7d8a91c`, `./scripts/test.sh`: **194 tests passed in 527.235 seconds**, no skips, exit status 0. Its terminal result confirms that the earlier scan had incomplete evidence rather than a demonstrated failing test.
- Complete canonical run with the cleanup fix, `./scripts/test.sh`: **198 tests passed in 81.669 seconds**, no skips, exit status 0. This includes every existing test and the four new lifecycle regressions.
- Focused run of all seven existing GUI test modules plus the new lifecycle module: **65 tests passed in 70.663 seconds**, no skips, exit status 0.
- Optional-dependency compatibility check with `python3 -S`: the same 65 tests were discovered and skipped because PySide6 was unavailable, exit status 0. This verifies import/skip compatibility only; it is not GUI execution coverage.
- `python3 -m compileall -q src tests packaging`: passed.
- Source app-entry `--smoke-test` using the test environment and offscreen Qt: passed for version 0.9.1.
- `git diff --check`: passed.

These are observed local durations, not benchmark guarantees; the runs overlapped with other focused validation work. GitHub CI and review status are tracked on the follow-up pull request.

## Validation boundary

Offscreen tests exercise widget layout, interaction, background loading, feedback safety and navigation against synthetic fixtures. They do not replace native macOS visual inspection or verification of a newly built application bundle. This change modifies test cleanup and verification guidance only; no bundle rebuild or installed-app replacement is required.

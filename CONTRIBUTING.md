# Contributing

Thanks for improving MacroFactor Workout Bridge. Start with the [development guide](docs/Development.md) for setup, tests, dependencies, and packaging, and the [architecture map](docs/Architecture.md) to find the right module. The [documentation index](docs/README.md) links to user workflows and command references.

1. Search existing issues and pull requests. Open an issue before changing source immutability, overwrite protection, workbook-part preservation, exact exercise matching, privacy, or external data access.
2. Make a focused branch and add tests for behavior changes. Use only synthetic or deliberately anonymized fixtures. Follow the full [verification gate](docs/Development.md#verification).
3. In the pull request, describe the user-visible result, workbook and privacy implications, test results (including the final exit status), and any manual macOS checks. The [pull request template](.github/pull_request_template.md) provides a checklist.

Exports and coach workbooks are immutable inputs. Outputs must use new paths, and workbook edits must preserve unrelated OOXML parts, formulas, styles, and structure. Matching stays exact and reviewable. Runtime processing remains local. Never commit real exports, coach workbooks, reports, manifests, credentials, or unredacted local paths in code, tests, screenshots, issues, or pull requests.

Participation follows the [Code of Conduct](CODE_OF_CONDUCT.md); report conduct concerns through its private channel. Report vulnerabilities through the [Security Policy](SECURITY.md#reporting-a-vulnerability), without publishing sensitive details. These are separate reporting paths.

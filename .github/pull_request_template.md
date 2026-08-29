## Summary

- What changed?
- Why is this the safest appropriate behavior?

## Privacy and workbook safety

- [ ] No real MacroFactor exports, coach workbooks, generated reports, local manifests, credentials, or machine-specific paths are included.
- [ ] Tests and examples use synthetic or deliberately anonymized data.
- [ ] Source files remain read-only and output still uses a distinct, non-existing path, or the change clearly explains why these invariants are unaffected.
- [ ] Security-sensitive details are reported privately through the Security Policy, not disclosed in this pull request.

## Verification

- [ ] `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- [ ] `python3 -m compileall -q src tests packaging`
- [ ] `git diff --check`
- [ ] Relevant manual macOS checks are described below, or are not applicable.

## Manual checks and screenshots

<!-- Use only synthetic data. Redact account names, file paths, workbook names, and other personal information. -->

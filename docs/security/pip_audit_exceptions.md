# pip-audit Exceptions

This file records explicit, reviewable exceptions used by release-prep and CI
security gates. An exception here is not a blanket waiver: `pip-audit` must keep
running, and only the listed advisory may be ignored.

## PYSEC-2024-277

- ID: `PYSEC-2024-277`
- CVE: `CVE-2024-34997`
- Package: `joblib`
- Status: disputed/no fixed version available
- Context: reported by `pip-audit` during RiskBands v2.4.0 release-prep.
- Risk: `joblib`/pickle deserialization can execute arbitrary code if an
  application loads untrusted serialized artifacts.
- RiskBands mitigation: RiskBands does not load untrusted `joblib`/pickle
  artifacts as part of the public workflow. RiskBands bundles use auditable
  formats such as JSON, CSV, and HTML where applicable.
- Decision: explicitly ignore `PYSEC-2024-277` in the `pip-audit` gate until a
  fixed version is available or the advisory is reclassified.
- Future review: re-evaluate this exception during each release-prep cycle and
  remove it as soon as an actionable upstream fix or corrected advisory metadata
  is available.

Approved command:

```bash
python -m pip_audit --ignore-vuln PYSEC-2024-277
```

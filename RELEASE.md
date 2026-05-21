# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.4.0`
- Planned release tag: `v2.4.0`
- Default branch: `main`
- Preparation branch: `release/v2.4.0-prep`
- Status: prepared for v2.4.0 publication review after local validation.

No PyPI upload, TestPyPI upload, tag creation, workflow dispatch, or push is
performed by Sprint I.

## 2.4.0 Release Notes

Type: compatible minor release preparation.

Positioning: RiskBands v2.4.0 - Spark missing merge, audit bundle narrative
reporting, public docs, examples, and Reveal.js documentation gallery.

### Added

- Spark transform support for `missing_policy="merge"` with learned merge
  decisions applied through native Spark expressions and `return_woe=False`.
- Spark sampled-to-pandas fit for missing merge, recording that the merge
  decision was learned on a controlled sample rather than a Spark-native full
  fit.
- Spark validation/reporting diagnostics for sampled missing merge, including
  `source_profile_`, sample-vs-source comparisons, and
  `missing_sampling_diagnostics`.
- Sampling caveats in metadata, bundle outputs, and `audit_report.html`.
- Narrative `audit_report.html` with embedded CSS, print-friendly layout,
  missing policy explanations, merge decisions, validation alerts, bundle
  inventory, and known limitations.
- Bundle integration for the narrative audit report through
  `export_bundle(..., include_audit_report=True)`.
- Docs-site Reveal.js gallery and RiskBands overview presentation.
- Public pt-BR/en docs and runnable examples for missing policy, audit report,
  bundle/reporting, and Spark missing merge.

### Compatibility

- `missing_policy="standard"` remains the default.
- `missing_policy="separate_bin"`, `missing_policy="forbid"`, and pandas
  `missing_policy="merge"` remain supported.
- `missing_merge_criterion="nearest_event_rate"` and
  `missing_merge_criterion="nearest_woe"` remain the only merge criteria.
- `missing_merge_fallback="separate_bin"` and
  `missing_merge_fallback="raise"` remain supported.
- `score_strategy="standard"` remains canonical; `score_strategy="legacy"`
  remains a compatibility alias.
- Existing `from riskbands import Binner` and `Binner(...)` usage is preserved.
- `RiskBands` remains the preferred public estimator name and aliases `Binner`.
- Base installation does not install PySpark.
- PySpark remains optional through `riskbands[spark]` with `pyspark>=3.5.2,<4`.

### Security Audit Exception

- The standard `python -m pip_audit` command reports
  `joblib/PYSEC-2024-277`, a disputed deserialization advisory with no fixed
  version available.
- RiskBands does not load untrusted `joblib`/pickle artifacts as part of the
  public workflow; bundle outputs use auditable formats such as JSON, CSV, and
  HTML where applicable.
- Release-prep keeps `pip-audit` enabled and ignores only this advisory through
  `python -m pip_audit --ignore-vuln PYSEC-2024-277`.
- The rationale and future review requirement are documented in
  `docs/security/pip_audit_exceptions.md`.

### Explicitly Out Of Scope

- No Spark-native full-data fitting backend for missing merge is added.
- No Spark `return_woe=True` support is added.
- No `temporal_stable` or `monotonic_neighbor` merge criterion is added.
- No additional merge criteria beyond `nearest_event_rate` and `nearest_woe`
  are added.
- No opaque intelligent imputation is added.
- No native PDF export for the audit report is added.
- No regulatory compliance guarantee is made.

## Workflows In Use

- `tests.yml`: regular CI test suite.
- `release-validation.yml`: package build, `twine check`, wheel smoke, and
  sdist smoke for PRs, `main`, manual dispatch, and tags.
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes
  to `main` and manual dispatch.
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing.
  Run manually only after review.
- `publish-pypi.yml`: PyPI publication via Trusted Publishing. Run manually only
  after review.

## Release Sequence

1. Prepare versioned files and release notes for `2.4.0`.
2. Run the complete local validation suite.
3. Confirm Spark tests with the configured local Java/PySpark environment.
4. Confirm docs-site build and Reveal.js route build.
5. Confirm package build, `twine check`, smoke base install, and smoke `[spark]`
   install.
6. Confirm no tag, push, workflow dispatch, PyPI upload, or TestPyPI upload was
   performed during Sprint I.
7. Commit the final release-prep changes only after review.
8. Open a PR from `release/v2.4.0-prep` to `main`.
9. Create the annotated git tag `v2.4.0` manually only after review approval and
   merge.
10. Push `main` and the tag manually.
11. Confirm `release-validation.yml` is green for the pushed tag.
12. Optionally run `publish-testpypi.yml` on the reviewed tag.
13. Run `publish-pypi.yml` on the same stable tag only after release validation
   and optional TestPyPI smoke checks are green.
14. Confirm `docs-deploy.yml` is green after the push to `main`.

Do not replace an artifact that already exists on a package index. If a defect
is found after PyPI publication, yank the affected version and prepare a new
version.

## Local Validation

Use the repository virtual environment or another clean Python environment.

Recommended command sequence:

```powershell
.\.venv-v210-spark\Scripts\python.exe -m pip check
.\.venv-v210-spark\Scripts\python.exe -m ruff check riskbands tests
.\.venv-v210-spark\Scripts\python.exe -m bandit -q -r riskbands
.\.venv-v210-spark\Scripts\python.exe -m pytest --basetemp .pytest_tmp\v240-full-core
.\.venv-v210-spark\Scripts\python.exe -m pytest -m spark --basetemp .pytest_tmp\v240-full-spark
.\.venv-v210-spark\Scripts\python.exe -m pip_audit --ignore-vuln PYSEC-2024-277
npm --prefix docs-site run build
Remove-Item -Recurse -Force dist, build, riskbands.egg-info -ErrorAction SilentlyContinue
.\.venv-v210-spark\Scripts\python.exe -m build
.\.venv-v210-spark\Scripts\python.exe -m twine check dist/*
```

Wheel smoke test, base install:

```powershell
python -m venv .pytest_tmp\v240-smoke-base
.\.pytest_tmp\v240-smoke-base\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v240-smoke-base\Scripts\python.exe -m pip install dist/riskbands-2.4.0-py3-none-any.whl
.\.pytest_tmp\v240-smoke-base\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.4.0 --expect-no-pyspark
.\.pytest_tmp\v240-smoke-base\Scripts\python.exe -m pip check
```

Wheel smoke test with the `spark` extra:

```powershell
python -m venv .pytest_tmp\v240-smoke-spark
.\.pytest_tmp\v240-smoke-spark\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v240-smoke-spark\Scripts\python.exe -m pip install "dist/riskbands-2.4.0-py3-none-any.whl[spark]"
.\.pytest_tmp\v240-smoke-spark\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.4.0 --check-spark --expect-pyspark-major 3
.\.pytest_tmp\v240-smoke-spark\Scripts\python.exe -m pip check
```

Docs-site validation:

```powershell
npm --prefix docs-site ci
npm --prefix docs-site run build
```

## Tag Rules

Both publication workflows require:

- the workflow to run against a git tag, not a branch;
- the tag name to match `v<pyproject version>`;
- the package version to be stable, such as `2.4.0`.

For this target, the planned tag is `v2.4.0`. Do not create the tag during
Sprint I.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when release preparation
changes packaging, metadata, dependencies, or installation behavior.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .pytest_tmp\v240-testpypi
.\.pytest_tmp\v240-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v240-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.4.0
.\.pytest_tmp\v240-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.4.0 --expect-no-pyspark
.\.pytest_tmp\v240-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[spark]==2.4.0"
.\.pytest_tmp\v240-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.4.0 --check-spark --expect-pyspark-major 3
```

## PyPI

Run `publish-pypi.yml` manually on `v2.4.0` only after:

- local validation is complete and green;
- `release-validation.yml` is green on the pushed tag;
- the tag points to the intended release commit;
- optional TestPyPI validation has completed, if used;
- the PyPI trusted publisher is configured for repository `joaaomaia/RiskBands`;
- the `pypi` GitHub environment is approved when required.

## Docs Site

`docs-deploy.yml` builds the site from `docs-site/` and deploys automatically on
pushes to `main`.

To validate locally:

```powershell
npm --prefix docs-site ci
npm --prefix docs-site run build
```

## Failure Handling

- If validation or packaging fails before publication, fix forward on the branch
  and tag only when the final version is ready.
- If TestPyPI succeeds but smoke tests fail, do not publish to PyPI; prepare the
  next version instead.
- If PyPI succeeds and a defect is found afterwards, yank the affected version
  and prepare a new stable version rather than replacing artifacts.

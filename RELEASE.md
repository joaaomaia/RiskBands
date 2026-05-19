# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.3.0`
- Planned release tag: `v2.3.0`
- Default branch: `main`
- Preparation branch: `release/v2.3.0-prep`
- Status: prepared for v2.3.0 publication review after local validation.

No PyPI upload, TestPyPI upload, tag creation, or push is performed by Sprint E3.

## 2.3.0 Release Notes

Type: compatible minor release preparation.

Positioning: RiskBands v2.3.0 - auditable missing merge policies.

### Added

- `missing_policy="merge"` for pandas flows that need to route a missing group into a learned regular bin while preserving audit evidence.
- `missing_merge_criterion="nearest_event_rate"` to select the regular candidate bin with the closest fit-time event rate.
- `missing_merge_criterion="nearest_woe"` to select the regular candidate bin with the closest fit-time WoE.
- `missing_merge_fallback="separate_bin"` and `missing_merge_fallback="raise"` for transform-time missing values when no fit-time merge decision was learned.
- `missing_merge_candidates_`, `missing_merge_map_`, and richer `missing_decision_log_` fields for reviewable merge decisions.
- Bundle and report persistence for merge criterion, fallback, candidates, selected destination, distances, and merge map.

### Changed

- Release documentation now describes merge as an opt-in policy alongside `standard`, `separate_bin`, and `forbid`.
- README, technical docs, and docs-site pages explain when to use `nearest_event_rate` versus `nearest_woe`.
- pandas examples include `separate_bin`, merge with both criteria, fallback behavior, audit fields, and bundle roundtrip.

### Compatibility

- `missing_policy="standard"` remains the default.
- `missing_policy="separate_bin"` and `missing_policy="forbid"` remain supported.
- `score_strategy="standard"` remains canonical; `score_strategy="legacy"` remains a compatibility alias.
- Existing `from riskbands import Binner` and `Binner(...)` usage is preserved.
- `RiskBands` remains the preferred public estimator name and aliases `Binner`.
- Bundles created before missing-merge metadata existed continue to load with missing-merge fields as `None`.
- The base installation does not install PySpark.
- PySpark support remains optional through `riskbands[spark]`.
- The Spark extra remains constrained to `pyspark>=3.5,<4`.

### Explicitly Out Of Scope

- No `temporal_stable` missing-merge criterion is included.
- No `monotonic_neighbor` missing-merge criterion is included.
- No additional merge criteria beyond `nearest_event_rate` and `nearest_woe` are included.
- No opaque intelligent imputation is added.
- No full PySpark implementation for `missing_policy="merge"` is added.
- No PySpark 4.x support is promised.
- No regulatory compliance guarantee is made.

## Workflows In Use

- `tests.yml`: regular CI test suite.
- `release-validation.yml`: package build, `twine check`, wheel smoke, and sdist smoke for PRs, `main`, manual dispatch, and tags.
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes to `main` and manual dispatch.
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing. Run manually only after review.
- `publish-pypi.yml`: PyPI publication via Trusted Publishing. Run manually only after review.

## Release Sequence

1. Prepare versioned files and release notes for `2.3.0`.
2. Run the complete local validation suite.
3. Confirm docs-site build.
4. Confirm package build, `twine check`, smoke base install, and smoke `[spark]` install.
5. Confirm no tag, push, PyPI upload, or TestPyPI upload was performed during Sprint E3.
6. Commit the final release-prep changes after review.
7. Open a PR from `release/v2.3.0-prep` to `main`.
8. Create the annotated git tag `v2.3.0` manually only after review approval and merge.
9. Push `main` and the tag manually.
10. Confirm `release-validation.yml` is green for the pushed tag.
11. Optionally run `publish-testpypi.yml` on the reviewed tag.
12. Run `publish-pypi.yml` on the same stable tag only after release validation and optional TestPyPI smoke checks are green.
13. Confirm `docs-deploy.yml` is green after the push to `main`.

Do not replace an artifact that already exists on a package index. If a defect is found after PyPI publication, yank the affected version and prepare a new version.

## Local Validation

Use the repository virtual environment or another clean Python environment.

Recommended command sequence:

```powershell
.\.venv-v210-spark\Scripts\python.exe -m pip check
.\.venv-v210-spark\Scripts\python.exe -m ruff check riskbands tests
.\.venv-v210-spark\Scripts\python.exe -m bandit -q -r riskbands
.\.venv-v210-spark\Scripts\python.exe -m pytest --basetemp .pytest_tmp\v230-full-core
.\.venv-v210-spark\Scripts\python.exe -m pytest -m spark --basetemp .pytest_tmp\v230-full-spark
.\.venv-v210-spark\Scripts\python.exe -m pip_audit
npm --prefix docs-site run build
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue
.\.venv-v210-spark\Scripts\python.exe -m build
.\.venv-v210-spark\Scripts\python.exe -m twine check dist/*
```

Wheel smoke test, base install:

```powershell
python -m venv .pytest_tmp\v230-smoke-base
.\.pytest_tmp\v230-smoke-base\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v230-smoke-base\Scripts\python.exe -m pip install dist/riskbands-2.3.0-py3-none-any.whl
.\.pytest_tmp\v230-smoke-base\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.3.0 --expect-no-pyspark
.\.pytest_tmp\v230-smoke-base\Scripts\python.exe -c "import importlib.util, riskbands; from riskbands import RiskBands, Binner; print('version:', riskbands.__version__); print('RiskBands is Binner:', RiskBands is Binner); print('pyspark_installed:', importlib.util.find_spec('pyspark') is not None); assert riskbands.__version__ == '2.3.0'; assert RiskBands is Binner; assert importlib.util.find_spec('pyspark') is None"
.\.pytest_tmp\v230-smoke-base\Scripts\python.exe -m pip check
```

Wheel smoke test with the `spark` extra:

```powershell
python -m venv .pytest_tmp\v230-smoke-spark
.\.pytest_tmp\v230-smoke-spark\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v230-smoke-spark\Scripts\python.exe -m pip install "dist/riskbands-2.3.0-py3-none-any.whl[spark]"
.\.pytest_tmp\v230-smoke-spark\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.3.0 --check-spark --expect-pyspark-major 3
.\.pytest_tmp\v230-smoke-spark\Scripts\python.exe -c "import pyspark; print('pyspark:', pyspark.__version__); assert int(pyspark.__version__.split('.')[0]) == 3"
.\.pytest_tmp\v230-smoke-spark\Scripts\python.exe -m pip check
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
- the package version to be stable, such as `2.3.0`.

For this target, the planned tag is `v2.3.0`. Do not create the tag during Sprint E3.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when release preparation changes packaging, metadata, dependencies, or installation behavior.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .pytest_tmp\v230-testpypi
.\.pytest_tmp\v230-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v230-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.3.0
.\.pytest_tmp\v230-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.3.0 --expect-no-pyspark
.\.pytest_tmp\v230-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[spark]==2.3.0"
.\.pytest_tmp\v230-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.3.0 --check-spark --expect-pyspark-major 3
```

## PyPI

Run `publish-pypi.yml` manually on `v2.3.0` only after:

- local validation is complete and green;
- `release-validation.yml` is green on the pushed tag;
- the tag points to the intended release commit;
- optional TestPyPI validation has completed, if used;
- the PyPI trusted publisher is configured for repository `joaaomaia/RiskBands`;
- the `pypi` GitHub environment is approved when required.

## Docs Site

`docs-deploy.yml` builds the site from `docs-site/` and deploys automatically on pushes to `main`.

To validate locally:

```powershell
npm --prefix docs-site ci
npm --prefix docs-site run build
```

## Failure Handling

- If validation or packaging fails before publication, fix forward on the branch and tag only when the final version is ready.
- If TestPyPI succeeds but smoke tests fail, do not publish to PyPI; prepare the next version instead.
- If PyPI succeeds and a defect is found afterwards, yank the affected version and prepare a new stable version rather than replacing artifacts.

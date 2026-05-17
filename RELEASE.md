# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.2.0`
- Planned release tag: `v2.2.0`
- Default branch: `main`
- Preparation branch: `release/v2.2.0-prep`
- Status: prepared for v2.2.0 publication after local validation.

No PyPI upload, TestPyPI upload, tag creation, or push is performed by Sprint C.

## 2.2.0 Release Notes

Type: compatible minor release preparation.

### Added

- `missing_policy="standard"` as the default missing-value policy, preserving the Sprint A baseline behavior.
- `missing_policy="separate_bin"` as an opt-in policy that creates explicit `Missing` bins, including categorical missing values.
- `missing_policy="forbid"` for governance flows that must fail when selected features contain missing values.
- pandas and PySpark support for the missing-policy contract.
- Persistence of `missing_policy`, `effective_missing_policy`, `missing_profile`, and `missing_decision_log` in fitted objects and bundles.

### Changed

- `standard` is the canonical name for the historical maximize-oriented score strategy.
- `legacy` remains accepted only as a compatibility alias for `standard`.
- New metadata and bundle fields use the canonical `standard` naming where applicable.

### Compatibility

- Existing `from riskbands import Binner` and `Binner(...)` usage is preserved.
- `RiskBands` remains the preferred public estimator name and aliases `Binner`.
- Bundles created before the missing-policy metadata existed continue to load as `standard`.
- The base installation does not install PySpark.
- PySpark support remains optional through `riskbands[spark]`.
- The Spark extra remains constrained to `pyspark>=3.5,<4`.

### Explicitly Out Of Scope

- No merge policies are included in this target. `merge_nearest_woe`, `merge_nearest_event_rate`, and similar policies remain future work.
- No opaque intelligent imputation is added.
- No new full distributed Spark fitting backend is added.
- No default change away from `missing_policy="standard"` is included.

## Workflows In Use

- `tests.yml`: regular CI test suite.
- `release-validation.yml`: package build, `twine check`, wheel smoke, and sdist smoke for PRs, `main`, manual dispatch, and tags.
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes to `main` and manual dispatch.
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing. Run manually only after review.
- `publish-pypi.yml`: PyPI publication via Trusted Publishing. Run manually only after review.

## Release Sequence

1. Prepare versioned files and release notes for `2.2.0`.
2. Run the complete local validation suite.
3. Confirm docs-site build.
4. Confirm package build, `twine check`, smoke base install, and smoke `[spark]` install.
5. Confirm no tag, push, PyPI upload, or TestPyPI upload was performed during Sprint C.
6. Commit the final release-prep changes after review.
7. Create the annotated git tag `v2.2.0` manually only after review approval.
8. Push `main` and the tag manually.
9. Confirm `release-validation.yml` is green for the pushed tag.
10. Optionally run `publish-testpypi.yml` on the reviewed tag.
11. Run `publish-pypi.yml` on the same stable tag only after release validation and optional TestPyPI smoke checks are green.
12. Confirm `docs-deploy.yml` is green after the push to `main`.

Do not replace an artifact that already exists on a package index. If a defect is found after PyPI publication, yank the affected version and prepare a new version.

## Local Validation

Use a clean project virtual environment rather than a globally shared Python environment.

Recommended command sequence:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
python -m pip check
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --cov=riskbands --cov-report=term-missing --basetemp .pytest_tmp/v220-final
python -m pytest -m spark --basetemp .pytest_tmp/v220-spark
python -m pip_audit
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue
python -m build
python -m twine check dist/*
```

Wheel smoke test, base install:

```powershell
python -m venv .pytest_tmp\v220-smoke-base
.\.pytest_tmp\v220-smoke-base\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v220-smoke-base\Scripts\python.exe -m pip install dist/riskbands-2.2.0-py3-none-any.whl
.\.pytest_tmp\v220-smoke-base\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.2.0
.\.pytest_tmp\v220-smoke-base\Scripts\python.exe -c "import importlib.util, riskbands; from riskbands import RiskBands, Binner; print('version:', riskbands.__version__); print('RiskBands is Binner:', RiskBands is Binner); print('pyspark_installed:', importlib.util.find_spec('pyspark') is not None); assert riskbands.__version__ == '2.2.0'; assert RiskBands is Binner; assert importlib.util.find_spec('pyspark') is None"
```

Wheel smoke test with the `spark` extra:

```powershell
python -m venv .pytest_tmp\v220-smoke-spark
.\.pytest_tmp\v220-smoke-spark\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v220-smoke-spark\Scripts\python.exe -m pip install "dist/riskbands-2.2.0-py3-none-any.whl[spark]"
.\.pytest_tmp\v220-smoke-spark\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.2.0
.\.pytest_tmp\v220-smoke-spark\Scripts\python.exe -c "import pyspark; print('pyspark:', pyspark.__version__); assert int(pyspark.__version__.split('.')[0]) == 3"
```

Sdist smoke test:

```powershell
python -m venv .pytest_tmp\v220-smoke-sdist
.\.pytest_tmp\v220-smoke-sdist\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v220-smoke-sdist\Scripts\python.exe -m pip install dist/riskbands-2.2.0.tar.gz
.\.pytest_tmp\v220-smoke-sdist\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.2.0
.\.pytest_tmp\v220-smoke-sdist\Scripts\python.exe -c "import importlib.util; print('pyspark_installed:', importlib.util.find_spec('pyspark') is not None); assert importlib.util.find_spec('pyspark') is None"
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
- the package version to be stable, such as `2.2.0`.

For this target, the planned tag is `v2.2.0`. Do not create the tag during Sprint C.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when release preparation changes packaging, metadata, dependencies, or installation behavior.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .pytest_tmp\v220-testpypi
.\.pytest_tmp\v220-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.pytest_tmp\v220-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.2.0
.\.pytest_tmp\v220-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.2.0 --expect-no-pyspark
.\.pytest_tmp\v220-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[spark]==2.2.0"
.\.pytest_tmp\v220-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.2.0 --check-spark --expect-pyspark-major 3
```

## PyPI

Run `publish-pypi.yml` manually on `v2.2.0` only after:

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

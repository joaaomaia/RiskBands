# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.1.0`
- Planned release tag: `v2.1.0`
- Default branch: `main`
- Status: prepared for v2.1.0 publication.

## 2.1.0 Release Notes

Type: compatible minor release.

### Added

- `RiskBands` as the preferred public name for the main estimator.
- `Binner` remains available as a compatible alias.
- `min_n_bins` as a soft, auditable quality rule.
- `sample_size` for controlled PySpark fit sampling.
- Automatic pandas/PySpark backend detection in `fit` and `transform`.
- DataFrame type preservation: pandas inputs return pandas outputs, PySpark inputs return PySpark outputs.
- `fit(validate=True)` with fit profiles, uncertainty diagnostics, `min_n_bins` status, sample/source comparison when available, and `fit_validation_report_`.
- `transform(validate=True)` with application profiles compared against a stored `reference_profile` and `transform_validation_report_`.
- v2.1.0 bundle metadata with fit/source/reference/application profiles, separate validation reports, backend metadata, sampling metadata, `min_n_bins` metadata, validation settings, and data schema when available.
- Optional `spark` extra for PySpark support.

### Changed

- Bundle exports include `bundle_schema_version` while preserving existing artifact fields.
- PySpark `fit` uses controlled sampling and the current pandas statistical engine.
- PySpark `transform` and validation profiles use native Spark expressions and aggregated profiles, preserving Spark DataFrame output without collecting full validation datasets.

### Compatibility

- Existing `from riskbands import Binner` and `Binner(...)` usage is preserved.
- PySpark is not required for the base installation.
- Spark tests are marked and skipped when PySpark is unavailable.
- Legacy bundles without v2.1.0 profile fields continue to load through the bundle metadata loader.

### Notes

- v2.1.0 does not implement a full distributed Spark fitting backend.
- v2.1.0 does not publish automatically to PyPI or TestPyPI.

## Workflows In Use

- `tests.yml`: regular CI test suite
- `release-validation.yml`: tag-oriented release validation with package build, `twine check`, wheel smoke, and sdist smoke
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes to `main`
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing
- `publish-pypi.yml`: PyPI publication via Trusted Publishing

## Release Sequence

1. Update versioned files and release notes to the target version.
2. Run the complete local validation suite before creating the tag.
3. Commit the final release preparation changes.
4. Create the annotated git tag `v2.1.0` only after local validation is green.
5. Push `main` and the tag.
6. Confirm `release-validation.yml` is green for the pushed tag.
7. Optionally run `publish-testpypi.yml` on the tag. This is recommended for packaging, metadata, dependency, and installation changes.
8. Run `publish-pypi.yml` on the same stable tag only after release validation is green.
9. Confirm `docs-deploy.yml` is green after the push to `main`.

Do not replace an artifact that has already been published. If a defect is found after PyPI publication, yank the affected release and prepare a new version.

## Local Validation

Use a clean project virtual environment rather than a globally shared Python environment.

Recommended command sequence:

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]
python -m pip check
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --cov=riskbands --cov-report=term-missing --basetemp .pytest_tmp/v210-final
python -m pip_audit
python -m build
python -m twine check dist/*
```

Wheel smoke test:

```powershell
python -m venv .venv-smoke-210
.\.venv-smoke-210\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-210\Scripts\python.exe -m pip install dist/riskbands-2.1.0-py3-none-any.whl
.\.venv-smoke-210\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.1.0
```

Wheel smoke test with the `viz` extra:

```powershell
python -m venv .venv-smoke-210-viz
.\.venv-smoke-210-viz\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-210-viz\Scripts\python.exe -m pip install "dist/riskbands-2.1.0-py3-none-any.whl[viz]"
.\.venv-smoke-210-viz\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.1.0 --check-viz
```

Sdist smoke test:

```powershell
python -m venv .venv-smoke-210-sdist
.\.venv-smoke-210-sdist\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-210-sdist\Scripts\python.exe -m pip install dist/riskbands-2.1.0.tar.gz
.\.venv-smoke-210-sdist\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.1.0
```

Docs-site validation:

```powershell
npm --prefix docs-site ci
npm --prefix docs-site run build
```

## Tag Rules

Both publication workflows require:

- the workflow to run against a git tag, not a branch
- the tag name to match `v<pyproject version>`

For this target, the planned tag is `v2.1.0`. `publish-pypi.yml` requires a stable semantic version such as `2.1.0`; do not publish an `rc` version unless the project explicitly adopts a release-candidate publishing policy.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when the release changes packaging, metadata, dependencies, or installation behaviour.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .venv-testpypi
.\.venv-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.1.0
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.1.0
```

Optional visualization extra:

```powershell
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[viz]==2.1.0"
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.1.0 --check-viz
```

## PyPI

Run `publish-pypi.yml` manually on `v2.1.0` only after:

- local validation is complete and green
- `release-validation.yml` is green on the pushed tag
- the tag points to the intended release commit
- the PyPI trusted publisher is configured for repository `joaaomaia/RiskBands`
- the `pypi` GitHub environment is approved when required

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
- If PyPI succeeds and a defect is found afterwards, yank the bad release on PyPI and cut a new stable version rather than replacing artifacts.

# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.0.3`
- Planned release tag: `v2.0.3`
- Default branch: `master`
- Status: local release candidate preparation; not published yet

## Workflows In Use

- `tests.yml`: regular CI test suite
- `release-validation.yml`: tag-oriented release validation with package build, `twine check`, wheel smoke, and sdist smoke
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes to `master`
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing
- `publish-pypi.yml`: PyPI publication via Trusted Publishing

## Release Sequence

1. Update versioned files and release notes to the target version.
2. Run the complete local validation suite before creating the tag.
3. Commit the release candidate changes.
4. Create the annotated git tag `v2.0.3` only after local validation is green.
5. Push `master` and the tag.
6. Confirm `release-validation.yml` is green for the pushed tag.
7. Optionally run `publish-testpypi.yml` on the tag. This is recommended for packaging, metadata, dependency, and installation changes.
8. Run `publish-pypi.yml` on the same stable tag only after release validation is green.
9. Confirm `docs-deploy.yml` is green after the push to `master`.

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
python -m pytest -q --cov=riskbands --cov-report=term-missing --basetemp .pytest_tmp/rc_203
python -m pip_audit
python -m build
python -m twine check dist/*
```

Wheel smoke test:

```powershell
python -m venv .venv-smoke-203
.\.venv-smoke-203\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-203\Scripts\python.exe -m pip install dist/riskbands-2.0.3-py3-none-any.whl
.\.venv-smoke-203\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.3
```

Wheel smoke test with the `viz` extra:

```powershell
python -m venv .venv-smoke-203-viz
.\.venv-smoke-203-viz\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-203-viz\Scripts\python.exe -m pip install "dist/riskbands-2.0.3-py3-none-any.whl[viz]"
.\.venv-smoke-203-viz\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.3 --check-viz
```

Sdist smoke test:

```powershell
python -m venv .venv-smoke-203-sdist
.\.venv-smoke-203-sdist\Scripts\python.exe -m pip install --upgrade pip
.\.venv-smoke-203-sdist\Scripts\python.exe -m pip install dist/riskbands-2.0.3.tar.gz
.\.venv-smoke-203-sdist\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.3
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

For this target, the planned tag is `v2.0.3`. `publish-pypi.yml` requires a stable semantic version such as `2.0.3`; do not publish an `rc` version unless the project explicitly adopts a release-candidate publishing policy.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when the release changes packaging, metadata, dependencies, or installation behaviour.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .venv-testpypi
.\.venv-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.0.3
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.3
```

Optional visualization extra:

```powershell
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[viz]==2.0.3"
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.3 --check-viz
```

## PyPI

Run `publish-pypi.yml` manually on `v2.0.3` only after:

- local validation is complete and green
- `release-validation.yml` is green on the pushed tag
- the tag points to the intended release commit
- the PyPI trusted publisher is configured for repository `joaaomaia/RiskBands`
- the `pypi` GitHub environment is approved when required

## Docs Site

`docs-deploy.yml` builds the site from `docs-site/` and deploys automatically on pushes to `master`.

To validate locally:

```powershell
npm --prefix docs-site ci
npm --prefix docs-site run build
```

## Failure Handling

- If validation or packaging fails before publication, fix forward on the branch and tag only when the final version is ready.
- If TestPyPI succeeds but smoke tests fail, do not publish to PyPI; prepare the next version instead.
- If PyPI succeeds and a defect is found afterwards, yank the bad release on PyPI and cut a new stable version rather than replacing artifacts.

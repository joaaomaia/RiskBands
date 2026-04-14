# RiskBands Release Runbook

## Current Target

- Project: `RiskBands`
- Distribution: `riskbands`
- Repository version: `2.0.2`
- Release tag: `v2.0.2`
- Default branch: `master`

## Workflows In Use

- `tests.yml`: regular CI test suite
- `release-validation.yml`: release-oriented pytest subset, package build, `twine check`, wheel smoke, and sdist smoke
- `docs-deploy.yml`: Astro/Starlight build plus GitHub Pages deploy on pushes to `master`
- `publish-testpypi.yml`: optional TestPyPI publication via Trusted Publishing
- `publish-pypi.yml`: PyPI publication via Trusted Publishing

## Release Sequence

1. Update versioned files and release notes to the target version.
2. Run local validation aligned with `release-validation.yml`.
3. Commit the release candidate changes.
4. Create the annotated git tag `v<version>`.
5. Push `master` and the tag.
6. Confirm `release-validation.yml` is green for the pushed tag.
7. Optionally run `publish-testpypi.yml` on the tag.
8. Run `publish-pypi.yml` on the same stable tag.
9. Confirm `docs-deploy.yml` is green after the push to `master`.

## Local Validation

Recommended command sequence:

```powershell
C:\Users\JM\AppData\Local\anaconda3\python.exe -m pip install -e .[dev]
C:\Users\JM\AppData\Local\anaconda3\python.exe -m pytest -q tests\test_public_api.py tests\test_api_usability.py tests\test_binning_engine.py tests\test_compare.py tests\test_examples_smoke.py tests\test_stable_score.py tests\test_temporal_stability.py --basetemp .pytest_tmp_release
C:\Users\JM\AppData\Local\anaconda3\python.exe -m build
C:\Users\JM\AppData\Local\anaconda3\python.exe -m twine check dist\*
```

This mirrors the key steps enforced by the release workflow.

## Tag Rules

Both publication workflows require:

- the workflow to run against a git tag, not a branch
- the tag name to match `v<pyproject version>`

`publish-pypi.yml` also requires a stable semantic version such as `2.0.2`.

## TestPyPI

`publish-testpypi.yml` is optional but recommended when the release changes packaging, metadata, or installation behaviour.

After a successful TestPyPI upload, smoke test with:

```powershell
python -m venv .venv-testpypi
.\.venv-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==2.0.2
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.2
```

Optional visualization extra:

```powershell
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[viz]==2.0.2"
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 2.0.2 --check-viz
```

## PyPI

Run `publish-pypi.yml` manually on `v2.0.2` only after:

- `release-validation.yml` is green
- the tag points to the intended release commit
- the PyPI trusted publisher is configured for repository `joaaomaia/RiskBands`
- the `pypi` GitHub environment is approved when required

## Docs Site

`docs-deploy.yml` builds the site from `docs-site/` and deploys automatically on pushes to `master`.

To validate locally:

```powershell
cd docs-site
npm ci
npm run build
```

## Failure Handling

- If validation or packaging fails before publication, fix forward on the branch and retag only when the final version is ready.
- If TestPyPI succeeds but smoke tests fail, do not publish to PyPI; prepare the next version instead.
- If PyPI succeeds and a defect is found afterwards, yank the bad release on PyPI and cut a new stable version rather than replacing artifacts.

# RiskBands Release Runbook

## Project Identity

- Project name: `RiskBands`
- Distribution name: `riskbands`
- Import name: `riskbands`
- Current version in the repository: `1.0.0`
- GitHub owner: `joaaomaia`
- GitHub repository: `RiskBands`
- Default branch currently in use: `master`

## Release Flow

The intended release path is:

1. run local and CI release validation
2. publish to TestPyPI
3. run post-upload smoke tests against TestPyPI
4. publish the approved version to PyPI

## Recommended Versioning Strategy

Recommended first rehearsal: keep the current stable version `1.0.0` for the
first controlled TestPyPI upload.

Why this is the recommended path:

- the repository is already internally consistent at `1.0.0`
- it avoids a churn-only version bump before the first rehearsal
- it allows the exact same tag to be promoted to PyPI if TestPyPI smoke tests pass

If the TestPyPI rehearsal exposes a defect:

- do not reuse `v1.0.0`
- fix forward to `1.0.1rc1` for the next rehearsal, or straight to `1.0.1` if the fixes are minimal and the release is immediately stable

## GitHub Environments

Create these GitHub environments in `Settings -> Environments`:

### `testpypi`

- Environment name: `testpypi`
- Recommended protection: optional reviewer approval
- Purpose: adds a manual checkpoint before any TestPyPI upload

### `pypi`

- Environment name: `pypi`
- Recommended protection: at least one required reviewer
- Purpose: protects the real release more strongly than TestPyPI

## Workflow Files

- `tests.yml`: regular test workflow
- `docs-deploy.yml`: docs site build and deploy
- `release-validation.yml`: build, `twine check`, selected pytest subset, smoke install via wheel, smoke install via sdist
- `publish-testpypi.yml`: trusted-publishing workflow for TestPyPI
- `publish-pypi.yml`: trusted-publishing workflow for PyPI

## Trusted Publisher Setup on TestPyPI

If `riskbands` already exists on TestPyPI:

1. Log in to TestPyPI.
2. Open the project page for `riskbands`.
3. Go to `Your account -> Publishing`.
4. Add a trusted publisher with these exact values:

- Project name: `riskbands`
- Owner: `joaaomaia`
- Repository name: `RiskBands`
- Workflow name: `publish-testpypi.yml`
- Environment name: `testpypi`

If `riskbands` does not yet exist on TestPyPI:

1. Log in to TestPyPI.
2. Open `Your account -> Publishing`.
3. Create a pending publisher with these exact values:

- Project name: `riskbands`
- Owner: `joaaomaia`
- Repository name: `RiskBands`
- Workflow name: `publish-testpypi.yml`
- Environment name: `testpypi`

## Trusted Publisher Setup on PyPI

If `riskbands` already exists on PyPI:

1. Log in to PyPI.
2. Open the project page for `riskbands`.
3. Go to `Your account -> Publishing`.
4. Add a trusted publisher with these exact values:

- Project name: `riskbands`
- Owner: `joaaomaia`
- Repository name: `RiskBands`
- Workflow name: `publish-pypi.yml`
- Environment name: `pypi`

If `riskbands` does not yet exist on PyPI:

1. Log in to PyPI.
2. Open `Your account -> Publishing`.
3. Create a pending publisher with these exact values:

- Project name: `riskbands`
- Owner: `joaaomaia`
- Repository name: `RiskBands`
- Workflow name: `publish-pypi.yml`
- Environment name: `pypi`

## Step-by-Step TestPyPI Rehearsal

This repository is currently prepared for the first controlled TestPyPI upload with:

- version: `1.0.0`
- tag: `v1.0.0`
- workflow: `publish-testpypi.yml`

### 1. Review the repository state

Confirm:

- `pyproject.toml` version is `1.0.0`
- `riskbands.__version__` resolves to `1.0.0`
- `release-validation.yml` is green

### 2. Create the release commit and tag

```bash
git add .
git commit -m "release: prepare 1.0.0"
git tag v1.0.0
```

### 3. Push the branch and tag

```bash
git push origin master
git push origin v1.0.0
```

### 4. Dispatch the TestPyPI workflow

1. Open `Actions -> publish-testpypi`
2. Click `Run workflow`
3. Select the tag ref `v1.0.0`
4. Confirm the environment approval if GitHub asks for it

The workflow refuses to run unless:

- the selected ref is a git tag
- the tag matches `v<pyproject version>`

## Post-TestPyPI Smoke Tests

Base install smoke:

```bash
python -m venv .venv-testpypi
source .venv-testpypi/bin/activate
python -m pip install --upgrade pip
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==1.0.0
python scripts/smoke_test_installed_package.py --expected-version 1.0.0
```

Base install smoke on Windows PowerShell:

```powershell
python -m venv .venv-testpypi
.\.venv-testpypi\Scripts\python.exe -m pip install --upgrade pip
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ riskbands==1.0.0
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 1.0.0
```

Optional Plotly benchmark smoke:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[viz]==1.0.0"
python scripts/smoke_test_installed_package.py --expected-version 1.0.0 --check-viz
```

Optional Plotly benchmark smoke on Windows PowerShell:

```powershell
.\.venv-testpypi\Scripts\python.exe -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "riskbands[viz]==1.0.0"
.\.venv-testpypi\Scripts\python.exe .\scripts\smoke_test_installed_package.py --expected-version 1.0.0 --check-viz
```

What this extra smoke validates:

- Plotly extra installation through `riskbands[viz]`
- benchmark plotting helpers import successfully
- HTML export through `export_figure_pack()` works in a clean environment

No Kaleido-based static export path was detected in the current repository, so the optional smoke focus is Plotly visualization plus HTML export.

## Promotion to PyPI

Promote only after TestPyPI smoke tests succeed.

If the TestPyPI rehearsal is clean and no code changes are required:

1. keep the same version `1.0.0`
2. keep the same tag `v1.0.0`
3. open `Actions -> publish-pypi`
4. run the workflow on `v1.0.0`

The PyPI workflow refuses to run unless:

- the selected ref is a git tag
- the tag matches `v<pyproject version>`
- the version is stable, such as `1.0.0` or `1.0.1`

## Failure Handling

If TestPyPI publication fails before any files are uploaded:

- fix the workflow or metadata issue
- keep the same version if the tag was not used

If TestPyPI publication succeeds but smoke tests fail:

- do not promote to PyPI
- prepare a new version such as `1.0.1rc1`
- repeat validation and TestPyPI publication

If PyPI publication succeeds but an issue is found immediately afterwards:

- yank the bad release on PyPI
- prepare the next fixed release instead of trying to overwrite artifacts

## Minimum Pre-Release Checklist

Before TestPyPI:

- trusted publisher configured on TestPyPI
- GitHub environment `testpypi` created
- `release-validation.yml` green
- package builds locally
- `twine check` passes
- wheel smoke install passes
- sdist smoke install passes

Before PyPI:

- TestPyPI smoke tests green
- trusted publisher configured on PyPI
- GitHub environment `pypi` created
- TestPyPI artifact is the exact one you want to promote

## References

- Trusted publishing overview: https://docs.pypi.org/trusted-publishers/
- Existing project trusted publisher setup: https://docs.pypi.org/trusted-publishers/adding-a-publisher/
- Pending publisher setup: https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/
- Publishing from GitHub Actions: https://docs.pypi.org/trusted-publishers/using-a-publisher/
- Trusted publisher troubleshooting: https://docs.pypi.org/trusted-publishers/troubleshooting/

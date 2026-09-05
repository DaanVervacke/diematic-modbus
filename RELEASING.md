# Releasing

The package version comes from the git tag through hatch-vcs. There is no version string to bump by hand. Release notes are drafted automatically by Release Drafter from merged pull request labels.

## One-time setup

Do these once before the first release.

1. Create a PyPI pending publisher at https://pypi.org/manage/account/publishing/ with these exact values:
   - PyPI project name: `diematic-modbus`
   - Owner: `DaanVervacke`
   - Repository name: `diematic-modbus`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
2. In the GitHub repository settings, create an environment named `pypi`. Add a required reviewer or a branch restriction if you want a manual gate before every publish.

No API token is stored anywhere. Publishing authenticates through OIDC trusted publishing.

## Cutting a release

1. Merge pull requests into `main`, each carrying exactly one release label (breaking-change, new-feature, enhancement, bugfix, maintenance, documentation, dependencies). The Verify PR Label check enforces this.
2. Release Drafter keeps a draft GitHub Release up to date, grouping the merged changes and resolving the next version from the labels.
3. When ready, open the draft in the Releases page, confirm the resolved version tag looks right, and publish it. Publishing creates the tag and triggers the Release workflow.
4. The Release workflow runs the full gate, builds from the tag, guards that the built version matches the tag, and publishes to PyPI through the `pypi` environment.
5. Confirm the new version on https://pypi.org/project/diematic-modbus/ and with a fresh install.

## Rebuilding an existing tag

If a publish fails after the tag exists, rerun the Release workflow manually from the Actions tab with the tag as input. The publish step uses skip-existing, so a version already on PyPI is left untouched.

## Version scheme

Tags are `vMAJOR.MINOR.PATCH`. hatch-vcs strips the leading `v` to produce the PEP 440 version. Release Drafter resolves the bump from labels: breaking-change bumps major, new-feature bumps minor, everything else bumps patch.

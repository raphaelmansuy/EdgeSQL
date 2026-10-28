# Publishing EdgeSQL

This note lists the steps to publish a release. Do them in order.

## One time setup

1. Create the PyPI project. Register a trusted publisher for
   `raphaelmansuy/EdgeSQL`, workflow `publish.yml`, environment `pypi`.
   Do the same on TestPyPI if you want a rehearsal.
2. In the GitHub repository, open Settings, Environments, and create an
   environment named `pypi`. Add a required reviewer if you want a manual gate.
3. In Settings, Pages, set the source to **GitHub Actions**. The
   `.github/workflows/pages.yml` workflow then publishes `docs/` on each push to
   `main`.

No API token is necessary in CI. The publish workflow uses OpenID Connect.

## For a manual upload from your machine

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-...        # a project scoped token

make release-check                    # build, then check the metadata
make publish-test                     # optional rehearsal on TestPyPI
make publish
```

## Release steps

1. Update the version in `pyproject.toml`. It appears once.
2. Move the entries in `CHANGELOG.md` from `Unreleased` to the new version and
   add the date.
3. Run the checks.

   ```bash
   make check          # lint, formatting, and every test
   make release-check  # build and validate the metadata
   ```

4. Commit, then push.
5. In GitHub, create a release with a tag such as `v0.1.0`. The `Publish to PyPI`
   workflow builds, tests, and uploads. It refuses to upload when a test fails.
6. Confirm the page at <https://pypi.org/project/edgesql/>.

## What the build includes

- `edgesql` and `edgesql.dialects`, with `py.typed`
- `LICENSE` and `NOTICE` under `dist-info/licenses`
- `README.md` as the long description

The example app, the tests, and the site stay out of the wheel. They live in the
repository.

## If a release is wrong

PyPI does not allow a second upload of the same version. Delete the release from
GitHub, bump the version, and publish again. A yanked release stays visible and
is not installed by default.

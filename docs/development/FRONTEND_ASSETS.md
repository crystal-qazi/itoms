# Frontend asset policy

ITOMS serves Bootstrap locally to support the private/offline-first deployment. Production pages must not depend on public CDNs.

## Pinned vendor distribution

- Product: Bootstrap
- Version: 5.3.9
- Source: https://github.com/twbs/bootstrap/tree/v5.3.9
- Release: https://github.com/twbs/bootstrap/releases/tag/v5.3.9
- License: MIT; the upstream license is retained alongside the vendored distribution at `itoms/static/vendor/bootstrap/LICENSE`.

Files loaded by `itoms/templates/base.html`:

- `itoms/static/vendor/bootstrap/css/bootstrap.min.css`
- `itoms/static/vendor/bootstrap/js/bootstrap.bundle.min.js`

The JavaScript bundle includes the required Popper functionality. Keep the version pinned; upgrades must update both files and this record together, review upstream release notes, and run the full UI and accessibility checks. Do not modify the minified vendor files locally.

The upstream Git blob object IDs for provenance are:

- CSS: `29eaf50d6b1b86255153d717eaa2261eec713d85`
- JS bundle: `c61e7766b0ef90d744e169c9d4ef226f65daf1be`
- MIT license: `d27a1619347bcd12c601fab403c918ff916397da`

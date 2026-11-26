# Frontend asset policy

The UI references locally hosted Bootstrap 5 CSS and bundle files under `itoms/static/vendor/bootstrap/`. Place the approved Bootstrap distribution at:

- `itoms/static/vendor/bootstrap/css/bootstrap.min.css`
- `itoms/static/vendor/bootstrap/js/bootstrap.bundle.min.js`

Do not load production UI assets from public CDNs. This supports the private/offline-first deployment and controlled outbound-access policy. Pin the Bootstrap version and record its source and checksum in the dependency inventory when the assets are vendored. No Bootstrap distribution files are committed in this foundation change.

# ITOMS PWA shell and cache policy

ITOMS exposes a root-scoped service worker and installable web-app manifest. The worker precaches only the approved static shell files: local Bootstrap CSS/JavaScript, application CSS/JavaScript, the manifest and the application icon.

The worker does not intercept or cache HTML navigations, authenticated pages, API responses, uploaded documents, notifications, reports, or any employee/incident data. POST and other non-GET requests are never cached. This is an intentional security boundary: offline access to sensitive records is not provided.

The application responses retain private/no-store cache headers. Only the explicit static allowlist is placed in the service-worker cache. When offline, the static shell may remain available to the browser, but server-backed workflows require the intranet connection.

When changing the shell asset list, update `itoms/static/sw.js`, test the cache allowlist and increment `CACHE_NAME` so clients discard the old shell. Do not add dynamic routes or data endpoints to the cache.

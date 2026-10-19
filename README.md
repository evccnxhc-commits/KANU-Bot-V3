# KANU Bot V3 — Web + Messenger (v3.5 UI update)

Independent project; keep separate from the older KANU/MangaDar deployment.

## Files / current GitHub layout
This package is intentionally flat to match the current repository layout: `app.py`, `index.html`, `style.css`, `app.js`, and Python modules live at the repository root. Flask is configured to serve root-level web assets as a compatibility measure. Do not upload `.env` or real secrets.

## Included
- Refined Arabic RTL responsive black/red interface.
- Web account registration/login/logout with hashed passwords and CSRF checks.
- New manga chapter panel; authenticated `/api/manga/download` route attempts to build and return a PDF using the existing `manga.py` adapter.
- Broader Arabic phrasing detection, including requests such as “هل تقدر ترسل لي فصول مانهوا نانو ميشل فصل 3”.
- Existing Messenger webhook and AI fallback chain are retained.
- A books/novels panel that passes the title to the existing book/AI handler.

## Important limitations
- Manga retrieval is only successful if the configured source is reachable and permits access. Mangawy may return HTTP 403; this package does not bypass site protections. A source-compatible adapter or permitted source is needed if that continues.
- The books panel is an entry point, not a complete Afedne crawler/PDF downloader. Do not claim a novel PDF was downloaded unless a real file is produced.
- Messenger delivery is separate from the web PDF download. Test it independently after deployment.
- SQLite stored on Render's ephemeral filesystem can be lost; configure persistent storage or a managed database before relying on account persistence.
- This has not been security-audited as a production identity service; no email verification, password reset, or comprehensive rate limiting.

## Required environment
Set a stable long random `SECRET_KEY` in Render. Keep existing `VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, `PAGE_ACCESS_TOKEN`, and AI provider keys in Render environment settings; never put secrets in GitHub.

## Deployment
Upload the package's contents to the root of `KANU-Bot-V3`, preserving this flat layout. Wait for Render deploy to complete.
- `/` should render HTML.
- `/health` should return JSON status.
- Sign up/login, then test the manga panel.
- A failed source request should show an error, not claim a PDF was produced.
- Test Messenger separately.

## Tests performed for this package
Python syntax checks, JavaScript syntax check (`node --check`), ZIP integrity, and chapter-request parsing examples were checked. Flask integration tests and live Render/Messenger/source tests were not run in this environment.

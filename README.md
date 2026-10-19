# KANU Bot V3 — v3.6 interface update

Independent KANU Bot V3 deployment. Keep it separate from the older KANU/MangaDar project.

## UI
- Chat homepage with a Telegram-inspired navigation and WhatsApp-like message bubbles.
- Dedicated `/manga` and `/novels` library pages with search, category filters, responsive title cards, and a grayscale TURBO DZ sponsor/team image in the footer.
- Homepage files are intentionally at repository root to match the current GitHub layout (`index.html`, `style.css`, `app.js`). Flask supports these root files and the nested library templates.

## Important limitations
The library entries are curated demonstration cards, not a live synchronized catalog. Their illustrated covers are CSS-generated placeholders, not official cover art. Manga chapter retrieval and Afedne book PDF download are not guaranteed; source access and rights determine availability. Mangawy HTTP 403 is not bypassed. Do not claim that a chapter/book has downloaded unless a real file was produced.
SQLite on Render's ephemeral filesystem may be lost on restart/rebuild; use persistent storage or a managed database for durable accounts.
No email verification, password reset, or comprehensive rate limiting is included.

## Keep secrets safe
Preserve Render environment variables privately: `SECRET_KEY`, `VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, `PAGE_ACCESS_TOKEN`, and provider API keys. Never commit actual values.

## Routes
- `/` home chat
- `/manga` manga library
- `/novels` novels/books library
- `/health` health check

## Validation
Python syntax and JavaScript syntax checks performed; ZIP integrity checked. Live Render, Messenger, AI provider, and source download tests have not been performed for this package.

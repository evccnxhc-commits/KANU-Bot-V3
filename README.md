# KANU Bot V3 — Complete Web + Messenger Starter

Independent project. Do not mix these files with the older KANU/MangaDar deployment.

## Included
- Arabic RTL responsive web interface (black/red theme) served by Flask at `/`.
- Registration/login/logout, hashed passwords, CSRF checks, and secure session-cookie defaults.
- `/api/chat` uses the existing `llm.py` provider fallback (Groq → Cerebras → OpenRouter → NVIDIA NIM).
- Existing Meta Messenger webhook and signature verification are retained.
- Existing manga chapter parser/PDF adapter and book intent handler are retained.
- `/health` endpoint for Render health checks.

## Honest feature boundaries
- Web accounts use SQLite on the service filesystem. On Render, local files can be lost on rebuild/restart unless a persistent disk or external database is configured. Do not assume account persistence on a free instance.
- Manga PDF retrieval depends on the source being reachable and allowing access; the source may return errors or change its HTML. The web chat does not claim to attach a chapter PDF.
- The book handler currently supports known routing/intent cases; it is not a universal book search or PDF downloader.
- No email verification, password reset, account deletion, or production-grade rate limiting is included. This is a starter deployment, not a fully audited production identity service.

## Required deployment environment
- `SECRET_KEY`: a long random secret. Render Blueprint can generate one using `render.yaml`.
- At least one AI key: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, or `NVIDIA_API_KEY`.
- For Messenger, preserve the existing `VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, and `PAGE_ACCESS_TOKEN` values in Render. Never commit these values to GitHub.

Optional environment variables are documented in `.env.example`. That file contains placeholders only.

## Render
`render.yaml` uses Python 3.12, `pip install -r requirements.txt`, `gunicorn app:app --workers 1 --threads 4 --timeout 60`, and health check `/health`.

After deployment, check:
1. `/` shows the KANU HTML interface, not JSON.
2. `/health` returns a small JSON status response.
3. Register/login and chat are tested with an AI provider key configured.
4. Test Messenger separately; a healthy web page does not prove Meta delivery works.

## Uploading on GitHub
Upload the **contents** of this archive into the repository root while preserving the folders `templates/` and `static/`. Do not upload only the ZIP file. `templates/index.html`, `static/style.css`, and `static/app.js` must keep these exact paths. Replace the old `app.py` with this archive's `app.py`. Keep any existing Render secrets unchanged. The old root-level `index.html` and `style.css` files are not used by Flask; do not rename them to replace the nested files.

## Local smoke check
Install dependencies from `requirements.txt`, set a test `SECRET_KEY`, set `COOKIE_SECURE=false` for plain local HTTP, and run `python app.py`. The site opens at `http://127.0.0.1:5000`.

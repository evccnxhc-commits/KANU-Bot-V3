# KANU Bot V3 — updated starter

Arabic-first Messenger bot starter. This update preserves manga chapter request handling and adds a book-request route, short per-sender in-memory AI context, a dialect-aware persona prompt, and a random dua footer on every outgoing text message.

## Included in this version
- Flask webhook for Meta Messenger.
- Webhook signature validation using `FACEBOOK_APP_SECRET`.
- AI provider fallback: Groq → Cerebras → OpenRouter → NVIDIA NIM.
- Arabic/English manga chapter request parsing remains available.
- Book request recognition for novels; the known Ikadoli page is returned as a link.
- Short in-memory conversation context per sender (lost when the process restarts; not persistent).
- Random short dua footer is appended centrally to every outgoing text response.

## Important implementation status
- Manga chapter downloading, page collection, PDF conversion, and attachment delivery are **not implemented yet**.
- Direct Afedne PDF downloading and attachment delivery are **not implemented yet**. The book module returns the known book page and does not guess undocumented download endpoints.
- Connect only authorized source adapters and test the actual site workflow before enabling file distribution.
- “Understands every dialect” cannot be guaranteed; the prompt asks the AI to understand varied dialects and ask when ambiguous.

## Setup
Python 3.12+ recommended.

```bash
pip install -r requirements.txt
python app.py
```

Set these environment variables in Render or your host dashboard; never commit secrets:
- `PAGE_ACCESS_TOKEN`
- `VERIFY_TOKEN`
- `FACEBOOK_APP_SECRET`
- At least one of `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`

Set `GRAPH_API_VERSION` only if needed. Keep signature verification enabled on public deployments.

## Free-tier note
The code has no paid SDK dependency, but hosting and AI providers' free quotas can change, sleep, rate-limit, or be unavailable. Zero cost cannot be guaranteed permanently.

## Deploy
Keep `gunicorn app:app` as the Render start command. After deploying, check `/health` and confirm Meta webhook verification. Do not expose API keys or access tokens in logs or chat.

# KANU Bot V3

An independent Arabic-first Messenger bot starter with multi-provider LLM fallback. This repository is separate from the older KANU/MangaDar deployment.

## Included
- Flask webhook for Meta Messenger (GET verification and POST events).
- Webhook signature validation using `FACEBOOK_APP_SECRET` (fail-closed by default).
- OpenAI-compatible fallback: Groq → Cerebras → OpenRouter → NVIDIA NIM.
- Basic Arabic/English manga chapter request parsing.
- Render blueprint and environment template.

## Not implemented yet
Manga chapter downloading, PDF conversion, and file delivery are **not implemented yet**. The manga module currently recognizes requests and explains that the source adapter is not connected. Add a source adapter only where access and reuse are authorized and permitted by the source's terms.

## Run locally
Python 3.12+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Health check: `http://127.0.0.1:5000/health`

Set real environment variables in your shell or deployment dashboard. Never commit `.env`, API keys, page tokens, or app secrets.

## Configure Meta Messenger
1. Configure a Meta app with Messenger and a Facebook Page.
2. Set `PAGE_ACCESS_TOKEN`, `VERIFY_TOKEN`, and `FACEBOOK_APP_SECRET` in the deployment environment.
3. Set callback URL to `https://YOUR-SERVICE.onrender.com/webhook`.
4. Subscribe the Page to the `messages` webhook field.
5. Keep signature verification enabled. Never set `ALLOW_UNSIGNED_WEBHOOKS=true` on a public service.

Meta may require app review, permissions, or tester roles depending on who will message the Page.

## Configure AI providers
Create a key with one or more providers and add it as an environment variable in Render. Free quotas, model names, and availability change; unlimited free requests are not guaranteed. The app skips common configuration/quota failures (401/403/404/429) and tries the next configured provider.

Suggested starting point: Groq, Cerebras, OpenRouter. Only configured keys are used. Never put keys in source files, issues, screenshots, or chat messages.

## Deploy to Render
1. Import this repository in Render.
2. Review the `render.yaml` blueprint.
3. Add secret environment variables in Render.
4. Deploy and open `/health`.
5. Configure the Meta webhook URL and verify token.

Render free services may sleep when idle, and free plans/limits can change.

## Security notes
- Never commit real credentials.
- Without `FACEBOOK_APP_SECRET`, webhook POSTs are rejected unless the unsafe local-test override is explicitly enabled.
- This starter still needs production testing.

## Roadmap
- [ ] Add tests and CI.
- [ ] Add privacy-limited persistent conversation history.
- [ ] Implement an authorized manga source adapter.
- [ ] Add chapter page downloading, PDF conversion, file-size checks, and Messenger attachment delivery.
- [ ] Add provider health metrics and configurable model selection.

# KANU Bot V3 — chapter retrieval and dua formatting update

## Changes
- Appends a random, lightly decorated short dua to outgoing text messages without the word "دعاء", e.g. `✨ اللهم ارزقنا راحة البال وطمأنينة القلب. ❤️`.
- Adds an initial HTML-based chapter adapter: discovers chapter links from a configured series page, looks for chapter image URLs, downloads images within configured limits, builds a PDF, and sends it through Messenger's file-attachment API.
- Keeps AI fallback and book request routing.
- User-facing chapter responses do not mention the source site.

## Manga source configuration
The initial built-in series mapping supports Nano Machine / نانو ميشل aliases pointing at the known series page. Add further permitted series pages using the Render environment variable `MANGA_SERIES_JSON`, as a JSON object mapping aliases to series-page URLs, for example:
`{"series alias":"https://example.org/series/example"}`

The adapter depends on the source's HTML exposing chapter links and reader images. Sites may use JavaScript or anti-bot protection; in that case it will fail gracefully and needs a source-specific adapter. This package has not been tested against the live source in this environment. Verify source permission/terms and test with one chapter before broad deployment.

## Messenger delivery
Requires `PAGE_ACCESS_TOKEN`, `VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, and at least one AI provider key. Check current Meta attachment requirements and limits for the app/page. Temporary PDFs are deleted after the send attempt.

## Security and cost
Never commit secrets. Free hosting/API quotas and source availability can change. Do not enable unsigned webhooks in production.

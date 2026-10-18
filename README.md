# KANU Bot V3 — intent and context fix

This update improves recognition of book requests and short follow-ups, broadens Arabic chapter phrasing, keeps the manga feature, and removes source-site names from user-facing manga status messages.

## Important status
- Manga downloader, PDF conversion, and attachment delivery still require implementation.
- Afedne book search and direct PDF delivery are not implemented; known Ikadoli page is available, and Arss is handled honestly without inventing a URL.
- Conversation context is in-memory and will reset when the process restarts.
- Random dua footer is appended to every outgoing text response.
- Free tiers have quotas and availability limits; permanent zero-cost service is not guaranteed.

## Required environment variables
`PAGE_ACCESS_TOKEN`, `VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, and at least one AI provider key.

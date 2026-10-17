"""OpenAI-compatible multi-provider fallback for KANU V3."""
import logging
import os
import requests

log = logging.getLogger(__name__)
TIMEOUT = (5, 25)
SYSTEM_PROMPT = (
    "أنت KANU، مساعد عربي ودود ومختصر. أجب باللغة التي يستخدمها الشخص، "
    "ولا تدّعِ أنك نفذت شيئًا لم تنفذه. إذا لم تعرف الإجابة فقل ذلك بوضوح."
)

def _providers():
    return [
        {"name": "Groq", "key": os.getenv("GROQ_API_KEY"),
         "url": "https://api.groq.com/openai/v1/chat/completions",
         "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")},
        {"name": "Cerebras", "key": os.getenv("CEREBRAS_API_KEY"),
         "url": "https://api.cerebras.ai/v1/chat/completions",
         "model": os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")},
        {"name": "OpenRouter", "key": os.getenv("OPENROUTER_API_KEY"),
         "url": "https://openrouter.ai/api/v1/chat/completions",
         "model": os.getenv("OPENROUTER_MODEL", "openrouter/free")},
        {"name": "NVIDIA NIM", "key": os.getenv("NVIDIA_API_KEY"),
         "url": "https://integrate.api.nvidia.com/v1/chat/completions",
         "model": os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")},
    ]

def answer_with_fallback(user_text, sender_id=None):
    configured = [p for p in _providers() if p["key"]]
    if not configured:
        return ("أهلًا! أنا KANU 🤍 لم يتم إعداد مفاتيح الذكاء الاصطناعي بعد. "
                "أضف مفتاح مزوّد واحد على الأقل في إعدادات البيئة، ثم جرّب مجددًا.")
    for provider in configured:
        try:
            headers = {"Authorization": f"Bearer {provider['key']}",
                       "Content-Type": "application/json"}
            if provider["name"] == "OpenRouter":
                headers.update({"HTTP-Referer": "https://github.com/evccnxhc-commits/KANU-Bot-V3",
                                "X-Title": "KANU Bot V3"})
            response = requests.post(
                provider["url"], headers=headers,
                json={"model": provider["model"],
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": user_text}],
                      "temperature": 0.7, "max_tokens": 700},
                timeout=TIMEOUT)
            if response.status_code in (401, 403, 404, 429):
                log.warning("%s returned HTTP %s; trying next provider",
                            provider["name"], response.status_code)
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, str) and content.strip():
                return content.strip()
            log.warning("%s returned an empty response", provider["name"])
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            log.exception("Provider %s failed; trying next provider", provider["name"])
        except Exception:
            log.exception("Unexpected provider failure: %s", provider["name"])
    return "تعذّر الحصول على رد من مزوّدي الذكاء الاصطناعي حاليًا. حاول مرة أخرى بعد قليل."

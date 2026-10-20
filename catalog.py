"""Library catalog loader.

Entries come from data/manga.json and data/novels.json. Only entries the owner has
configured are shown. Entries marked "demo": true are hidden unless
KANU_SHOW_DEMO=true, and are then badged as demonstration items.
"""
import json
import os
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
KINDS = {"manga": "manga.json", "novels": "novels.json"}


def _load(kind):
    path = DATA_DIR / KINDS[kind]
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return items if isinstance(items, list) else []


def show_demo():
    return os.getenv("KANU_SHOW_DEMO", "false").lower() == "true"


def get_items(kind):
    items = [i for i in _load(kind) if isinstance(i, dict) and re.fullmatch(r"[a-z0-9-]{2,60}", str(i.get("slug", "")))]
    if not show_demo():
        items = [i for i in items if not i.get("demo")]
    return items


def get_item(kind, slug):
    return next((i for i in get_items(kind) if i["slug"] == slug), None)


def categories(items):
    seen = []
    for item in items:
        for c in item.get("categories", []):
            if c not in seen:
                seen.append(c)
    return seen

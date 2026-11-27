"""Seed phrases per factor.

Kept as PHRASES on purpose: E5 encodes a whole phrase as one vector,
unlike FastText which only had single-token vectors.

IMPORTANT: seed sets are DISJOINT. A seed shared by two factors makes both
scores fire on the same text (the old "בלעדי" was in clickbait AND fomo —
that overlap made the clickbait factor look broken). Each factor owns its
seeds only.

THE ENGLISH SEEDS (M2) are PHRASES, never single words: a literal word like
"secret" is ambiguous (it is also a normal noun), and the seed floor must
never fire on an innocent word. The model is multilingual, so an English
phrase works on an English headline and scores low against a Hebrew one —
the Hebrew rulers do not move.

The authoritative seed lists live in config/seeds.json. This module loads
them from that file, falling back to the hardcoded lists below if the file
is missing or malformed. A super-admin with file access edits
config/seeds.json directly; regular admins can preview seed tweaks through
the admin UI and submit them as tuning suggestions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from api.lib.paths import FUD_FOMO_ROOT as ROOT, CONFIG_DIR# noqa: E402

SEEDS_FILE = CONFIG_DIR / "seeds.json"


def _hardcoded_seeds() -> dict[str, list[str]]:
    """Hardcoded fallback seed lists (identical to config/seeds.json)."""
    return {
        "clickbait": [
            "דרמטי", "שערוריה", "תדהמה", "נחשף",
            "לא תאמינו", "זה מה שקרה", "מה שאף אחד לא רוצה שתדע",
            "כך תירדו מהסוד", "הסיבה האמיתית מאחורי",
            "you won't believe", "you'll never believe", "you won't believe what happened",
            "what nobody tells you", "the real reason why",
            "this one trick", "the truth about", "here's what happened",
            "the secret behind", "the reason why", "what they don't want you to know",
            "the surprising truth", "one simple trick", "the hidden reason",
            "doctors hate him", "doctors hate her", "doctors hate them",
            "shocking", "shocking truth", "shocking details",
            "click here to see what happens",
            "shocking celebrity caught",
            "the truth about vaccinations",
        ],
        "fud": [
            "משבר", "איום", "סכנה", "מזעזע", "מזעזעת", "הותקף", "הותקפה",
            "קטסטרופה", "פחד", "מוות", "אימה",
            "הסלמה", "קיצון",
            "חריג",           # exceptional / unusual → FUD (fear)
            "נחרץ",           # determined / decisive → FUD (+FOMO per operator)
            "נחרצת",          # feminine form of נחרץ → FUD (+FOMO per operator)
            "מתריס",          # defiant / challenging → FUD (fear)
            "מכה קשה",        # severe blow → FUD (fear)
            "החריף",          # harsh / severe → FUD (fear)
            "תרחיש אימים",
            "השלכות הרסניות", "אי ודאות",
            "עבריין", "עבריינים",   # criminals / crime syndicate → FUD (fear)
            "a deadly danger", "a terrifying threat", "a catastrophic crisis",
            "the alarming truth", "a looming crisis", "the hidden danger",
            "terrifying consequences", "a deadly warning", "anxiety and panic",
            "the shocking danger", "an imminent threat",
            "orgy", "orgies",
            "catastrophic", "scandal", "brutal", "bloodbath", "bomb", "threat", "disruption",
            "showdown", "reportedly", "rumor", "rumors", "execution", "inmate",
            "sex crimes",
        ],
        "fomo": [
            "לזמן מוגבל", "אל תפספסו", "נדיר", "בלעדי", "רק היום",
            "הזדמנות שלא תחזור", "אסור לפספס", "מדהים",
            "מטורף", "מטורפים", "מטורפת", "מטורפות",
            "מרהיב", "מרהיבה", "מרהיבים", "מרהיבות",
            "בשכונה הזאת", "במי יבחרו",
            "ויראלי", "viral",
            "חריג",           # exceptional / unusual → FOMO
            "נחרץ",           # determined / decisive → FOMO (+FUD per operator)
            "נחרצת",          # feminine form of נחרץ → FOMO (+FUD per operator)
            "limited time only", "don't miss out", "last chance to",
            "only today", "selling fast", "before it's gone",
            "one time offer", "final hours", "hurry limited", "while stocks last",
            "historic", "massive", "stunning", "major",
        ],
        "violence": [
            "רצח", "הרג", "הרוג", "הריג", "קטל", "טבח", "מטהר", "טרור", "פיגוע",
            "תקפ", "תקיפ", "חטיפ", "אלימ", "ירי", "ריסוא", "ריסוי",
            "מלחמ", "לחימ", "דקיר", "חנית",
            "kill", "killer", "murder", "shoot", "shooting", "shot", "attack", "terror",
            "bomb", "rape", "violence", "violent", "wars", "assault", "stab",
            "massacre", "torture", "execution", "sex crimes",
        ],
        "attack": [
            "טיפש", "בור", "מקבלן", "נבלה", "שוטה", "זונה", "שרלטן", "נוכל",
            "רמאי", "בוגד", "פיגל", "רשע", "מתועב", "מכוער",
            "idiot", "idiots", "moron", "fool", "foolish", "stupid", "liar", "liars",
            "bastard", "scumbag", "slime", "cretin", "coward", "disgrace", "jerk",
            "traitor", "charlatan", "swine", "worthless", "clown", "lousy",
        ],
        "profanity": [
            "זיין", "פאק", "מנאק", "ערס", "חמס",
            "קיצור גנאי", "גידוף לשון", "שפה בערה", "מילה גסה",
            "a vulgar insult", "a swear word", "profane language",
            "a dirty mouth", "an obscene slur", "foul language",
        ],
        "fear": [
            "טראומה", "חרדה", "מסוכן",
            "fear", "terrifying", "dread", "horror", "traumatic",
            "panic", "menacing", "stalker", "stalking",
            "raped", "kidnap", "abduction",
        ],
    }


def load_seeds() -> dict[str, list[str]]:
    """Load seed phrases from config/seeds.json, falling back to hardcoded.

    Returns a dict mapping factor name -> list of seed phrases.
    Never raises: a broken JSON file keeps the hardcoded values.
    """
    try:
        if SEEDS_FILE.exists():
            data = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out: dict[str, list[str]] = {}
                for factor, plist in data.items():
                    if isinstance(plist, list):
                        out[factor] = [str(s) for s in plist if str(s).strip()]
                if out:
                    return out
    except (OSError, ValueError, json.JSONDecodeError):  # noqa: BLE001
        pass
    return _hardcoded_seeds()


def load_scan_mode() -> str:
    """Load the scan mode from config/seeds.json.

    "immediate" = scan synchronously on the homepage (default).
    "queue" = enqueue and show a position indicator.
    Never raises: falls back to "immediate".
    """
    try:
        if SEEDS_FILE.exists():
            data = json.loads(SEEDS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                mode = str(data.get("scan_mode", "immediate")).strip().lower()
                if mode in ("immediate", "queue"):
                    return mode
    except (OSError, ValueError, json.JSONDecodeError):  # noqa: BLE001
        pass
    return "immediate"


# Loaded at import time. A super-admin editing config/seeds.json must
# restart the service for changes to take effect.
_CATEGORIES = load_seeds()
SCAN_MODE = load_scan_mode()

CLICKBAIT_SEEDS = _CATEGORIES.get("clickbait", [])
FUD_SEEDS = _CATEGORIES.get("fud", [])
FOMO_SEEDS = _CATEGORIES.get("fomo", [])
VIOLENCE_SEEDS = _CATEGORIES.get("violence", [])
ATTACK_SEEDS = _CATEGORIES.get("attack", [])
PROFANITY_SEEDS = _CATEGORIES.get("profanity", [])
FEAR_SEEDS = _CATEGORIES.get("fear", [])

CATEGORIES = {
    "clickbait": CLICKBAIT_SEEDS,
    "fud": FUD_SEEDS,
    "fomo": FOMO_SEEDS,
    "violence": VIOLENCE_SEEDS,
    "attack": ATTACK_SEEDS,
    "profanity": PROFANITY_SEEDS,
    "fear": FEAR_SEEDS,
}


def reload_seeds() -> dict[str, list[str]]:
    """Re-load seeds from config/seeds.json (for testing / hot-reload)."""
    global _CATEGORIES, CLICKBAIT_SEEDS, FUD_SEEDS, FOMO_SEEDS
    global VIOLENCE_SEEDS, ATTACK_SEEDS, PROFANITY_SEEDS, FEAR_SEEDS, CATEGORIES
    global SCAN_MODE
    _CATEGORIES = load_seeds()
    SCAN_MODE = load_scan_mode()
    CLICKBAIT_SEEDS = _CATEGORIES.get("clickbait", [])
    FUD_SEEDS = _CATEGORIES.get("fud", [])
    FOMO_SEEDS = _CATEGORIES.get("fomo", [])
    VIOLENCE_SEEDS = _CATEGORIES.get("violence", [])
    ATTACK_SEEDS = _CATEGORIES.get("attack", [])
    PROFANITY_SEEDS = _CATEGORIES.get("profanity", [])
    FEAR_SEEDS = _CATEGORIES.get("fear", [])
    CATEGORIES = {
        "clickbait": CLICKBAIT_SEEDS,
        "fud": FUD_SEEDS,
        "fomo": FOMO_SEEDS,
        "violence": VIOLENCE_SEEDS,
        "attack": ATTACK_SEEDS,
        "profanity": PROFANITY_SEEDS,
        "fear": FEAR_SEEDS,
    }
    return _CATEGORIES

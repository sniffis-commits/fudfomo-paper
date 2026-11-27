"""Eval: score eval/headlines_he.csv, print per-row + confusion vs labels.

Usage: python eval/run_eval.py
Tune lib/score.py:_MATCH_THRESHOLD, _COS_FLOOR/CEIL based on output.
"""
import csv, sys
import os
from pathlib import Path

# Project root, layout-independent: FUD_FOMO_ROOT env var wins; else walk up
# from this file looking for config/seeds.json.
def _find_root() -> Path:
    env = os.environ.get("FUD_FOMO_ROOT", "").strip()
    if env:
        return Path(env)
    p = Path(__file__).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "api" / "config" / "seeds.json").exists():
            return p
        p = p.parent
    return Path.cwd()

ROOT = _find_root()
sys.path.insert(0, str(ROOT))
from api.lib import assess_text

MAP = {"low": 0, "moderate": 1, "high": 2}

def main():
    rows = list(csv.DictReader(open(ROOT / "eval" / "headlines_he.csv", encoding="utf-8")))
    correct = {"clickbait": 0, "fud": 0, "fomo": 0}
    for r in rows:
        res = assess_text(r["text"])
        line = f"TEXT: {r['text'][:60]}"
        for cat in ("clickbait", "fomo", "fud"):
            pred = res["labels"][cat].lower()
            gold = r[cat]
            ok = "OK " if abs(MAP[pred] - MAP[gold]) <= 0 else "MISS"
            if ok == "OK ":
                correct[cat] += 1
            line += f" | {cat}:{res[cat]}:{pred}(gold:{gold}){ok}"
        print(line)
    n = len(rows)
    print(f"\nAccuracy exact: " + ", ".join(f"{c}={correct[c]}/{n}" for c in correct))
    print("Tune thresholds in lib/score.py if MISS rate high.")

if __name__ == "__main__":
    main()

# Why scores collapse to Moderate — diagnosis + calibration plan

## Evidence (measured, not guessed)
- `shrink_sentence_model_e5.py` sanity: `cos(query:אל תפספסו את ההזדמנות, passage:אל תפספסו)=0.896`
  vs `cos(..., passage:עגבניה)=0.803`. Margin only 0.09, floor very high (~0.80).
- CLI: sensational `56.3/51.5/54.1`, neutral weather `55.7/50.8/51.2` — delta < 2 pts.
- Eval `eval/run_eval.py`: clickbait 1/10, fud 3/10, fomo 3/10 exact-match. Nearly every
  prediction lands Moderate.

## Root causes
1. **Anisotropy (main).** BERT-family sentence vectors live in a narrow cone: random Hebrew
   pairs score ~0.75-0.85, related pairs ~0.88-0.95. Absolute cosine is not a 0-1 signal.
   Global map in `api/lib/score.py` (`_COS_FLOOR=0.70, _COS_CEIL=0.95`) puts the entire
   operating range into 40-70/100 = Moderate.
2. **Single global floor/ceiling.** Each category has a different baseline: `fud` seeds
   (פחד/סכנה) sit closer to generic news than `fomo` phrases (לזמן מוגבל). One shared
   0.70-0.95 compresses them identically.
3. **Document-level max only.** `assess_text` encodes the whole article as one query and
   takes `max(seed cos)`. Long neutral articles contain one vaguely urgent sentence that
   spikes max; short sensational ones get diluted by boilerplate. No contrastive term.
4. **Match threshold conflated with score.** `_MATCH_THRESHOLD=0.82` reports matches for
   almost every input (neutral weather matched נחשף/סכנה/נדיר), which misleads users
   even if the numeric score were fixed.

## Calibration principle
Do not interpret raw cosine. Interpret **position of this text's cosine inside the
category's own background distribution**:
`score = (cos - p5_cat) / (p95_cat - p5_cat)`, per category, from a background corpus
(neutral news + eval set). Alternatives considered and rejected:
- Fixed 0.7 cutoff (old FastText habit): meaningless for E5; everything passes.
- Mean-pooling phrases or translating seeds: treats symptom, keeps global floor.
- Retraining/fine-tuning E5 now: overkill before linear calibration is tried.

## Procedure (to be executed after approval)
1. Build background: `eval/headlines_he.csv` (10 gold) + ~30 neutral Hebrew sentences
   (news/weather/history). Encode each as `query:`, seeds as `passage:` via `api/lib/embed.py`.
2. Per category, record max-cos distribution; take `p5`/`p95` as floor/ceil. Expect e.g.
   fud floor ~0.81, fomo floor ~0.78 — different per category.
3. Score = clipped linear map above; add small margin bonus:
   `score += 10 * clip(best - mean_top3_other_cats, 0, 0.1) / 0.1` so a text spiking one
   category outranks a text mildly matching all three (fixes neutral-weather case).
4. Set Low/Moderate/High cuts from gold tertiles on eval, not 33/66. Report per-category
   accuracy + confusion; accept if exact-match ≥ 6/10 and no neutral scores High.
5. Separate concerns: `matches` threshold becomes per-category `p75` (report-only),
   numeric score uses `p5/p95` (ranking). Document final numbers in this file.

## Current numbers (measured 2026-10-20, after the evidence gate + the seed floor)

Rulers live in `api/lib/score.py:_CALIB` (per-factor ruler) and `_MATCH_T`
(p50, report-only). Measured with `python tools/measure_calibration.py`:

| factor | corpus | ruler | match_t | note |
|---|---|---|---|---|
| clickbait | eval/headlines_he.csv | 0.830–0.861 | 0.854 | + the linguistic layer |
| fud | eval/headlines_he.csv | 0.840–0.876 | 0.835 | the floor kills the FOMO headlines |
| fomo | eval/headlines_he.csv | 0.850–0.889 | 0.832 | the seeds sit high on neutral Hebrew |
| violence | eval/violence_probes.csv | **0.850–0.863** | 0.845 | sharp: the word list carries it |
| attack | eval/attack_probes.csv | **0.845–0.853** | 0.840 | sharp |
| profanity | eval/profanity_probes.csv | **0.845–0.855** | 0.840 | sharp |

Gold set (50 rows, `eval/headlines_he.csv`): **clickbait 50/50, fomo 49/50,
fud 50/50, violence 50/50, attack 50/50, profanity 50/50** exact-match.
Delta check: clickbait 80.0, fud 100.0, fomo 69.7, violence 80.0, attack 75.0,
profanity 50.0 — all OK (the FOMO delta went from 19.2 WEAK to 69.7).

**These numbers are optimistic and must be read as such.** The rulers, the
floors and the seed lists were tuned *on this same 50-row set*. 50 rows with
12–20 positives per factor is a development set, not a test set. A held-out
set (another 50 rows, labelled the same way, never looked at while tuning) is
the next honest measurement — until then, treat "50/50" as "the known
failures are fixed", not as "the model is 100%".

### The two rules that did the heavy lifting (2026-10-20)

**1. No evidence → no score.** The doc-max is a *background artifact*: E5
gives ~0.84 to almost any Hebrew text, so a text with no matched seed was
still getting 36–57/100 from a similarity that means nothing. The five
clickbait false alarms had **zero matched seeds** — the number was real, the
evidence was not. Now a semantic factor with no seed above its match
threshold, no linguistic rule and no literal seed scores **0** and says so
("no evidence: the best cosine stayed at the background level").

**2. A literal seed floors the factor.** If the text literally contains a
seed phrase, that is direct evidence and the factor cannot be near zero:
`משבר` → FUD ≥ 72, `רק היום` → FOMO ≥ 72, `זה מה שקרה` → clickbait ≥ 66.
The floor applies only to *unambiguous* seeds: a multi-word seed always
qualifies, a single word only when it has one clear sense — `בלעדי` is also
"unique" and `נדיר` is also "rare", so neither floors the FOMO.

Both rules are **floors, not ceilings**: a stronger signal still wins, and a
clean headline still scores 0.

### The labelling rules of the gold set

The full guide is **`docs/labeling.md`** (how a headline gets its six labels,
the tie-breakers, the annotator protocol). The three rules that decide the
hard cases:

1. **The factors are disjoint.** A scarcity headline ("בלעדי! אל תפספסו…")
   is FOMO, not clickbait — it has no curiosity gap, so the clickbait is Low
   even though the words are dramatic.
2. **The canonical phrases are High.** A headline that opens with a
   textbook clickbait phrase ("זה מה שקרה…") is High clickbait, like the
   other canonical openers in the set.
3. **The factor measures the WORDING, not the topic.** "טבח קטסטרופה באזור
   מגורש" is a violence story, but "קטסטרופה" is fear *wording* → High FUD,
   like the other explicit fear words ("משבר", "סכנה").

### The lexical context rules

Two word lists are polysemous in news, and the context decides:

| word | the wrong reading | the right reading | the rule |
|---|---|---|---|
| שוטה | "a jerk" | "a police officer" | a casualty word after it → a report, not an insult ("שוטה נהרג") |
| תקף | "he assaulted" | "he lashed out at" | an idea/policy after it → a verbal attack, not violence ("תקף את המחאה") |

And the shoot verb (`ירה`/`נורה`) is a different root from the noun `ירי`,
so it needed its own patterns: "חייל נורה בגבול" is now High violence. The
passive (`שנורה`) is not covered yet — a documented gap, not an oversight.

### Why the lexical factors are not embedding-led
The doc-max of a *neutral* sentence reaches 0.836 and sensational-but-not-violent
text reaches 0.850 — the same band as violent text (0.818–0.861). A p5/p95
ruler over that distribution cannot separate them, so violence/attack/profanity
lean on explicit word lists (`api/lib/lexicon.py`) and keep the embedding as a
sharp bonus only. Neutral rows score 0.0.

**A p5/p95 ruler over a mixed corpus does NOT work** for the semantic
factors: with 30 rows the p5 lands in the noise and the neutral rows drift
into Moderate/High (measured: fud 19/20 → 11/20). The rulers above are the
validated ones — background level → 0, strong level → 100.

### The clickbait ablation (where the signal comes from)

Measured on the 50-row gold set (11 clickbait positives):

| variant | catches | false alarms | what it is |
|---|---|---|---|
| **rules only** | **4/11** | **0** | the model-free language layer (`python tools/measure_rules_only.py`) |
| embedding seeds only | 6/7 (old set) | 4–6 | the OLD formula (no rules) |
| full (evidence gate + seed floor + rules) | **11/11** | **0** | what ships |

The rules are the *precise* half (0 false alarms) and the seeds are the
*sensitive* half — they also fire on alarming-but-informative headlines,
which is what the evidence gate now removes. That is why the browser
extension (T1) ships the rules only: a badge on every page must never cry
wolf.

### The Hebrew BERT layer — measured, and kept OFF

`dicta-il/dictabert-tiny-parse` (4 layers, 45M params, exported to a 45 MB int8
ONNX by `tools/export_dictabert.py`) parses the headline: Hebrew NER (PER /
ORG / LOC / GPE / TIMEX) + the informal register, in ~50 ms.

**Result (`tools/ab_hebrew_bert.py`): NEUTRAL.** On the gold set it changes no
clickbait label and no false alarm (25/30, 4 false alarms — with and without).
A "veto on concrete headlines" was tried and **removed**: the assumption
("a headline that names someone is not clickbait") is false — "עכשיו הכול ברור:
זו הסיבה שבני גנץ פרש דווקא עכשיו" names a person *and* is textbook
clickbait.

So it ships **off** (`FUDFOMO_HEBREW_BERT=0` by default) and is kept for:
- the evidence panel (the admin can show *what* the headline names),
- being the right **encoder** for a future fine-tuned "missing bottom line"
  classifier — that needs labelled headlines, which we do not have yet,
- the small Hebrew model the browser extension wants (T3').

### The lexical matcher — the false positives that were found and fixed
The word-list matcher originally used a loose "subsequence" rule (the root's
letters in order, one extra letter allowed). It was added for the infix ו
(`רוצח` = ר+ו+צ+ח) and it over-fired badly. Measured on a real cached page
(ynet, scan #56): violence/attack/profanity all scored **100**.

| matched | the actual word | now |
|---|---|---|
| `בור` | **עבור** ("because"), **ברור** ("clear") | blocked (not a prefix+suffix form) |
| `בור` | **סבור** ("concerned") | blocked ("ס" is not a prefix) |
| `ירי` | **מכירים** ("we know") | blocked |
| `פוק` | **פודקאסטים** ("podcasts") | the word is gone from the list |
| `זין` | **לזינוק** ("to wiggle") | blocked ("וק" is not a suffix) |
| `קטל` | **קטלנית** (a boxer's nickname) | blocked (collision list) |
| `טרור` | **בטרור** ("in the ring") | blocked (collision list) |
| `מטבח`/`מקטל`/`מזיין`/`מיאב` | the prefix created a match | blocked (collision list) |
| `זונה` | **מזון** ("food"), **מזונות**, **מזוני**, **המזון** | a root variant is a plural marker, never a word + the family is excluded |
| `נבל` | **נבל** (a snare drum) | the root is "נבלה" (the insult); the bare form is blocked |
| `רמאי` | **ברמא** ("in vain") | blocked (collision list); "הרמא" still hits |

The rules now: the root must **start** the token (after ≤2 prefixes), what
follows must be a **real Hebrew suffix** (`ו/י/יה/ת/ות/ית/ה/הם/ים/ן/נית/יות…`),
one infix ו is allowed, the final letters are folded (זיין ~ זיינו), a root
**variant** (the plural form) needs a real suffix after it, and a small
collision list blocks the ordinary words that would still slip through.
`eval/lookalike_probes.csv` is the guard corpus (35 rows) and
`tests/test_lexicon.py` asserts that every one of them stays clean while the
true forms (רוצח, טיפשים, מלחמה, יריה, מקבלנים, זיינו, זונות, הרמא…) keep
matching. `python tools/sweep_lexicon.py` runs 105 ordinary Hebrew words
through the matcher and fails on any hit — the only tolerated hits are the
genuinely ambiguous ones ("בור" = a pit *or* the insult "a jerk"), listed with
the reason.


### The article, not the page
The same page also showed that the scanner was reading the **page**: the ynet
page has no `<article>`/`<main>`, so the fallback joined every `<p>` — including
the nav line `… ידיעות+ פודקאסטים כלכלה ספורט …`. Now `api/lib/article.py`
isolates the article (the body block) and strips the chrome; the suggestions
are collected separately. After the fix the same page reads
**violence 100 / attack 45 / profanity 0** — it is a war story (violence is
right), the "attack" is the word "טיפשים" inside the article itself, and the
menu words are gone. (A second bug fixed on the way: Hebrew sites that declare
a latin charset came out as mojibake — the fetcher now forces UTF-8.)

### Rebuilding the seed vectors
`python tools/build_seed_vectors.py` regenerates `api/assets/e5_seed_vectors.npz`
from `api/lib/seeds.py` with the local ONNX model (de-duplicated seeds, one index
array per factor). It **reuses the stored vector of a seed that already
exists**: the int8 model is sensitive to the batch padding, so a full
re-encode shifts the old vectors by ~0.02 and moves the tuned rulers.
`--fresh` forces a full re-encode, `--check` verifies without writing.

## ELI5 (read this first)

The model gives every pair of Hebrew sentences a similarity number.
Problem: it gives ~0.80 even to unrelated pairs ("urgency" vs "tomato").
So the *real* signal lives in a tiny band: 0.81–0.89, not 0–1.

Old code treated 0.82 as "strong match" for everything — but neutral weather also
scores 0.82. Result: every text looked Moderate.

Fix in plain words:
1. Measure each category separately. FOMO seeds naturally score higher than FUD
   seeds, so each gets its own ruler (its own 0-point and 100-point).
2. Score = where THIS text lands on its category's ruler (p5→0, p95→100).
3. Bonus for spikiness: a text screaming one category beats a text mumbling all three.
   Neutral weather mumbles all three → stays Low. Scandal screams FUD → goes High.

Numbers live in `api/lib/score.py:_CALIB` (measured 2026-10-19, see the table above).

## Acceptance
- Re-run `python eval/run_eval.py`: target ≥6/10 per category, neutral rows all Low.
- Re-run CLI pair: sensational-neutral delta ≥ 20 pts on the driven category.
- `python -m unittest discover -s tests` still green.

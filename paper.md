# Media manipulation pressure: a transparent, reproducible meter for headline language

**Working draft — version 0.2, 18 November 2026.**
**Status of the numbers: every accuracy figure in this document comes from a
DEVELOPMENT set. None of them is a measurement of quality. The held-out set
does not exist yet (§8).** The document is written to be extended, not to be
believed: each claim below points at the command that produces it.

---

## 1. Abstract

Headlines are a site of persuasion: they select and frame what a reader
encounters, and they do so in a small, repeatable vocabulary — the vague
noun that withholds the payload ("the secret", "the reason why"), the
scarcity claim ("only today"), the threat ("a deadly danger"). We built a
meter for that vocabulary: a public, versioned tool that reads an article,
returns six scores in 0–100 with the exact phrases that produced them, and
refuses to score anything it cannot point at.

The design principles are three, and they are unusual for this genre: (1)
**evidence-only** — a factor with no matched phrase scores zero rather than
inheriting the embedding's background similarity; (2) **no black box** — every
score resolves to a phrase in the headline and a published ruler, and no
component is permitted to create a signal on its own; (3) **reproducible
by hand** — a reader can re-run the whole pipeline and get the same
numbers, and the accuracy claims are guarded by machine-checked gates.

This document describes the system, the evaluation protocol, the results as
they honestly stand (a development set, not a test), and a reliability
analysis that we did not expect to need: the int8 model is not
bit-reproducible across CPUs, so a small number of decisions are coin flips
whose outcome depends on the machine that serves the request.

## 2. The question, and what the tool is not

The movement we are trying to start has a simple goal: **publishers being
careful about the reader's mental health** — not "the media lying", not a
partisan scoreboard, and not a truth detector. A headline can be frightening
because the story is frightening. We measure *language pressure*, not
intent, and the method page says so in the same words the reader sees.

Three things this instrument deliberately does **not** do:

- it does not judge the truth of a claim;
- it does not rank publishers by "quality" in general — it measures one
  dimension of the language;
- it does not make claims about a person or an outlet's motives.

It also does not measure everything that can feel manipulative. The six
factors are an operationalisation of a specific vocabulary (manipulation
framing, fear/uncertainty, urgency/scarcity, violence, personal attacks,
profanity), not a claim about the full space of persuasive techniques. A
headline can manipulate in ways none of the six catch; the corrections log
(§11) is where that becomes visible, in public.

## 3. What is measured

### 3.1 The six factors, in two families

| factor | what it captures | how |
|---|---|---|
| **clickbait** | a curiosity gap: the payload is withheld behind a vague noun or an unanswered question | embedding evidence against published seeds + a rule layer (vague noun in noun role, unanswered wh-question) |
| **FUD** | fear, uncertainty and doubt wording | embedding evidence against published seeds |
| **FOMO** | urgency and scarcity wording ("only today", "don't miss it") | embedding evidence against published seeds |
| **violence** | explicit violent words | a published word list with a score ramp |
| **attack** | insults and personal attacks | a published word list with a score ramp |
| **profanity** | swear words | a published word list with a score ramp |

The factors fall into **two families**, and the reports keep them apart:

- **pressure** = clickbait, FUD, FOMO — the manipulation language, which is
  what the instrument is about;
- **content** = violence, attack, profanity — what the story is about.

A war headline is high on the content side and can be quiet on the pressure
side. That difference is the interesting finding, so the two families are
never averaged into a single "how bad is this outlet" number. The reader's
headline number for one article is the **strongest** of the six — never an
average, because a violent article with five zeros must not come out
"Moderate" and disappear.

Seed lists live in `api/config/seeds.json` and are versioned with the code. The
list has been expanded over time (e.g. `arson`, `chaos`, `damaged` added to
the violence/FUD families after live headlines scored 0 despite clear
evidence words) — each addition preserves the disjoint rule that a seed
belongs to exactly one factor.

### 3.2 The evidence rule

A semantic factor with **no matched seed** scores **0**, not the ~40 that the
embedding's background similarity would produce (E5 gives roughly 0.84
cosine to *any* Hebrew text; the measured background is a score in the
middle of the scale). The consequence is that the meter's output is
interpretable: a non-zero score means a phrase matched, and the phrase is
shown.

Two floors sit above the continuous score:

- a **literal seed floor** — a multi-word seed phrase in the headline (e.g.
  "משבר" → FUD, "רק היום" → FOMO) floors the factor, because the evidence
  is direct rather than statistical;
- a **rule floor** for clickbait — a missing bottom line floors at 90, an
  unanswered wh-question at 78, an un-anchored vague word at 70. The rule
  verdict is a floor, not a bonus: a toxic headline fails on its own, and
  the body can add evidence but never dilute it.

### 3.3 Empty titles

A scan whose headline or title comes back empty is treated as an error, not
as a zero-scored article. Every empty title is written to the `error_log`
table (url, domain, http_code, error_type, error_message, created_at) by
`db.log_error()`, in three places:

- the scanner's drain path (`api/service/scanner.py:_do_scan()`);
- the on-demand scan path (`api/service/scanner.py:scan_url()`);
- the admin test endpoint (`api/service/api.py`).

A separate tool, `tools/fix_empty_titles.py`, audits the cached `scans`
table for empty headlines and writes them to `error_log` (with an optional
`--delete` to also remove the scan rows). This means an article that never
got a badge is visible to the operator, with a reason, instead of silently
showing as 0/0/0/0/0/0 on the site.

### 3.4 The rulers and the thresholds

Each factor has its own calibration range (a low/high cosine pair) mapping
the embedding distance onto 0–100, and its own match threshold below which
a seed does not count as evidence. The rulers are fitted on the development
set and versioned with the code. They are *not* gold tertiles: Low < 33,
Moderate < 66, High above.

## 4. The system

```
URL ──► SSRF guard ──► fetch (once) ──► article isolation ──► six factors
         (api/lib/safefetch)              (api/lib/article.py)          (api/lib/score.py)
                                               │
                               ┌──────────────────────────────────────┤
                               ▼                                      ▼
                      the scores + the phrases            the site dimension
                      (the evidence panel)                (the observations table)
```

- **The fetch happens once.** A repeated check is free; a URL that is
  already in the cache never creates a second row.
- **The article is isolated from the page.** The navigation, the ads, the
  "related headlines" blocks and the footer are stripped before anything is
  scored. This mattered: before the isolation, one cached ynet article
  scored violence/attack/profanity 100/100/100 because the page's menu
  contained the word "פודקאסטים"; after it, 100/45/0.
- **The model is a meter, not a judge.** The headline is compared against a
  published list of manipulation phrases with a small multilingual sentence
  model (multilingual-E5-small, int8 ONNX; Wang et al., 2022). The model
  returns a proximity; the decision is a published formula over that
  proximity. Every score resolves to a phrase in the headline plus a public
  ruler. No component creates a signal on its own (§7.3).
- **The configuration is data.** The word lists, the exclusions, the ramps
  and the clickbait rule lists are editable in the admin; every value has a
  hardcoded fallback in the library, and a broken value is ignored rather
  than allowed to take the scanner down. A deployment can therefore be
  tuned per publisher, and an editor in production can block a false
  positive without a code deploy.
- **The Hebrew BERT is off.** A small Hebrew BERT (dictaBERT-tiny-parse)
  is exported and can confirm a rule signal or veto the embedding evidence,
  but an A/B measurement found it **neutral** as a scoring signal, so it
  ships disabled. It is retained for the evidence panel and as the encoder
  for a future head.

## 5. The data

### 5.1 The corpus

Two sources, both automatic:

- **scanned articles** — the article the reader submits, scored and stored
  with its evidence;
- **headline observations** — the headline-level sample of what a site
  publishes, including the rotating "related/most-read" blocks, which is a
  live sample of what a publisher promotes rather than of one article.

At the time of writing (22 October 2026): 954 scanned articles, 2267
headline observations, 21 outlets. The feed list holds 37 sites (the Israeli
Hebrew press, the international English press, and a few tabloids — the
point of the sample is to see the pressure *differ* between outlets, so a
corpus of only serious papers would measure nothing). These numbers have
grown since the feeder runs continuously; the table in §5.2 is the sample
at 22 October 2026 and is not updated live.

Roughly half the international sites refuse a plain fetch (HTTP 403/401/402 —
bot walls). This is a property of the web, not of the instrument, and it
biases the corpus towards outlets that allow automated reading.

### 5.2 The corpus at a glance

The table below is the sample at the time of writing (22 October 2026). The
**pressure** is the average of clickbait, FUD and FOMO; the **content** is
the highest of violence, attack and profanity. Only the outlets with at
least five observed headlines are listed.

| outlet | headlines | the pressure | the content |
|---|---|---|---|
| nypost.com | 725 | 0.6 | 9.3 |
| bbc.co.uk | 449 | 0.0 | 9.5 |
| theguardian.com | 198 | 0.6 | 3.6 |
| kan.org.il | 162 | 3.1 | 9.5 |
| srugim.co.il | 124 | 2.9 | 5.8 |
| ynet.co.il | 121 | 1.9 | 6.9 |
| dailymail.co.uk | 94 | 1.1 | 4.7 |
| c14.co.il | 94 | 2.1 | 4.8 |
| nbcnews.com | 72 | 0.0 | 5.3 |
| haaretz.co.il | 44 | 1.7 | 6.3 |
| walla.co.il | 40 | 0.1 | 6.9 |
| cbsnews.com | 36 | 1.1 | 7.6 |
| maariv.co.il | 34 | 2.4 | 3.2 |

**Read this table as a description of the corpus, not as a finding.** The
pressures are small (0–3 out of 100) because the sample is dominated by
straight news headlines, and the *content* column is several times larger
than the *pressure* column almost everywhere — which is exactly the
separation the two families exist for. A press study needs a sample
weighted towards the promotional blocks ("most read", "recommended"),
which is what the observation table holds; the article-level sample cannot
show the difference between a hard-news site and a tabloid's front page,
because the tabloid's own articles are mostly news too.

The honest reading of this table: **the instrument measures the language of
headlines, and most of the headlines it has seen so far do not carry much
manipulation pressure.** Whether that is a property of the corpus or of the
sampling is an open question, and it is the question the held-out sample
and a weighted corpus would answer.

### 5.3 The labelling

The labels are produced in the admin's labelling queue: the observer picks
one of the six bands per factor for a real headline, with a note. The
current draft (`eval/draft_labels.csv`) holds **93 real observed headlines**
of which **26 carry a note** - those are the rows where the human's label
differs from the machine's, and the note says why. The draft awaits human
approval. Two known false
positives were found by this process and are recorded with the reasoning
("אובך" as a surname rather than an insult; "מכוערת" as a harsh response
rather than an insult).

One label was changed with written reasoning: a headline about a dog that
was shot moved from violence-low to violence-moderate, because the factor
measures the violent *content*, not the victim.

### 5.4 The split

The evaluation set carries a `split` column, assigned by a hash of the
headline text so that a row cannot leak between the two. **At the time of
writing all 50 rows are `dev`**: the held-out split has not been frozen, and
`tools/freeze_test_split.py --check` therefore has nothing to verify. Until
the split is frozen and scored once, every number in §7 is a repair log.

## 6. The evaluation protocol

- **Metric**: exact match per factor — the predicted band equals the
  labelled band.
- **Delta check**: a sensational/neutral pair per factor; the score must
  separate them (the "does the meter notice a difference" sanity check).
- **No-regression gate**: a committed baseline (`eval/baseline.json`); a
  drop fails the build.
- **False-alarm sweep**: 105 ordinary Hebrew words that must not appear in
  any word list (the "מזון" class — a food word that once became an
  insult through a stem match).
- **Lookalike probes**: 35 near-miss headlines that must stay clean.
- **Extension parity**: the JavaScript in the browser extension must
  produce the same answers as the Python library, headline by headline.
- **A false-alarm ablation** of the clickbait layer: the rules alone, the
  embedding alone, and the full pipeline.

## 7. Results, as they stand

### 7.1 The development set (not a test set)

| factor | exact match | the delta check |
|---|---|---|
| clickbait | 50/50 | 80.0 |
| FUD | 50/50 | 100.0 |
| FOMO | 49/50 | 69.7 |
| violence | 50/50 | 80.0 |
| attack | 50/50 | 75.0 |
| profanity | 50/50 | 50.0 |

**Read this as a repair log, not a result.** The rulers, the floors and the
seed lists were tuned on these rows. The one FOMO miss is a label-vs-floor
disagreement: the headline contains a literal urgency seed, and the floor
makes it High while the human labelled it Moderate.

### 7.2 The clickbait ablation

| configuration | catches | false alarms |
|---|---|---|
| the rules alone | 4/11 | 0 |
| the embedding alone | 6/7 | 4–6 |
| the full pipeline (evidence rule + floors + rules) | 11/11 | 0 |

The full pipeline's 11/11 is also a development-set number. What the
ablation *does* show, and what survives the tuning, is the ordering: the
rules are precise but incomplete, the embedding is sensitive but noisy, and
the evidence rule is what makes them combine.

### 7.3 Reliability: the measurement has a noise floor

An unplanned result of running the CI on a different machine.

The model is int8-quantised with **dynamic** quantisation (96
`MatMulInteger` operations), so the integer arithmetic is performed at
inference time and takes a different path on a different CPU (VNNI vs AVX2
vs a different onnxruntime build). The seed vectors are additionally
**frozen**: `api/assets/e5_seed_vectors.npz` was computed once, in one batch, and
is committed; the headline is encoded live, alone, at inference time. The
cosine is therefore computed between a vector that went through one
arithmetic path and a vector that went through another.

Measured on one machine, the frozen seed vectors and a fresh encoding of
the same text have a cosine of 0.993 — not 1.0 — and on a borderline
headline the query-to-seed cosine moves by **0.0008**.

One development row had a margin of **0.00046** — *smaller than the noise
floor*. It was never determinate. On the CI runner it crossed the
threshold, the evidence fired, and the row scored 76.3 (High) where the
workstation scored it 0 (no evidence) — a difference of one row in the
clickbait accuracy, and a red build.

Two responses, both implemented:

1. **The evidence margin** (`api/lib/score.py: _EVIDENCE_MARGIN = 0.005`): a
   seed only counts as evidence when it is *clearly* over the threshold, not
   merely over it. The margin is wider than the noise floor, so the same
   headline gets the same answer on every machine. The cost was measured,
   not guessed: the development accuracy is unchanged at every margin from
   0.001 to 0.020, because the rows in the band were scoring zero anyway.
2. **The margin report** (`tools/check_margins.py`): it computes the
   distance of every decision to its boundary and names the ones that a
   different CPU could flip. Two of the 300 decisions on the development set
   can flip a label, and the no-regression gate therefore carries a
   **one-row tolerance** per factor — narrowly, and with the reason
   written down.

The deeper point: the match thresholds are the *median* of the
best-match distribution, so by construction a band of headlines sits near
them. A margin makes that band deterministic rather than a coin flip, at the
cost of some recall on genuinely marginal headlines — a cost that only the
held-out set can quantify.

This is the sort of finding that a held-out set does not reveal, and a
single-machine evaluation hides. It is reported here because a published
metric that cannot survive a different CPU is not a measurement.

### 7.4 The false-alarm classes that were found and fixed

- **The stem trap.** A root's plural form is a plural marker, never a word
  on its own: otherwise "מזון" (food) became "זונ" and reached the attack
  list — a real cached article scored attack 100. The fix: a root's variant
  needs a real suffix after it, and the exclusion list folds like the
  matcher (one "מזון" entry kills מזונות / מזוני / המזון).
- **The substring trap.** The vague-word match was a substring match, so
  "מדברת" (she speaks) matched "דבר" (thing) and "בלי סיבה" (without a
  reason) matched "סיבה" (reason).
- **The context traps.** "שוטה" (a police officer in a report) is not an
  insult; "תקף" (to attack, in a protest report) is not violence; the
  Hebrew word for a song ("שירה") is not the shoot verb ("נורה").
- **The "no evidence" false alarms.** Before the evidence rule, five
  clickbait false alarms had *zero* matched seeds — the embedding's
  background similarity, nothing else. The rule removed them and the
  clickbait accuracy went 26/30 → 50/50.

## 8. Threats to validity

- **The evaluation set is the development set.** Every number in §7.1 was
  measured on the rows the rulers and floors were fitted on. The held-out
  set does not exist. This is the dominant threat and it is not mitigated
  by anything in this document.
- **The labels are one annotator's.** There is no second annotator and no
  agreement statistic yet. The labelling guide (docs/labeling.md) fixes the
  rules, but "the same person, later" is not inter-rater reliability.
- **The corpus is biased towards outlets that allow automated reading**
  (§5.1) and towards English and Hebrew in roughly equal parts, which is
  not the audience's language mix.
- **The factors are an operationalisation, not a construct.** "Pressure" is
  defined by the six measurements; a reader may experience pressure from
  factors we do not measure. The corrections log is the check on this.
- **The band cuts are placeholders.** Low < 33 < Moderate < 66 are fixed
  constants, not the tertiles of a population; with a held-out set they
  should be fitted.
- **One machine scores the site.** A reader's number is the number of the
  server they hit, not a number with an uncertainty interval. §7.3 bounds
  the variation but does not remove it.
- **The model is a background-similarity machine.** The evidence rule is a
  guard against its most common failure; it is not a claim that the
  embedding is unbiased.

## 9. Ethics and governance

- **The meter measures language, not intent** — stated on every page that
  shows a score.
- **A disagreement is a claim, not an edit.** Readers can report a wrong
  number; an editor verifies it; nothing changes until the editor says so.
  The confirmed false positives are published in a corrections log, and
  they become rows in the labelled set, so the same mistake does not come
  back.
- **Publishers answer on the record.** A publisher can reply from their
  site's page; the reply is published on that page after verification. We
  do not chase publishers; they contact us.
- **The reporter stays anonymous**, because the point is the measurement,
  not the complaint.
- **The instrument is public.** The method, the thresholds, the seed lists
  and the corrections are all public, and the data is reproducible by hand.
  A measurement nobody can check is a marketing claim.

## 10. Reproduction

```bash
pip install -r requirements.txt
python -c "from api.service.db import init; init()"     # the database
python api/service/api.py                                # the service (the scorer)
php -S localhost:8000 -t frontend/www                    # the site + the admin

python -m unittest discover -s tests                 # 221 tests
python run_eval.py                                   # the accuracy + the delta check
python tools/check_regression.py                     # the no-regression gate
python tools/check_margins.py                        # the decisions a CPU could flip
python tools/check_security_checklist.py             # the security checklist, run
python tools/sweep_lexicon.py                        # the false-alarm sweep
python tools/test_extension_parity.py                # the JS == the Python
python tools/check_preproduction.py                  # every claim in PREPRODUCTION.md
python tools/reeval_all.py                           # re-score all cached scans (no fetch)
python tools/reeval_all.py --only-zero --dry-run     # fast path: only still-unscored rows
# --only-zero=all also requires violence == 0 (default checks the 5 public factors)
python tools/fix_empty_titles.py                     # audit empty titles -> error_log
python tools/flexible_score_eval.py                  # compare current vs experimental model
```

An experimental **flexible rating model** (`flexible-v1`) is being explored as a
non-destructive alternative to the sharp seed floor: it accumulates weighted
seed evidence on a saturation curve so multiple weak signals add up. It is
**not shipped** — the current model stays the API/public default and no stored
scores are migrated. `tools/flexible_score_eval.py` compares both models on the
development set and writes `reports/flexible_score_comparison.md`; an admin-only
toggle (`?p=admin-flexible`) views both side by side. Weights and thresholds are
config (`config/flexible_score.json`). See `docs/flexible-score.md`.

The model (113 MB) is a derived artifact and is not in the repository: the
Docker build and the CI fetch it from the upstream release.

## 11. What is next, in order

1. **G1 — the answer key (label approval).** A human approves the 93 drafted
   labels in the admin queue (`?p=admin-label`), then labelling continues to
   500 Hebrew + 250 English rows. Each row is one headline with 6 factor
   bands (low/moderate/high) and optional notes. The labels are the ground
   truth — everything else depends on their quality.

2. **G2 — the held-out exam (freeze & score once).** The split is frozen by
   hashing the headline text so a test row can never leak into the training
   set. The held-out portion is scored **exactly once** — no retuning after
   seeing the results. This gives an honest accuracy number. Tool:
   `tools/freeze_test_split.py --freeze` then `run_eval.py`.

3. **G3 — the model, if the held-out set shows the rule layer is the
   accuracy ceiling.** Two tracks, only if G2 proves the current pipeline
   cannot improve further:
   - **G3a (cheap):** feature model over existing features (cosine, lexical
     hits, seed floors) — trains in seconds.
   - **G3b (fine-tuned BERT):** a small head on dictaBERT-tiny-parse
     embeddings — trains in minutes on GPU.
   Both are built in the same shape as the current BERT layer: they may
   confirm a rule signal or veto the embedding evidence, never create a
   signal of their own. In shadow mode they change no published number.
   **Progressive-retrain reports:** `reports/g3_progressive_report.html` and
   `.md` (100 labelled titles, hardcoded vs fitted rulers, 90.4% fitted
   accuracy); CLI: `cli/test_g3.py`, `cli/test_g3_progressive.py`;
   config: `api/config/trained_rulers.json`.

4. **G4 — the instruments.** Bootstrap confidence intervals, confusion
   matrix, balanced accuracy — the measures a paper needs before a
   percentage means anything.

5. **G5 — the rulers.** Fitted on a background corpus per language, so the
   thresholds describe the population rather than 50 rows.

## 12. The artefacts

Everything in this document is backed by something you can run:

| what | where |
|---|---|
| the site (the live view, the reports, the corrections, the per-site pages) | `?p=main-default`, `?p=main-reports`, `?p=main-corrections`, `?p=main-site&domain=?` |
| the method the readers see | `?p=main-method` (and `docs/method.md`) |
| the public API (read-only; the writes need the token) | `api/service/api.py` |
| the scorer (a pure function) | `api/lib/score.py: assess_text()` — `docs/lib.md` |
| the configuration (editable in the admin, with hardcoded fallbacks) | `frontend/modules/admin/ui/scanner.php` |
| the labelling queue | `frontend/modules/admin/ui/label.php` — `docs/labeling.md` |
| the error log (empty titles, fetch failures, timeouts) | `api/service/db.py` — `error_log` table, `db.log_error()` |
| the gates and the budget | `PREPRODUCTION.md` |
| the security checklist (every item runnable) | `docs/security.md` + `tools/check_security_checklist.py` |
| the deployment | `docs/deploy.md` + `Dockerfile` |
| the checks | `tools/check_regression.py`, `tools/check_margins.py`, `tools/check_preproduction.py`, `tools/check_production_config.py`, `tools/sweep_lexicon.py`, `tools/test_extension_parity.py`, `cli/test_g3.py`, `cli/test_g6.py`, `cli/test_dicta.py` |
| the progress reports (G3 retrain + dictaBERT) | `reports/g3_progressive_report.html` (.md), `reports/dicta_bert_report.html` (.md) |
| the CLI scanners / tests | `cli/scan.py`, `cli/test_g3.py`, `cli/test_g3_progressive.py`, `cli/test_g6.py`, `cli/test_dicta.py`, `tests/test_multi_worker.py` |
| re-eval and empty-title audit | `tools/reeval_all.py`, `tools/fix_empty_titles.py` |
| the corpus (the scans, the observations, the labels) | `api/data/fudfomo.db` (the service owns it; the schema is in `api/service/db.py`) |
| the write-up's own numbers | every figure above points at a command in §10 |

## 13. References

- Wang, L., et al. (2022). *Multilingual E5 Text Embeddings.* ACL 2022. — the
  sentence model (int8 ONNX) used as the proximity meter.
- Przybylski, A. K., et al. (2013). *Motivational, emotional, and behavioral
  correlates of fear of missing out (FoMo).* Computers in Human Behavior
  29(3). — the psychological construct behind the FOMO factor; we measure
  its *wording*, not the state.
- Chakraborty, A., et al. (2016). *Stop Clickbait: Detecting and preventing
  clickbaits in online news media.* IEEE Transactions on Services Computing.
  — the closest existing task; our contribution is the evidence rule, the
  phrase-level accountability and the corrections loop, not the detection
  itself.
- `dicta-il/dictabert-tiny-parse` (CC BY 4.0) — the Hebrew BERT, exported
  for the evidence panel and kept in shadow mode.
- Report files: `reports/g3_progressive_report.html` (G3 progressive retrain,
  100 labelled titles), `reports/dicta_bert_report.html` (dictaBERT off/on,
  clickbait comparison) — both with charts/colors and full per-title tables.
- The Tile Grid Map (CC BY-SA 4.0) — the world map in the country report.

---

### The one-paragraph version

We built a meter that reads a headline and returns six numbers with the
phrases that produced them, refuses to score anything it cannot point at, and
publishes everything it uses — the seeds, the rulers, the corrections. Empty
titles are logged as errors, not silently zero-scored. The instrument is
ready; the *measurement* of how good it is is not: every number we have comes
from the set we tuned on. The next honest step is a held-out set, frozen
before it is scored. Along the way we found that our own metric could not
survive a change of CPU, which is a reminder that a number you cannot
reproduce is a number you have not measured.

# LABELLING GUIDE — how a headline gets its six labels

> This is the contract for the labelled data. A label set is worth exactly what
> its definition is: two annotators following this file must agree on most
> rows, and the disagreements are the examples that belong in this file.
>
> The gold set lives in `eval/headlines_he.csv` (Hebrew) and, when it exists,
> `eval/headlines_en.csv` (English). The training/eval plan is in
> `PREPRODUCTION.md` §2.

## The row format

```csv
"הטקסט של הכותרת",clickbait,fud,fomo,violence,attack,profanity
```

- one row per **headline** (not per article, not per page)
- the six bands, in the fixed order above
- every band is `low`, `moderate` or `high`
- `?` is allowed in any column: it means *"the annotator was not sure"*. A
  `?` row is **excluded from the metrics** and kept in the set — flagging a
  hard row is honest; guessing is not.

## The six factors, in one sentence each

| factor | what it measures | a High label means |
|---|---|---|
| `clickbait` | the **curiosity gap** — the headline withholds the payload | "this headline will make you click to find out what it is about" |
| `fud` | **fear / uncertainty / doubt** wording | "this headline is written to make you afraid or uncertain" |
| `fomo` | **urgency / scarcity** wording | "this headline is written to make you rush" |
| `violence` | violent or threatening **content** | "this is a violent story" |
| `attack` | a **personal attack** (an insult aimed at someone) | "someone in this headline is being insulted or derogated" |
| `profanity` | **swearwords** (including the censored `פ*ק`) | "this headline contains a swearword" |

The factors are **separate questions about the same headline**. A row can be
High on two of them at once (a violent attack: `violence=high, attack=high`).

## The three rules that decide the hard cases

**1. The factors are disjoint.**
A scarcity headline ("בלעדי! אל תפספסו את ההזדמנות החד פעמית") is **FOMO, not
clickbait** — it has no curiosity gap, so `clickbait=low` even though the words
are dramatic. A fear headline ("משבר חמור, סכנה מיידית") is **FUD, not
clickbait**. The same words must not buy two factors.

**2. The canonical phrases are High.**
A headline that opens with a textbook clickbait phrase ("זה מה שקרה…",
"מה שלא סיפרו לך…", "לא תאמינו…") is `clickbait=high`, like the other
canonical openers. A headline that merely *hints* at a payload (a vague noun
with a pointer, an unanswered question) is `moderate` unless something else
pushes it up.

**3. The factor measures the wording, not the topic.**
"טבח קטסטרופה באזור מגורש" is a violence story, but "קטסטרופה" is fear
*wording* → `fud=high` (like the other explicit fear words "משבר", "סכנה"),
and `violence=high` for the killings. The factors do not compete for the same
sentence: the same headline can be High on two factors.

## The tie-breakers

**Low vs Moderate vs High.** Until the cuts are derived from the labels
(`PREPRODUCTION.md` §5.2), the working rule is:

- **Low** — the factor is not present in the wording. A reader who did not
  know the six factors would not notice it.
- **Moderate** — the factor is present but weak: a single soft cue, or a
  canonical phrase in a short, flat headline.
- **High** — the factor is the headline's whole job: several cues, or one
  unmistakable one.

**Quoted speech counts.** An insult inside a quote is still an insult: "השר
תקף את המחאה: 'אלה אנשים טיפשים'" → `attack=moderate`. There is **no
discount for quoted speech** — that is the current policy, deliberately: a
headline can smuggle an attack through a quote.

**A role word in a casualty report is not an insult.** "שוטה נהרג" (a police
officer was killed) → `attack=low`; "השרה שוטה שאינו מבין דבר" (the minister
is a jerk) → `attack=moderate`. The word is the same; the context is not.

**A verbal attack is not violence.** "השר תקף את המחאה" (the minister lashed
out at the protest) → `violence=low`; attacking a *person* is violence.

**A role word is not profanity.** "פודקאסטים" (podcasts) is not a swearword.
"מטבח" (kitchen) is not a massacre. The matcher blocks these; the label must
too.

**A swearword used literally is profanity.** "הפרשן זיין בשידור" → the word
counts (`profanity=moderate`), even when the sentence means it figuratively —
we do not guess the intent.

**The headline only.** Label the headline, not the article. The body may add
evidence to the score, but it never changes what the headline *is*.

## The annotator protocol

1. **Read the guide once**, then label 20 rows and compare with the existing
   labels.
2. **Two annotators label the same 50 rows** at the start of every new batch.
3. **The disagreements become examples here** — each one is a line in this
   file, with the row and the resolution.
4. **A `?` is a valid answer.** It is not a failure; it is a signal that this
   guide is missing a rule.

The agreement target: **Cohen's κ ≥ 0.7** on the band level, per factor. Below
that, the guide is not ready — fix the guide before labelling more.

## How the labels are used

- The **train/dev/test split** (`PREPRODUCTION.md` §2.1): the test split is
  **frozen** — a `api/data/splits.json` next to it holds its hash, and it is
  scored **once**. If a test row turns out to be mislabelled, the *next* test
  set replaces it; the old one is not re-edited.
- The **metrics** (`PREPRODUCTION.md` §4.2): the exact-match band accuracy per
  factor, plus the precision/recall/F1 and the bootstrap CI. The plain
  accuracy is meaningless at the ~7:1 class imbalance.
- The **seeds, the rulers and the cuts** are fitted on the train split only.
- The **hard negatives** (`eval/hard_negatives.csv`) are labelled the same way
  and reported separately: the alarming-but-informative headlines must not
  trigger `clickbait`.

## Changing a label

A label change is a **data change**, not a code change. It needs:

1. the reason (which rule, in this file, was applied),
2. a re-run of the eval (`python run_eval.py`),
3. and — if the row is in the frozen test split — a **new** test split, never
   an edit of the old one.

If a label change moves the headline accuracy by more than a point, that is
usually a *rule* change, not a data change: write the rule down here first.

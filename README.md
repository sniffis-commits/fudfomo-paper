# fudfomo-paper

Method, calibration and evaluation set behind **fudfomo**, the headline
pressure-load meter running at https://fudfomo.cia.org.il/ — a tool that
reads an article, returns six 0–100 scores, and shows the exact phrases
that produced them.

## What's here

- **paper.md** — the working paper (v0.3): the construct (the psychological
  pressure load of headline language, explicitly *not* manipulation-intent
  detection), the system, the evaluation protocol, and the honest status of
  every number.
- **calibration.md** — why the raw model scores collapse to "moderate"
  without fitted rulers, and the calibration plan.
- **labeling.md** — the headline labeling guide.
- **seeds.json / seeds.py** — the seed phrases per factor (verbatim reference
  copies from the private product repository; their import paths match that
  repository's layout, not this one).
- **thresholds.json** — the calibration rulers, match thresholds, evidence
  margin and label cuts, with provenance notes.
- **trained_rulers.json** — the fitted rulers.
- **headlines_he.csv / headlines_en.csv** — the labelled Hebrew and English
  headline sets (development sets — see paper §9).
- **attack_probes.csv, lookalike_probes.csv, profanity_probes.csv,
  scan_filter_probes.csv, violence_probes.csv, background_he.txt** — the
  factor probe corpora.
- **run_eval.py** — the evaluation harness (reference copy; it runs against
  the private repository's `api/lib`).
- **baseline.json** — the current eval baseline.

## Status of the numbers

Every accuracy figure here is a **development-set** figure. The held-out
test set does not exist yet (paper §9). The int8 model is not
bit-reproducible across CPUs, so a small number of borderline decisions are
machine-dependent.

## License

Creative Commons Attribution-NonCommercial-NoDerivatives 4.0
International (see `LICENSE`). This repository is shared for research
transparency and citation; it is not open-source code.

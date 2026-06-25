# paper_results: the five Section 4 numbers, reproducibly

This directory finishes the gaze and process analyses behind the five `\clg`
markers in `PatchworkPaper2026/Paper/patchwork.tex` Section 4 and makes each
number reproducible from local inputs. Every modeled contrast is saved to a JSON
in `results/` and a human-readable log in `logs/`, so each number in the paper
traces back to one record.

The analyses themselves and their status are documented in
`../../explorations/INVENTORY-gaze-process.md`. This layer promotes the five that
became load-bearing paper claims out of `explorations/` and applies the project's
modeling conventions uniformly through `lib/model_helpers.R`.

## Setup (running on a machine other than the original)

Three things must be in place. None are hardcoded to one laptop.

1. **Where the repo and data are.** Paths resolve from two environment variables,
   each with a sensible default:
   - `PATCHWORK_ROOT` — repo root. Defaults to the path the running script derives
     from its own location, so it usually needs no setting. Set it to override.
   - `PATCHWORK_DATA` — the per-task gaze data (the large
     `patchwork_data/<PID>/t<n>/*_fixation_filtered.csv` files). Defaults to
     `$PATCHWORK_ROOT/patchwork_data`. Set it to point at an external drive or
     shared mount if the data lives apart from the code.

2. **Python deps.** `python3 -m pip install -r requirements.txt` (pandas, numpy;
   compatible-floor pins). The builds also import two local modules from
   `explorations/diagram-support/src/`, which ship with the repo.

3. **R deps.** `Rscript install.R` (installs lme4, lmerTest, emmeans, jsonlite,
   MASS if missing). `lme4` needs a C/C++/Fortran toolchain to compile.

The interpreters are overridable in the `Makefile`: `PY ?= python3` and
`RS ?= Rscript`. Point `PY` at a Python 3.12+ that has the requirements (e.g. an
activated venv), or run `make PY=/path/to/python3`.

## Run it

```
make all       # build inputs, fit models, write results/ + logs/
```

`make all` reruns from local data: each finding's Python builder reads the raw
per-task gaze/IDE data under `$PATCHWORK_DATA` plus the task list from
`timing_correctness_data.csv`, writes its input CSV next to the model, and the R
model fits it and writes the results JSON. Each finding's `make` target (`search`,
`editing`, `validation`, `debugger`, `browser`) runs just that one.

## Modeling conventions (in `lib/model_helpers.R`)

- Crossed random intercepts `(1|PID)+(1|bug)`, with a fixed fallback when not
  estimable. Try full, drop `(1|bug)` keeping `(1|PID)`, then drop `(1|PID)`
  keeping `(1|bug)`, then plain `lm`/`glm`. The chosen structure is recorded in
  every JSON record so the choice is auditable, not a hidden degree of freedom.
- Two planned contrasts from the three-level condition factor.
  `patch_vs_control = c(-1, .5, .5)` and `correct_vs_overfit = c(0, 1, -1)`.
- BH correction within a finding's family, never across findings.
- Odds ratios via `exp()` for logistic models.

## Each finding, its `make` target, its script, and where it lands in the paper

| Finding (`make` target) | Paper marker | Script(s) | Results JSON | Headline |
|-----|--------------|-----------|--------------|----------|
| **search** | RQ2 fault localization (`add results from IDE analysis`) | GAZE: `01_search_behavior/build_fixation_buggy_method.py` then `fixation_buggy_method.R` (`results_fixation_buggy_method.json`). IDE: `build_ide_navigation.py` then `ide_navigation.R` (`results_ide_navigation.json`). | two JSONs (see scripts) | Patch removes the SEARCH not the STUDY, shown two ways. GAZE: share of fixation duration over the four NON-PATCH AOIs (denominator matched to Kaia's ARTool ANOVA and the Test/Runtime survival model); other-method share drops under a patch ($-0.092$, BH $=.006$), buggy-method share does not fall (positive, NS); raw minutes (~2 min on the buggy method across all conditions) retained descriptively. IDE: developers with a patch open ~24\% FEWER distinct files (breadth, ratio 0.76, BH $=.030$); explicit navigation-command rate is null after the duration offset (matching Phases 0--5); files-opened RATE (offset) is also null, so the effect is a total-count breadth effect, not a per-minute rate. |
| **editing** | RQ2 patch editing | `02_patch_editing/patch_editing_models.R` | `results_patch_editing.json` | Leaving the patch as given is much less likely under a deceptive patch (applied-unchanged OR 0.20, BH $=.041$). Developers fix elsewhere more under a deceptive patch (23\% vs 7\%; OR unstable at this N, reported descriptively). Among tasks where the patch entered the code, modifying it does not raise correctness (null; a coin flip, ~50\% either condition). |
| **validation** | RQ2 fix validation | `03_validation_window/validation_window_models.R` | `results_validation_window.json` | No measure shows MORE validation under a patch. Source-minutes lower ($p=.009$). Perception-vs-behavior gap. |
| **debugger** | RQ3 debugger use | `04_debugger_use/debugger_use_models.R` | `results_debugger_use.json` | Debugger use 52/17/37\% (control/correct/overfit); patch OR 0.16, $p=.004$. |
| **browser** | RQ3 browser use | `05_browser_engagement/browser_engagement_models.R` | `results_browser_engagement.json` | SUGGESTIVE. Late browser 51/47/71\%; correct-vs-overfit $p=.051$, permutation $p=.23$. |

The matching `\clgdraft{...}` blocks in `patchwork.tex` carry these numbers, each
with a `%% from results_<finding>.json` provenance comment. Claire's original
`\clg{...}` questions are preserved next to each answer.

## What Claire should know

- **The browser finding is method-dependent.** The correct-vs-overfit browser difference is
  borderline under a model ($p=.051$) and clears nothing under a permutation test
  ($p=.23$). No confirmatory bounded-proportion model was possible here, since
  `glmmTMB` cannot rebuild without gfortran and Stan is not installed. It is
  reported as a suggestive trend with both p-values shown.

## P-hacking notes

`make all` records, for the cases where a method choice moves a p-value across
.05, both options rather than the favorable one. The validation finding records the narrow
five-test BH family (source-minutes BH $=.046$) and the wider ten-test family
(BH $=.091$); the NULL headline holds under either. The browser finding shows model and
permutation p-values side by side.

The search-vs-study finding uses ONE normalization: the share of fixation
duration over the four non-patch AOIs (Test-and-Runtime-Feedback, Tests, Source
Code, Browser). This denominator is not a post-hoc pick. It matches Kaia's
existing AOI fixation analyses in the manuscript (the aligned-ranks-transform
ANOVA on non-patch AOI proportions and the Test-and-Runtime-Feedback survival
model), so the share is directly comparable to them. It deliberately excludes the
Patch AOI, which exists only in the patch conditions and would otherwise make the
cross-condition contrast incoherent. Raw fixation minutes are reported
descriptively only. Under this normalization the other-method share drops under a
patch ($-0.092$, $p<.001$, BH $=.006$) and the buggy-method share does not fall
(positive, trending up, NS). The total-source-share contrast does not survive BH,
so the claim rests on the other-method-share drop plus the buggy-method-share
null, not on total source.

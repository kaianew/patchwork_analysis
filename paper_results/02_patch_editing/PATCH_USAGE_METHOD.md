# How `patch_usage.csv` is built

## The question

Among the 84 patch tasks (every (participant, task) in the `correct` and
`overfitting` conditions), how did each developer use the suggested patch? The
goal is to determine when a developer took the suggested patch as given,
took it and then reworked it, fixed the bug their own way, or did nothing.

`build_patch_usage.py` answers supports this, getting us to: 

| `patch_usage` | n | meaning |
|---|---|---|
| `applied_unchanged` | 44 | left the suggested patch exactly as given |
| `applied_and_modified` | 12 | the patch entered their code, then they edited it |
| `own_fix_at_site` | 9 | edited the patch's location but with a different fix; the patch never entered |
| `own_fix_elsewhere` | 13 | fixed the bug somewhere other than the patch's location |
| `nothing` | 6 | no substantive code change |

Total N = 84.

## How it works, at a glance

Each task is characterized along two independent axes, which are then combined.

1. **End-state** is what the participant's *final code* looks like, found by
   comparing their submitted diff to the canonical suggested patch.
2. **Mechanism** is *how their answer got into the code, and if part of it is
   the patch suggestion being inserted*. This comes from the IDE event stream.
   This is a little subtle because there are many ways it could happen: apply
   dialogue, paste of the patch, or hand-typing. 
   
Two tasks are then corrected by a documented manual override, where the
mechanical signal is misleading (autocomplete masking a real transcription; token
overlap mistaken for transcription).

The rest of this document details each piece: the end-state classifier and its
matching rules, the mechanism flags, the join table, the two overrides, and the
cross-checks.

## End-state: the final diff vs the canonical patch

The end-state compares each participant's final submitted diff
(`patchwork_data/<disk_pid>/<bug>_diff.txt`) against the canonical suggested
patch for that (bug, condition). 

The end-state knows only two things. Is the final code identical to the
suggestion, and if not, is the edit at the suggestion's location or elsewhere.
The output is one of four end-states.

- `MATCHES-SUGGESTION`. Every canonical added clause appears at the patch's
  location, and there is no other substantive source change.
- `EDIT-AT-SITE`. The participant edited the patch's location, but either the
  canonical clauses are not fully reproduced, or there are additional
  substantive source changes elsewhere.
- `EDIT-ELSEWHERE`. The participant edited source, but not at the canonical
  patch's location. The edit is in a different file, or a clearly different
  region of the same file.
- `NOTHING`. No substantive added source lines anywhere.

### How clause matching works

Each line is normalized (comments stripped, internal whitespace collapsed) and
tokenized case-sensitively into identifiers, numbers, and individual
punctuation. A canonical added clause counts as reproduced if its token
sequence aligns into some participant line. The match first tries an exact
contiguous token-sequence match, then falls back to a tolerant alignment that
allows two kinds of slack.

- Redundant parentheses. Bracket tokens `(` and `)` can be inserted or deleted,
  so `((Character.isWhitespace(c)))` matches `(Character.isWhitespace(c))`.
- Typos. An identifier may be substituted by a typo-near identifier with
  character-level Levenshtein distance at most 2 and within 25% length, so the
  stimulus typo `addChangeListner` matches the compilable `addChangeListener`.

A token swapped for a genuinely different identifier is not a typo. For example
`epsilon` versus `maxUlps` (Levenshtein 6) is treated as not reproduced, which
correctly keeps a wrong or different fix out of `MATCHES-SUGGESTION`.

### Debug-line and comment handling

Comments are stripped before any substantiveness test, so commented-out code
never counts as a change. Live debug and instrumentation statements (print
tracing such as `System.out.println(...)`, `printStackTrace`, and logger calls)
are recognized and excluded from the count of extra source changes. A
participant who applies the patch verbatim and adds a `println` to trace it is
therefore still `MATCHES-SUGGESTION`, not `EDIT-AT-SITE`.

### The `suspect_trivial_patch` flag

Five (bug, condition) cells have a canonical patch so small that reproducing it
is almost indistinguishable from a participant independently making the same
one-token edit. These are flagged as `suspect_trivial_patch` whenever their
end-state is `MATCHES-SUGGESTION` or `EDIT-AT-SITE`. These are the only
end-states whose correctness rests on the clause match. `EDIT-ELSEWHERE` and
`NOTHING` are decided by location or absence, so they are never flagged. The
five cells and their
distinguishing single-token change are:

- `math50/correct`: `x1` -> `x0` (one character)
- `math50/overfitting`: `x0` -> `x` (delete one character)
- `lang10/overfitting`: `isWhitespace` -> `isHighSurrogate` (one identifier)
- `math33/correct`: `maxUlps` -> `epsilon` (one identifier)
- `math63/overfitting`: `x` -> `EPSILON` (one identifier, inside the line)

This is a property of the stimulus patch, not of any participant. It lowers
confidence in those cells but does not change the categorization.

## Mechanism: the IDE event stream

The end-state says what the final code looks like. The mechanism reads the IDE tracking log
(`patchwork_data/<disk_pid>/t<task>[ _part1/_part2]/ide_tracking.xml`) to
determine HOW the patch text got into the code. It computes four non-exclusive
present/absent flags by scanning the whole task event sequence.

- `applied_dialog`. The participant used the apply-patch dialog (any
  `ChangesView.ApplyPatch` event; the path is always `/suggested.patch` in this
  corpus, so this is unambiguous).
- `pasted_patch`. A paste into a source file that was preceded earlier in the
  task by a copy from `/suggested.patch`. A paste with no patch-copy precedent
  does not set this flag.
- `transcribed`. The participant typed the patch by hand. The typed source text
  is reconstructed positionally from the typing events, and its token
  containment is scored against the canonical added lines. The flag is True when
  containment is at least 0.80 and autocomplete interference is low (at most two
  `EditorChooseLookupItem` events). The containment score is the underlying
  signal; the boolean is a thresholded convenience.
- `deleted_at_source`. Any removal-based edit (backspace, delete, cut) on a
  source file. This catches patches that are applied by deleting characters
  rather than inserting them, which leave no typing, paste, or apply trace.

The six `P*_0` participants (P1_0 through P6_0) write actions with an `id="..."`
attribute instead of `event="..."`. The event reader falls back to `id`, so
their apply, copy, paste, and deletion events are not missed.

### What `patch_entered` means

`patch_entered = applied_dialog OR pasted_patch OR transcribed`. These are the
three ways the suggested patch text genuinely enters the developer's code. A
deletion does NOT count as the patch entering, with one inherent exception. The
single delete-only canonical patch, `math50/overfitting` (`x0` -> `x`), is
applied precisely by deleting a character, so for that cell a source deletion is
the legitimate application mechanism. The join handles this through the
end-state, not through `patch_entered`.

### The autocomplete caveat on transcription scoring

When a participant types and IntelliJ's autocomplete inserts tokens for them,
the reconstructed typed text under-represents what actually reached the buffer,
and containment under-scores. The `AUTOCOMPLETE_MAX` guard (at most two
autocomplete events) prevents calling a heavily autocompleted task
`transcribed` on an untrustworthy score. One task where this guard
under-counted a real transcription is corrected by a manual override (P5 t2,
below).

## The join

`patch_entered` and the end-state map to the final category by this rule:

| end_state | patch_entered | patch_usage |
|---|---|---|
| `MATCHES-SUGGESTION` | (either) | `applied_unchanged` |
| `EDIT-AT-SITE` | True | `applied_and_modified` |
| `EDIT-AT-SITE` | False | `own_fix_at_site` |
| `EDIT-ELSEWHERE` | (either) | `own_fix_elsewhere` |
| `NOTHING` | (either) | `nothing` |

The distinction the join adds is, among tasks that did not leave the patch
exactly as suggested, whether the patch actually entered the code and was then
modified (`applied_and_modified`) versus whether the participant wrote their own
fix at the same location without the patch ever entering (`own_fix_at_site`).

## The two manual overrides

Two cells are corrected by hand after the rule, because the mechanical signal is
misleading there. Both are encoded explicitly in the script so they are
auditable, with `override_applied = True` and the reason recorded per row.

- **(P5, t2)** -> `applied_and_modified`. The participant typed the deceptive
  patch `if(Character.isHighSurrogate(c))` verbatim, but an
  `EditorChooseLookupItem` autocomplete inserted `Surrogate` invisibly, so the
  typed-text containment under-scored a real transcription. The patch did enter
  via typing. The rule would have called this `own_fix_at_site`.

- **(P7, t2)** -> `own_fix_at_site`. A containment of 0.5 here is shared
  vocabulary, not transcription. The final diff is the participant's own
  diagnostic scaffolding (`final int t`/`e` comparison variables, an `if(t!=e)`
  probe, `DEFAULT_ULPS` changed 10 to 1, hand-worked math in comments), not the
  canonical `maxUlps` -> `epsilon` swap. The patch did not enter.

## External cross-checks

Two of Kaia's independent hand-coded fields, carried in
`timing_correctness_data.csv`, agree with the categorization.

- `evaluated_patch`. `N` means the participant did not engage with the suggested
  patch. No task categorized `applied_unchanged` or `applied_and_modified` is
  coded `evaluated_patch = N`. The diff-based and hand-coded engagement signals
  agree on whether the patch was used.
- `fix_site_same`. The single disagreement is P27 t1, which is
  `applied_and_modified` with `fix_site_same = Y`. This is not a
  misclassification. The canonical clause stayed intact at the patch line (so
  Kaia's `Y` is reasonable), but the participant also added a substantive source
  change elsewhere, which the file-level rule routes to EDIT-AT-SITE, and since
  the patch entered, to `applied_and_modified`. It is an apply-then-edit-elsewhere
  case.

## Final counts

`applied_unchanged = 44`, `applied_and_modified = 12`, `own_fix_at_site = 9`,
`own_fix_elsewhere = 13`, `nothing = 6`. N = 84.

## Inputs and output

The script reads only:

- participant final diffs `patchwork_data/<disk_pid>/<bug>_diff.txt`
- IDE logs `patchwork_data/<disk_pid>/t<task>[ _part1/_part2]/ide_tracking.xml`
- the 84-task list and the `fix_site_same` / `evaluated_patch` anchors from
  `patchwork_analysis/timing_correctness_data.csv`

The canonical patches are embedded in `build_patch_usage.py` (`CANONICAL_PATCHES`).

It writes `patch_usage.csv` in this directory, next to the R model
(`patch_editing_models.R`) that consumes it. The CSV is committed, so the model
runs without rebuilding, but the categorization is reproducible on demand by
running:

```
python3 patchwork_analysis/paper_results/02_patch_editing/build_patch_usage.py
```

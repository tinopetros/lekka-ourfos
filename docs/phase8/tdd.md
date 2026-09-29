# Phase 8: a cheaper expenser

## Goal

- Fewer tokens per classification, with no metric below phase 7's baseline. Hillclimbing on cost, held by the evals
- Spend little finding out: an eval run costs more than a month of production (phase 7 ADR 8), so every paid check has to earn its place

## Where a call's cost goes

From `usage_metadata` in ADK's eval history, gemini-3.5-flash-lite, at $0.30/M input and $2.50/M output:

| Part | Tokens | Share of cost |
|---|---|---|
| Prompt text: the rules, two examples, the chart, the schema | ~3.7k | ~57% |
| Images | ~1.4–2.2k | ~22% |
| Output | ~160 | ~21% |

- About $0.002 a call. No thinking tokens, nothing cached
- The prompt is the same for every call: the biggest lever, and the one quality leans on hardest

## Hypotheses

In order of risk to quality, lowest first.

### 1. The model names the account, code fills in the rest

- The model answers `name`, `glCode` and `amount` per line. `glId` and `accountType` come from the chart, by `glCode`
- `name` stays in what the model writes, before the code: it's the model's check on itself, naming the account it means before its number. Code then writes the chart's name, so what's stored reads the same every time. A name that doesn't match its code is logged
- A `glCode` not in the chart can't be filled: the answer becomes a rejection naming the code, never a guessed line. Fails closed, and a person sees why
- An `after_model_callback` on the agent does it, so classify, `adk eval` and `adk web` all see the whole `Classification`, as today. What's stored and logged doesn't change shape
- Expected: about a fifth less output. And a `glId` can no longer be wrong

### 2. The chart shows the model only what it reads

- `accounts.csv` stays whole, the reference and what code fills from. The prompt shows Account, GL Code, Account Type and Comment
- `GL ID` goes with hypothesis 1. `Disabled?`, `Are Manual Entries Allowed?` and `Used as` are the same on every row
- Expected: a few hundred tokens off every call

### 3. The prompt says each rule once

- Repeated rules said once: the credit rule is in `__TASK__` and `__EXCEPTIONS__`, the second example's note says it a third time
- Wording tightened, no rule dropped or changed. The examples' outputs shrink with hypothesis 1
- The riskiest of the three: ourfos-v2's wording was tuned by hand. Changed a section at a time, checked more than the others

### Not tried

- **Explicit context caching:** storage is billed by the hour, and production's calls are days apart. It costs more than it saves
- **Image resolution:** handwriting has to stay legible, and the images are a fifth of the cost
- **A smaller model:** Flash-Lite is the floor
- **Skipping the model for obvious rejections:** too few to matter

## Checking cheaply

- **Free first.** Unit tests, and Gemini's `count_tokens`, which generates nothing: a candidate's saving is known before any eval is paid for
- **What each run cost.** `make eval-failures` also prints tokens per call and dollars per run, from the `usage_metadata` ADK already keeps. Still stock ADK, still only reading its results
- **One paid rung at a time,** each only if the one before passed:
  1. `count_tokens` and unit tests: free
  2. 36 cases once: about 6 cents
  3. The final prompt 36 cases × 3, the phase 7 baseline's shape: about 15 cents
- **Hypotheses 1 and 2 together** in one run: neither changes what the model is asked to judge. Hypothesis 3 on its own run after, so a regression points at the wording
- **A fresh baseline once,** 36 × 1 on main, for tokens: phase 7 kept quality numbers, not token counts
- **Budget: $1 in all.** Stop and write up if it runs out

## Accepting a change

- Any false approval rejects it
- `accounts`, `amounts` and `no_false_rejection` no lower than phase 7's baseline, over 36 × 3. ADR 11's known misses fail as they did; a new failing case is a regression unless phase 7's variance already showed it
- A once-only failure in a 36 × 1 run is rerun on its own case before it's called: a case costs a fifth of a cent

## Done when

- Every hypothesis tried, kept or dropped, with its tokens and metrics in "What execution changed"
- The kept ones deployed to dev, and smoke passes
- The PR's description has the before and after

## What execution changed

## Not in this phase

- Image resolution
- A model or prompt change for accuracy: ADR 11's known misses stay as they are

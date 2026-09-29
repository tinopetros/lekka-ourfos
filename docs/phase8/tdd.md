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
- `name` stays in what the model writes, before the code: it's the model's check on itself, naming the account it means before its number. Code then writes the chart's name, so what's stored reads the same every time
- A line the chart can't confirm, a `glCode` it hasn't got or one whose name isn't the model's, can't be filled: the answer becomes a rejection naming it, never a guessed line. Fails closed, and a person sees why
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
- **What each run cost.** `make eval-report`, once `make eval-failures`, also prints tokens per call and dollars per run, from the `usage_metadata` ADK already keeps. Still stock ADK, still only reading its results
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
- Tests, lint, and every final answer in the evals a whole `Classification`. Dev gets it, and smoke, on merge to main
- The PR's description has the before and after

## What execution changed

### Results

gemini-3.5-flash-lite, 36 cases, each run's tokens per call from ADK's `usage_metadata`:

| Run | Prompt (`count_tokens`) | Text | Output | $ a call | Failures outside ADR 11's misses |
|---|---|---|---|---|---|
| main, 36 × 1 | 3,026 | 3,753 | 174 | 0.00202 | none |
| 1 and 2, 36 × 1 | 2,452 | 3,091 | 129 | 0.00171 | none |
| + 3a, 36 × 1 | 2,311 | 2,950 | 138 | 0.00169 | none |
| + 3b, 36 × 1 | 2,127 | 2,766 | 139 | 0.00164 | zimra-march-679, mr-chishakwe, mr-muchenje |
| 1, 2, 3a and the name check, 36 × 3 | 2,311 | 2,950 | 138 | 0.00169 uncached | mr-chishakwe ×1 |

The kept prompt against phase 7's baseline, 36 × 3:

| Metric | Phase 7, local | Phase 7, CI | Phase 8 |
|---|---|---|---|
| `no_false_approval` | 108/108 | 108/108 | 108/108 |
| `no_false_rejection` | 105/108 | 108/108 | 108/108 |
| `accounts` | 93/99 | 94/102 | 94/102 |
| `amounts` | 93/99 | 94/102 | 94/102 |

- **16% cheaper a call,** $0.00202 to $0.00169 with nothing cached. Text down 21%, output down 21%. Images unchanged
- The 36 × 3 run cached about a third of each prompt, implicitly, back to back: $0.00129 a call. Evals get that, production's calls days apart don't
- No metric below the baseline. Rawson and Safeden fail ×3, Bhola once, as in phase 7. Bhola was approved all three times
- mr-chishakwe once: Security Charges for a security installation, where the ledger has Maintenance Equipment. Rerun alone, 5 of 5 passed here and 4 of 5 on main: a judgement call that varies, not a regression
- All 108 final answers are whole `Classification`s, GL IDs filled from the chart
- Spent about $0.40 of the $1

### What was kept, and what wasn't

- **Hypotheses 1 and 2 kept.** Most of the saving: 574 prompt tokens and 45 output tokens a call
- **3 split in two.** 3a is structural, with no rule's wording changed: the prompt dedented, the credit rule said once in `__EXCEPTIONS__` and the examples, the role's lines on feedback and reversals gone (one call never sees either), and `form_name` out of the examples (no requisition has one). Kept
- **3b dropped:** each rule reworded more tightly, 184 tokens, about 3% a call. zimra-march-679 was credited to ZB Bank "as indicated on the receipt": the reworded credit rule had lost its "CANNOT". A safety rule isn't worth 3%, and rewording until the evals pass would fit the prompt to them. Reverted, not tuned
- **The name check fails closed.** In 3b's run mr-muchenje was System Support Expense by name and 5035, Consumables, by code: a slipped digit. The fill trusted the code. Now a name that isn't its code's is a rejection naming both, as an unknown code is. A handover, never a wrong account posted
- `count_tokens` priced every candidate before a run, for free. `make eval-report` prints each run's calls, dollars and tokens per call

## Not in this phase

- Image resolution
- A model or prompt change for accuracy: ADR 11's known misses stay as they are
- Rewording the prompt's rules: 3b showed its risk, for little

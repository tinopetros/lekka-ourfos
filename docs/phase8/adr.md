# Phase 8: decisions and shortcuts

### 1. Cost, never at quality's expense

- A change stays only if no metric falls below phase 7's baseline, over the same 36 × 3. One false approval drops it
- Production's spend is cents a month. The saving matters as much for eval runs, which cost more than production does

### 2. The model names the account, code looks it up

- `glId` and `accountType` are lookups, not judgements (phase 7 ADR 5): the chart has them, so the model no longer writes them
- The model keeps writing `name` before `glCode`, as its own check. What's stored is the chart's name
- An account not in the chart, or a name that isn't its code's, is a rejection that names it: never a guessed id posted to Mifos
- **Revised** (#25): the model writes only the account's name, and code looks up its GL code too. The model slipped on codes, 5035 for System Support's 5135 in 3 runs of 10 (#24), and a name is what it gets right. A name the chart hasn't got is still a rejection, and its reason says so

### 3. The chart stays whole

- `accounts.csv` is the reference and the lookup. The prompt shows only the columns the model reads

### 4. Paid checks climb a ladder

- Free checks first: tests and `count_tokens`. Then 36 × 1, then 36 × 3 for what's kept
- A $1 budget for the phase's evals
- **Revisit** if a check misses a regression that a larger run finds

### 5. Images and caching stay as they are

- Images are a fifth of the cost and carry the handwriting. Explicit caching bills storage by the hour for calls days apart
- **Revisit** if volume grows: caching pays once calls are minutes apart

### 6. The rules' wording stays ourfos-v2's

- Structure changed, words didn't: a tighter rewording saved 3% and broke the credit rule once in 36
- **Revisit** with a judge for reasons, or many more runs, if the prompt's wording is worth another look

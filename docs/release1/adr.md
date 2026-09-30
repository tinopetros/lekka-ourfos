# Release 1: decisions

Phases 1 to 9 and what follows them are release 1. Each phase kept its own ADR; the meaningful ones get gathered here later. New decisions that belong to no phase start here.

### 3. A test run tells only lekkai@ and its submitter

- `?test=true` beside `?workflow=`, on dev and prod alike. The run is real: cleaned, classified by the model, stored. Only who hears changes
- Its emails go to `lekkai@` and the submitter, never the project's list, and their subjects start `[TEST]`, so a forwarded one can't pass for real
- The document keeps `test: true`, so anything that lists requisitions can leave them out by default
- `true` or `false` only: anything else is a 400, as the cleaner guesses nothing
- The token still guards the trigger, so only whoever holds it can make a run a test
- Not `simulate`: that forces failures, on dev only. A test run fails only as a real one would
- **Revisit** with Mifos: a test run must never post. Until then `post` is a stub, and a test run goes through it like any other

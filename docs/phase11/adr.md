# Phase 11: decisions and shortcuts

### 1. One identity holds both Gmail and Mifos

- Closes phase 1 ADR 4: `ourfos-services` acts as `lekkai@` and holds Mifos's password
- The cost: whatever runs as it can email as Lekkai and post to the books
- The cap: its Mifos user can only make journal entries
- Not taken: **a `mifos` service of its own**, the only reader of the secret. One more thing to deploy, for one route
- **Revisit** when a second workflow posts

### 2. Verify reads Mifos's own lines

- Phase 5 counted lines, all a stub could give. Now each account, side and amount we posted is checked against what Mifos has
- A mismatch hands over, naming the transaction. Never a second post

### 3. The last email is Mifos's read-back

- It says what the books hold, not what we sent
- Closes phase 9 ADR 6 and phase 1 ADR 2: the confirmation is the word that counts

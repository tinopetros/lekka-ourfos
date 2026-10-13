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
- **Closed** by phase 12 ADR 11: Mifos isn't read back, since its reads take minutes

### 3. The last email is Mifos's read-back

- It says what the books hold, not what we sent
- Closes phase 9 ADR 6 and phase 1 ADR 2: the confirmation is the word that counts
- **Closed** by phase 12 ADR 11: the last email shows what we posted and Mifos's transaction id

### 4. Only prod posts to the books

- One Mifos server, two tenants: `default` is the books, `demo` is ours to break
- Terraform refuses `default` for any project but `ourfos-prod`, so a tfvars copied from prod fails its plan, before anything deploys
- Dev's user exists only in `demo` too, so even a wrong tenant can't log in. The check catches it sooner, and still holds if a `default` user ever lands in dev's secrets

### 5. We don't check Mifos's certificate, yet

- The server answers on a bare IP with a self-signed certificate, expired since May 2023, that doesn't name the IP. There's nothing to check it against
- So neither env checks it. The risk: whoever sits between Cloud Run and that IP could pass for Mifos and read the user's password
- The cap: the user can only make journal entries, and its password can be changed
- **Revisit** when the server has a name and a real certificate: `verify_ssl` on, in tfvars

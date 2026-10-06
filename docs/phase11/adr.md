# Phase 11: decisions and shortcuts

### 1. The connector is built into a wheel before the image

- It's private, so pip needs a token to fetch it. Inside the Docker build that means BuildKit secrets, which `gcloud builds submit --tag` doesn't pass
- So `package`, which already has the build's secrets, builds the locked commit's wheel. The Dockerfile installs it like any staged file, and never sees git or a token
- One PAT, read-only on one repo, in two places: Actions for `make check`, Secret Manager for Cloud Build
- Not taken:
  - **A private package index** (Artifact Registry). The connector's `publish.yml` already can, but it's another registry to grant, for one package
  - **Vendoring the source.** No token anywhere, but two copies to keep in step, and the connector is meant to be shared

### 2. Secrets for who we are, Terraform for where

- The username and password are secrets, made by hand per project, as `trigger-token` is. Neither the value nor the deployer's access goes through Terraform
- The URL, tenant, office and currency are plain env vars in tfvars: harmless, and a diff shows them
- **Revisit** if the Mifos user needs rotating often: one secret holding both, versioned together

### 3. Dev can't post to production Mifos

- One server, two tenants: `default` is the books, `demo` is ours to break
- Dev's credentials are a `demo` user, so even a wrong tenant can't log in. Terraform's validation and `mifos.py` both refuse `default` outside `ourfos-prod`
- Three guards for one mistake, since a wrong post to the books is the one failure we can't undo cleanly: a reversal is a second entry, and both stay

### 4. Verify reads what Mifos has, line by line

- Phase 5's count was all a stub could check. Now the read-back is Mifos's own, so each line's account, side and amount is compared with what we posted
- A mismatch is a handover naming the transaction, never a second post

### 5. The confirmation shows Mifos's lines, not ours

- The last email is built from the read-back, so it says what the books hold. When they differ from the suggestion, verify has already handed over
- A test run's last email says it wasn't posted, and shows the suggestion's lines instead

### 6. One service still holds both identities

- Phase 1 ADR 4 said Gmail's delegation and Mifos's credentials should never share an identity. `ourfos-services` now acts as `lekkai@` and reads Mifos's password
- Kept, for now: splitting means a second Cloud Run, its own account and a hop the workflow calls, while only one route posts
- What it costs: anything that can run as `ourfos-services@` can post to Mifos. The Mifos user can only make journal entries, which caps it
- **Revisit** before prod is released: if the split is cheap by then, it goes first

### 7. Dev doesn't check Mifos's certificate, yet. Prod must

- The server answers on a bare IP with a self-signed certificate for `Lekka Credit`, no IP in it, expired since May 2023. Nothing can verify it, so the connector's tests run with `verify_ssl` off
- Dev does the same against `demo`: its user can only reach the throwaway tenant
- Prod checks it, and Terraform refuses `default` without the check. So prod fails closed until the server has a name and a real certificate, rather than sending the books' password to whoever answers on that IP
- Not taken: **pinning the certificate's fingerprint.** It would work despite the expiry, but needs the connector to take a custom transport, and a server fixed once beats a pin kept forever

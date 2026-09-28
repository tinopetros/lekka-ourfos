# Phase 6: decisions and shortcuts

### 1. Keyless domain-wide delegation, for now

- `ourfos-services@` acts as `lekkai@` by signing its own JWT through `signJwt`. No key exists to leak
- The grant covers every user in the domain, not just `lekkai@`. Anyone who can sign as the account can read Drive and Gmail, and send mail, as anyone, within the three scopes
- Who can: the account itself, `ourfos-app-deployer` (acts as it to deploy), and infra's `deployer` (can grant itself). So whoever can merge to either repo or run their triggers
- No branch protection: both repos are personal, so the control is that only I can push
- **Revisit** with our own front end: uploads go to GCS, and delegation goes

### 2. It lives in the main service

- The runtime account holds the delegation, so everything in `ourfos-services` runs with it: the agent, the model's SDKs, every dependency
- A separate Workspace service would keep them out of reach, at the cost of another deployable and another cold start in every run. Not worth it yet
- **Revisit** if the service grows, or before prod

### 3. Three scopes, one subject

- `drive.readonly`, `gmail.readonly`, `gmail.send`. Never `mail.google.com`, which ourfos-v2 used and which can delete
- Workspace doesn't limit which user we act as, so our code does: `WORKSPACE_SUBJECT`, from Terraform, never from a request

### 4. The model sees the files

- Bytes go in as inline parts, labelled by field. The prompt's attachment rules come back word for word, which closes phase 5 ADR 5's gap
- A file we can't fetch or show hands over. With the rules back, dropping it would turn a sharing problem into a rejected requisition
- 15 MB per requisition, inline. Larger needs GCS or the Files API, which comes with GCS
- The files themselves aren't checked to come from the form's upload folder. The trigger's token is what stands in the way of someone naming any file `lekkai@` can see
- **Revisit** the folder check with email processing, or if the token leaks

### 5. Files are screened alone

- The plugin's whole-prompt screen reads only text, so files would reach the model unscreened
- Each PDF is screened on its own as a document, one at a time, as phase 5 ADR 12 does the fields. A made-up PDF with an injection matched; a clean one didn't
- Images aren't screened: Model Armor's `IMAGE` type fails on our template. A photo of a receipt reaches the model as is, accepted
- One more Model Armor call per PDF

### 6. Gmail is a setup check

- Three routes, reachable only with invoker IAM, never called by the workflow. `send` only mails `lekkai@` itself
- They prove the grant and the scopes. Email processing is its own phase, with its own decisions about threads and recipients

### 7. The trigger takes a bearer token

- A shared secret, since the form's webhook can't mint Google ID tokens. Cloud Run still lets anyone reach the function, and the function turns them away
- Weaker than IAM: whoever has the token can start runs. It's in Secret Manager and the form's webhook settings, and nowhere else
- Rotating it needs a redeploy
- Closes phase 5 ADR 9

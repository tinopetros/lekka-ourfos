# Phase 6: real workspace

## Goal

- Classify sees the actual attachments: fetched from Drive and given to the model as bytes, with ourfos-v2's attachment rules back in the prompt
- Show that Gmail works as `lekkai@`: find an email by subject, read a thread, send one to itself. No email processing yet
- The trigger stops being public: it wants a bearer token

## Shape

```
form / Postman ─ Bearer ─▶ trigger ─▶ workflow ─▶ /requisitions/{id}/classify
                   │                                   │
                   401                                 ├─ Drive, as lekkai@ ─▶ file bytes
                                                       ├─ Model Armor: fields, whole prompt
                                                       └─ expenser: JSON + one part per file

curl + ID token ─▶ /workspace/messages, /workspace/threads/{id}, /workspace/send   (Gmail, as lekkai@)
```

- The workflow, its steps and statuses are phase 5's. Only classify does more, and gets longer to do it
- `get_thread` and `notify` stay stubs

## Acting as lekkai@

- Keyless domain-wide delegation. `ourfos-services@` signs its own JWT through the IAM Credentials API, with `sub` set to `lekkai@lekkacredit.com`, and trades it for a token that acts as `lekkai@`
- `services/google_workspace.py`: `iam.Signer` into `service_account.Credentials(subject=…)`. One set of credentials per scope set, cached and refreshed by google-auth
- The subject comes from `WORKSPACE_SUBJECT`, set by Terraform. Never from a request
- Scopes: `drive.readonly`, `gmail.readonly`, `gmail.send`. Each call asks only for the one it needs
- Needs: Token Creator on itself (infra), the Drive and Gmail APIs (infra), and the Admin console grant (by hand). See Bootstrapped, once

## Attachments into classify

1. Read the requisition's file ids, per form field
2. For each: `files.get` for its `mimeType`, then the bytes (`alt=media`). Google Docs, Sheets and Slides are exported as PDF
3. Give the model one turn: the requisition as JSON, then for each file its form field as a label (`signed_requisition_form`) and the file as `Part.from_bytes(data, mime_type)`

- **Nothing about the files is stored.** The bytes live in memory for one classify request. The document keeps the Drive ids `requisition.files` already had, and `raw`. File names are never read: they're random, and often carry a person's name

- Shown: PDF, PNG, JPEG, WEBP, HEIC, and Google-native files as PDF. At most 40 MB across a requisition. Vertex took 105 MB inline on dev; the cap is about our own memory, now 1 Gi
- Any other image Pillow reads (GIF, BMP, TIFF, …) becomes PNG. `image/jpg` and friends are read as what they are. Nothing is resized: Gemini scales to 3072px itself and bills after, so shrinking first would only lose detail
- Word, Excel and the like still hand over: the model can't take them, and Drive can't export a file it didn't make
- The SDK base64s the bytes on the wire. `to_base64` exists only for looking at a part by hand
- **Can't fetch or can't show:** classify answers 422 with which file and why, and the run hands over. Not a silent drop, as ourfos-v2 did: with the rules back, the model would reject for a "missing" requisition that's really a permissions problem
- Drive's 429 and 5xx pass through as themselves, so the workflow retries them. Anything else from Drive is a 422
- Classify's timeout goes from 60s to 120s

### The prompt

- ourfos-v2's attachment rules come back word for word: a requisition attached, only one, it matches the form, signatures, receipts match, never state signatories' names
- Phase 5's "you are not shown the files yet" line goes
- "the email" stays "the requisition" (phase 5 ADR 7). The examples' comments get their signatures back
- The credit rule is unchanged: never from an attachment

### Screening

- Phase 5's: free text alone, then the whole prompt. Files aren't screened (ADR 4)
- The plugin reads the requisition from the turn's first text part, now that the turn has several

## Gmail, a setup check

On `ourfos-services`, which only invokers reach. The workflow never calls these:

```
GET  /workspace/messages?subject=…      up to 10: id, threadId, subject, from, date
GET  /workspace/threads/{id}            its messages: id, subject, from, to, date, snippet
POST /workspace/send {subject, body}    to lekkai@ itself, and nobody else
```

- Called by hand, with your own ID token (`make workspace` wraps it)
- Logs counts and ids, never subjects, bodies or addresses

## The trigger's token

- `Authorization: Bearer <token>`, compared with `hmac.compare_digest`. Missing or wrong: 401 before the body is read. No token configured: 500, so it never fails open
- The token is Secret Manager `trigger-token`, per project, made by hand (Bootstrapped, once). The function gets it as `TRIGGER_TOKEN`, a secret env var pinned to `latest`
- Rotate: add a version, redeploy the trigger
- `make start`, `smoke` and Postman read it with `gcloud secrets versions access`. The dev build can, as `ourfos-app-deployer`
- Still `allUsers` invoker at the Cloud Run level: the form can't mint Google ID tokens. The token is the gate
- Closes phase 5 ADR 9

## Terraform

- Services: `WORKSPACE_SUBJECT`, and 1 Gi of memory for the files. It signs as its own runtime account, read from its credentials
- Trigger: `TRIGGER_TOKEN` from `trigger-token:latest`
- Infra (tinopetros/lekka-ourfos-infra#14): the Drive, Gmail and IAM Credentials APIs, Token Creator for `ourfos-services@` on itself

## Fixtures and smoke

- Real files, shared with `lekkai@`: a signed requisition and a receipt, for LMS support, 60, to Mr Muchenje on 18 September 2026. Both are phone photos
- `happy` becomes that requisition: its payload, its two files. The model approves it
- `classify-jailbreak` loses its files, so it's Model Armor that stops it, not a missing file
- `nssa`, `bank` and `salary` lose their made-up files, so with the rules back they end `rejected`: no requisition attached. They get files when we have some to give them
- Simulated fixtures keep their made-up ids: a stubbed classify fetches nothing
- New:

| Fixture | simulate | Ends | Why |
| --- | --- | --- | --- |
| `file-missing` | none | `handed_over` | an id `lekkai@` can't see |

- A file of a type we don't show is unit tested, not a fixture, until we have one in Drive
- Smoke: `happy` done, `classify-jailbreak` and `classify-400` handed over, as before. Plus a run without the token gets 401
- `make test` also runs the new unit tests: which types are shown and converted, the size cap, labels, the token check

## Bootstrapped, once

Done 2026-09-28, both projects, and in infra's README (steps 10 and 11):

```bash
for P in ourfos-dev ourfos-prod; do
  gcloud secrets create trigger-token --project="$P" \
    --replication-policy=user-managed --locations=africa-south1
  openssl rand -base64 32 | tr -d '\n' | \
    gcloud secrets versions add trigger-token --project="$P" --data-file=-
  gcloud secrets add-iam-policy-binding trigger-token --project="$P" \
    --member="serviceAccount:ourfos-trigger@$P.iam.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
done
gcloud secrets add-iam-policy-binding trigger-token --project=ourfos-dev \
  --member="serviceAccount:ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor
```

By hand, in consoles:

- **Admin console** → Security → Access and data control → API controls → Manage Domain Wide Delegation → Add new, with `ourfos-services@`'s client ID and exactly `https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.send`
  - `ourfos-dev`: `107247035916374382942`
  - `ourfos-prod`: `110821488460640547261`, when prod is due
- **Drive**: the form's upload folder and the test files' folder, shared with `lekkai@` as Viewer
- **The form's webhook**: `Authorization: Bearer <token>`, from `gcloud secrets versions access latest --secret=trigger-token --project=<project> | pbcopy`. Later: the trigger checks the token as soon as this phase deploys

## Testing by hand

```bash
make test
make run FIXTURE=happy
make doc ID=<execution_id>
make workspace ROUTE='messages?subject=Requisition'
make workspace ROUTE=threads/<thread_id>
make workspace ROUTE=send BODY='{"subject": "ourfos setup check", "body": "hello"}'
```

- Postman without the token: 401. With it: 202

## Done when

- `happy` ends `done` on dev, the model having seen both its files
- `file-missing` hands over, naming the file
- The three Gmail routes work, and the email arrives in `lekkai@`'s inbox
- The trigger answers 401 without the token, and smoke passes with it
- `make check` passes

## What execution changed

- **Images**: any image Pillow reads is shown, as PNG if Gemini doesn't take its type, never resized. Only Word, Excel and the like hand over
- **The cap**: 15 MB was Gemini's old 20 MB inline limit. Vertex took 105 MB on dev, so it's 40 MB, bounded by our memory, which goes to 1 Gi
- **No file screening**: Model Armor can't read images (its `IMAGE` type fails on our template), and uploads are almost always photos. Screening only the rare PDF wasn't worth it (ADR 4)
- **Nothing about files stored**: an `attachments` list was tried and dropped. The Drive ids were already there, and names are noise
- **`happy` is real**: its files are the ones on the actual requisition, both phone photos, and its payee and date match them
- **Handovers say why**: `call_service` appends the service's `detail` to the error, so a handover names the file it couldn't fetch, with Google's own message
- **Gmail**: `lekkai@` sees the form's notifications, so email processing has what it needs

## Not in this phase

- Processing email: finding the form's thread, replies, who they go to
- Catching a reused requisition: a file, or its hash, already on an earlier requisition, or a date far from `disbursed_on` (ADR 4)
- Real Mifos
- Prod
- Uploads to GCS from our own front end, which is what replaces delegation

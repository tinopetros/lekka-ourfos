# Phase 3: a real model behind classify

## Goal

- `classify` can call a real model, to prove the whole chain fires: workflow → Cloud Run → Model Armor → Vertex → back
- The agent is `expenser`. Classify will do more before calling it; for now it only calls it
- Its prompt is a dummy on purpose. The real use case comes later
- Classify calls the model by default, as prod will. `simulate` opts out: `stub` for the canned answer, or a forced failure

## Shape

```
workflow ─▶ ourfos-services POST /requisitions/classify
              │
              ├─ simulate.classify = stub | 400 | rejected | …   stub, as in phase 1
              └─ no simulate                                     agents/expenser, in process
                                                            │
                                                            ├─ ModelArmorPlugin: jailbreak? ─▶ 422
                                                            └─ gemini-3.5-flash-lite on global ─▶ classification
```

- `agents/expenser/agent.py` exposes an ADK `app`: the `root_agent` plus ADK's own `ModelArmorPlugin`. `adk web` and `services` load the same `app`, so screening is on in both
- `services` runs it through an ADK `Runner`, single-shot: no `get_fast_api_app`, no memory service, no session kept. The `Runner` insists on a session service, so each request gets a fresh `InMemorySessionService` that goes away with the request
- Its output is the stub's shape (`approve`, `reason`, `debit`, `credit`) through `output_schema`, so `check` and everything after it stay unchanged

## The dummy prompt

- Approve, debit `6100`, credit `1100`, both for the amount
- Reject anything over 10,000 as too large
- Model defaults otherwise. No temperature

## Model Armor

- ADK's `ModelArmorPlugin` screens the prompt in `before_model_callback`. We only configure it
- One `google_model_armor_template` named `expenser` in each project, with only prompt injection and jailbreak turned on, at medium confidence
- In `eu`: the plugin calls `modelarmor.<location>.rep.googleapis.com`, and there's neither an `africa-south1` nor a `global` one
- It fails closed, which is the plugin's default. A block or a screening error comes back as a canned reply marked `model_armor_blocked`, and classify turns that into a 422. It isn't retried, so it ends `handed_over`

## Errors

| From | classify returns | The workflow |
| --- | --- | --- |
| Vertex 429 / 503 | same code | retries (`is_retryable_read`) |
| Model Armor block or error | 422 | `handed_over` |
| Output that doesn't parse | 500 | `handed_over` |

## Config

The model runs where it's served, and the container stays in `africa-south1`.

```bash
# Cloud Run env, set by Terraform. agents/expenser/.env locally
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=ourfos-dev
GOOGLE_CLOUD_LOCATION=global
EXPENSER_MODEL=gemini-3.5-flash-lite
MODEL_ARMOR_TEMPLATE=projects/ourfos-dev/locations/eu/templates/expenser
```

## Build

- The image now needs `agents/` too. `make build` stages `services/` and `agents/expenser/` into `.build/services` and builds that, just like the trigger zip
- The image tag hashes both, so a prompt edit is a new image
- `ruff` and `uv lock --check` cover `agents/` too

## Terraform

- Infra already enables `aiplatform` and `modelarmor` in both projects. Nothing to enable here
- New here: the template, the env above on `ourfos-services`, and two project roles for `ourfos-services`: `aiplatform.user` and `modelarmor.user`

## Fixtures and smoke

| Fixture | simulate.classify | Ends | Smoke |
| --- | --- | --- | --- |
| `happy` | none, 250 | `done` | yes |
| `classify-jailbreak` | none, injection in `payable_to` | `handed_over` | yes |
| `classify-400` | 400 | `handed_over` | yes |
| `classify-too-large` | none, 50,000 | `rejected` | no |

- Fixtures aimed at later steps (`post-*`, `read-back-mismatch`, `thread-missing`) say `stub`, so they stay free and don't depend on the model

## Testing by hand

Locally, with application default credentials:

```bash
cp agents/expenser/.env.example agents/expenser/.env
make agent        # adk run agents/expenser
make agent-web    # adk web, in the browser
```

On dev, end to end:

```bash
make deploy
make run FIXTURE=happy
make run FIXTURE=classify-too-large
make run FIXTURE=classify-jailbreak
```

## Bootstrapped, once

The deployer now also makes the template and grants two more project roles.

In order, from a shell logged in as a project owner:

```bash
SA=ourfos-app-deployer@ourfos-prod.iam.gserviceaccount.com

for P in ourfos-dev ourfos-prod; do
  gcloud projects add-iam-policy-binding "$P" --condition=None \
    --member="serviceAccount:$SA" --role=roles/modelarmor.admin

  # Replace the phase 2 condition: four roles now (ADR 5)
  gcloud projects remove-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin --all
  gcloud projects add-iam-policy-binding "$P" \
    --member="serviceAccount:$SA" --role=roles/resourcemanager.projectIamAdmin \
    --condition='^;^expression=api.getAttribute("iam.googleapis.com/modifiedGrantsByRole", []).hasOnly(["roles/logging.logWriter", "roles/workflows.invoker", "roles/aiplatform.user", "roles/modelarmor.user"]);title=only-four-roles'
done
```

## Done when

- `make agent` answers locally, and a jailbreak there is refused
- On dev, `happy` ends `done`, `classify-too-large` ends `rejected` and `classify-jailbreak` ends `handed_over`
- Every phase 1 fixture ends exactly as before
- Smoke passes through the real dev trigger with the three cases

## Not in this phase

- What classify does before expenser
- The real prompt, chart of accounts and attachments
- Evals
- Telemetry beyond logs: Cloud Trace and token cost
- Output screening and the other Model Armor filters
- Agent Runtime

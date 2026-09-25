# Phase 3: decisions and shortcuts

### 1. In process on Cloud Run, not Agent Runtime

- Phase 1 ADR 3 still stands: classify stays in `ourfos-services`. One image, one deploy, and no extra hop to authenticate
- The agent is a plain ADK agent in its own `agents/` folder, so moving it is packaging, not a rewrite
- **Revisit when** it needs its own scaling, sessions or memory, or moves to `lekka-ourfos-agents`

### 2. ADK, not `google-genai` directly

- One structured call doesn't need ADK. It costs a heavier image, slower cold starts and a `Runner` that wants a session
- We take it anyway for `adk web` and the same shape as `lekka-ourfos-agents`
- **Revisit when** cold starts hurt, or if classify is still a single call once the real prompt lands

### 3. No sessions, no memory

- `InMemorySessionService` is a dict that only grows. One service shared across a warm instance would leak a session per request
- So each request gets its own, and nothing outlives it

### 4. `simulate` decides, and the model is opt-in

- No `simulate` still means the stub, so fixtures and `make run` stay deterministic and free
- `simulate.classify = "llm"` is the only way to spend tokens, and smoke does it on every deploy
- That is the point: the grant, the region and the model id are what a deploy breaks, and only a real call catches them

### 5. The deployer can grant four project roles now

- `aiplatform.user` and `modelarmor.user` for `ourfos-services` join phase 2's two, deliberately, as phase 2 ADR 2 asked
- The service account is infra's, but what it may do is ours, like the other two

### 6. Model Armor through ADK's plugin

- `ModelArmorPlugin` on the `app`, so `adk web` screens exactly what production does, whichever model answers
- We only map its block marker to a 422
- Prompt injection and jailbreak only, on input only, fail closed
- **Revisit** with the real use case: output screening, harmful content, documents for attachments, and alerting on every block

### 7. `global` for inference, `eu` for screening

- Neither Flash-Lite nor Model Armor is offered in `africa-south1`. The container stays there
- The plugin only speaks to regional Model Armor endpoints, and there's no `global` one
- **Revisit when** either comes to `africa-south1`, or if data residency starts to matter

### 8. Prompts and answers are not logged

- Requisitions carry names and salaries, so neither logs nor spans capture what goes to the model or what comes back. Only the decision and the amount are logged, as today. Same stance as `lekka-ourfos-agents`

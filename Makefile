ENV ?= dev
VALID_ENVS := dev prod
PROJECT := ourfos-$(ENV)
REGION := africa-south1
# ourfos-api alone, for its domain (terraform/variables.tf, api_region)
API_REGION := europe-west1
TF_DIR := terraform
FORM ?= requisition
FIXTURE ?= happy
CLOUDSHELL_DEST ?= ~/lekka-ourfos
RUFF := uvx ruff@0.16.9

# One Terraform data dir per env, so dev's state can never be planned against prod
export TF_DATA_DIR := .terraform-$(ENV)

# The image tag is a hash of what goes in it, so an unchanged service is never rebuilt.
# No git, since Cloud Shell gets a plain copy, and sha1sum or shasum, whichever the image has
SERVICES_SRC := $(shell find services agents/expenser -type f ! -path '*/.venv/*' ! -path '*/__pycache__/*' \
	! -path '*/.pytest_cache/*' ! -path '*/tests/*' ! -path '*/.adk/*' ! -path 'agents/expenser/evals/*' ! -name requirements.txt ! -name .env \
	! -path 'services/api/*' ! -name api.Dockerfile | LC_ALL=C sort)
TAG := $(shell cat $(SERVICES_SRC) | (sha1sum 2>/dev/null || shasum) | cut -c1-12)
IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT)/ourfos/ourfos-services:$(TAG)
# ourfos-api's image the same way, from what goes in it: the services' code, and the UI
API_SRC := $(shell find services web -type f ! -path '*/.venv/*' ! -path '*/__pycache__/*' ! -path '*/.pytest_cache/*' \
	! -path '*/tests/*' ! -name requirements.txt ! -name .env ! -name Dockerfile \
	! -path 'web/node_modules/*' ! -path 'web/dist/*' ! -name '*.tsbuildinfo' | LC_ALL=C sort)
API_TAG := $(shell cat $(API_SRC) | (sha1sum 2>/dev/null || shasum) | cut -c1-12)
API_IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT)/ourfos/ourfos-api:$(API_TAG)
API_BUILD := .build/api
SERVICES_BUILD := .build/services
WHEELS := .build/wheels
REQUIREMENTS := services/requirements.txt
TF_ARGS ?=
comma := ,
# make evals: which cases (comma separated eval_ids, all when empty), and how many times over
CASE ?=
RUNS ?= 1
EVALS := expenser/evals
TF_VARS := -var-file=env/$(ENV).tfvars -var services_image=$(IMAGE) -var api_image=$(API_IMAGE) -var build_version=$(VERSION) $(TF_ARGS)
# The form names its workflow
WORKFLOW = $(if $(filter requisition,$(FORM)),expense,intake)
# A fixture run's submission: its own each time, unless you name one to run on again
SUBMISSION ?=
SERVICES_URL = $$(gcloud run services describe ourfos-services --region $(REGION) --project $(PROJECT) --format 'value(status.url)')
API_URL = $$(gcloud run services describe ourfos-api --region $(API_REGION) --project $(PROJECT) --format 'value(status.url)')
# What the UI says it's on: the commit, from Cloud Build's SHORT_SHA or git, so a bug report names its build
VERSION ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
# make web: the API's port beside Vite's 5173, and who to be instead of your ADC account
API_PORT ?= 8000
ACT_AS ?=
OPENAPI := .build/openapi.json
SCHEMA := web/src/lib/api/schema.d.ts
# Each form's own, as JSON Schema: the UI draws its forms from them
FORM_SCHEMAS := web/src/lib/api/forms.json

.DEFAULT_GOAL := help
.PHONY: help check-env package build build-services build-api stage stage-api deploy destroy run start wait correct-start correct sync logs doc smoke evals eval-cases eval-report check test lint lock-check \
	web types types-check web-check \
	agent agent-web copy copy-to-cloudshell tf-init tf-fmt-check tf-validate-ci tf-plan tf-apply tf-destroy tf-output clean

help:
	@echo "make deploy              build the services image, then terraform apply"
	@echo "make run [FORM=requisition] [FIXTURE=happy] [TEST=1] [MIFOS=false] [SUBMISSION=<id>]  run workflows/fixtures/<FORM>/<FIXTURE>.json,"
	@echo "                         wait, show its logs. TEST=1: a test run. MIFOS=false: posting off. SUBMISSION: run on that submission again"
	@echo "make correct ID=<submission> [FIXTURE=correct]  run workflows/fixtures/requisition/corrections/<FIXTURE>.json on a requisition, and wait"
	@echo "make sync [FROM=2026-01-01]  the nightly journal_entries sync, or with FROM the preload, and wait"
	@echo "make logs ID=<execution> everything logged for one execution"
	@echo "make doc [FORM=requisition] ID=<submission>  its document and its runs, from Firestore"
	@echo "make smoke               the UI turns away whoever isn't signed in, then requisition's happy posted to demo, happy-gcs and google-doc done, mifos-off"
	@echo "                         not posted, jailbreak and 400 handed_over, every other form's happy done,"
	@echo "                         happy corrected in demo, and the stub's corrections (what CI runs)."
	@echo "make web [API_PORT=8000] [ACT_AS=<email>]  the UI on localhost:5173 and its API, on your ADC, reading dev's Firestore."
	@echo "                         Installs, and generates the types, first"
	@echo "make types               web's TypeScript types, from the API's OpenAPI (after changing services/api/models.py)"
	@echo "make check               fmt, validate, lock, lint and test, the types and the UI (what a PR runs)"
	@echo "make evals [CASE=a,b] [RUNS=1]  adk eval: expenser against real requisitions, paid (docs/phase7)"
	@echo "make eval-cases          the eval_ids CASE takes"
	@echo "make eval-report         which cases failed which metric, and what they cost, in the last RUNS runs"
	@echo "make test                the services' steps, emails and attachments"
	@echo "make package             requirements.txt from uv.lock, and the connector's wheel"
	@echo "make build               Cloud Build the services' and the API's images, each only if its hash is new"
	@echo "make copy                build, then sync the repo to Cloud Shell"
	@echo "make agent|agent-web     expenser locally, in the terminal or the browser"
	@echo "make destroy             terraform destroy"
	@echo "make tf-init|tf-plan|tf-apply|tf-destroy|tf-output"
	@echo "ENV=$(ENV) -> $(PROJECT)"

check-env:
	@case " $(VALID_ENVS) " in *" $(ENV) "*) ;; *) echo "ENV must be one of: $(VALID_ENVS)" >&2; exit 1 ;; esac

# File targets, so a later CI step without uv reuses what an earlier one made. The connector is left out: the image
# installs its wheel
%/requirements.txt: %/uv.lock %/pyproject.toml
	cd $* && uv export --frozen --no-hashes --no-dev --no-emit-package mifos-connector -q -o requirements.txt

# The connector is private, so its locked commit is built into a wheel here, where git can reach it, and never in
# the image (docs/phase11/tdd.md, step 1). In Cloud Build, git swaps a token in for ssh
$(WHEELS): services/uv.lock
	rm -rf $@ && cd services && uvx -q --from pip pip wheel -q --no-deps -w ../$@ \
		"$$(uv export --frozen --no-hashes --no-dev -q --only-emit-package mifos-connector | grep '^mifos-connector @')"

package: $(REQUIREMENTS) $(WHEELS)

# services/ with expenser and the connector's wheel beside it, as the image sees them. Never a local .env or venv,
# and not ourfos-api's own code, which has its image
stage: services/requirements.txt $(WHEELS)
	rm -rf $(SERVICES_BUILD) && mkdir -p $(SERVICES_BUILD)
	cp -R $(WHEELS) $(SERVICES_BUILD)/wheels
	COPYFILE_DISABLE=1 tar -cf - --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude tests \
		--exclude ./api --exclude api.Dockerfile -C services . | tar -xf - -C $(SERVICES_BUILD)
	COPYFILE_DISABLE=1 tar -cf - --exclude .env --exclude __pycache__ --exclude .adk --exclude expenser/evals -C agents expenser | tar -xf - -C $(SERVICES_BUILD)

# ourfos-api's: services/ and web/ side by side, the same packages, and its own Dockerfile
stage-api: services/requirements.txt $(WHEELS)
	rm -rf $(API_BUILD) && mkdir -p $(API_BUILD)/services
	cp -R $(WHEELS) $(API_BUILD)/wheels
	cp services/requirements.txt $(API_BUILD)/
	cp services/api.Dockerfile $(API_BUILD)/Dockerfile
	COPYFILE_DISABLE=1 tar -cf - --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude tests \
		--exclude Dockerfile --exclude api.Dockerfile --exclude requirements.txt -C services . | tar -xf - -C $(API_BUILD)/services
	COPYFILE_DISABLE=1 tar -cf - --exclude node_modules --exclude dist --exclude '*.tsbuildinfo' web | tar -xf - -C $(API_BUILD)

# As ourfos-build rather than the compute account (roles/editor), staged in our africa-south1 bucket rather than the
# US default. Each image only when its hash is new
CLOUD_BUILD = gcloud builds submit --project $(PROJECT) --region $(REGION) \
	--service-account projects/$(PROJECT)/serviceAccounts/ourfos-build@$(PROJECT).iam.gserviceaccount.com \
	--gcs-source-staging-dir gs://$(PROJECT)-ourfos-sources/builds --gcs-log-dir gs://$(PROJECT)-ourfos-sources/logs

build: build-services build-api

build-services: check-env
	@gcloud artifacts docker images describe $(IMAGE) --project $(PROJECT) >/dev/null 2>&1 \
		&& echo "$(IMAGE) already built" \
		|| { $(MAKE) -s stage && $(CLOUD_BUILD) $(SERVICES_BUILD) --tag $(IMAGE); }

build-api: check-env
	@gcloud artifacts docker images describe $(API_IMAGE) --project $(PROJECT) >/dev/null 2>&1 \
		&& echo "$(API_IMAGE) already built" \
		|| { $(MAKE) -s stage-api && $(CLOUD_BUILD) $(API_BUILD) --tag $(API_IMAGE); }

deploy: build tf-apply

destroy: tf-destroy

# Straight to the form's workflow, with the argument the API starts it with. Each run its own response_id, or every
# run after the first would find the first's thread and send no first email. The submission's id goes to stderr
start: check-env
	@python3 -c 'import json, sys, time; d = json.load(open(sys.argv[1])); \
		id = sys.argv[3] or f"fixture-{sys.argv[2]}-{time.time_ns()}"; d["submission"]["response_id"] = id; \
		print("submission", id, file=sys.stderr); \
		print(json.dumps(d | {"form": sys.argv[4], "id": id, "test": sys.argv[5] == "1", "mifos": sys.argv[6] != "false"}))' \
		workflows/fixtures/$(FORM)/$(FIXTURE).json $(FIXTURE) "$(SUBMISSION)" $(FORM) "$(TEST)" "$(MIFOS)" \
		| gcloud workflows execute $(WORKFLOW) --location $(REGION) --project $(PROJECT) --data "$$(cat)" --verbosity error \
			--format 'value(name)' | awk -F/ '{print $$NF}'

wait:
	@gcloud workflows executions wait $(ID) --workflow $(WORKFLOW) --location $(REGION) --project $(PROJECT) \
		--format 'value(state, result, error.payload)'

# A correction on a requisition's submission, ID: a fixture's reason, requested_by, lines and simulate
# (docs/phase12/tdd.md, step 4). Prints the execution, then waits for it
correct-start: check-env
	@python3 -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1])) | {"id": sys.argv[2]}))' \
		workflows/fixtures/requisition/corrections/$(FIXTURE).json $(ID) \
		| gcloud workflows execute correction --location $(REGION) --project $(PROJECT) --data "$$(cat)" --verbosity error \
			--format 'value(name)' | awk -F/ '{print $$NF}'

correct:
	@id=$$($(MAKE) -s correct-start) && echo "execution $$id" && $(MAKE) -s wait WORKFLOW=correction ID=$$id

# The nightly sync by hand, or with FROM, the preload (docs/phase12/tdd.md, step 6)
sync: check-env
	@id=$$(gcloud workflows execute sync --location $(REGION) --project $(PROJECT) \
		--data '{"kind": "journal_entries"$(if $(FROM),$(comma) "from": "$(FROM)")}' --format 'value(name)' | awk -F/ '{print $$NF}') \
		&& echo "execution $$id" && $(MAKE) -s wait WORKFLOW=sync ID=$$id

# Starts a run, waits for it to finish, then shows its logs (which land a few seconds late)
run:
	@id=$$($(MAKE) -s start) && echo "execution $$id" && $(MAKE) -s wait ID=$$id && sleep 5 && $(MAKE) -s logs ID=$$id

logs:
	gcloud logging read 'jsonPayload.execution_id="$(ID)"' --project $(PROJECT) --freshness 1d --order asc \
		--format 'table(timestamp, severity, resource.type, jsonPayload.message)'

# With your application default credentials: the submission, then each run on it
doc:
	@cd services && GOOGLE_CLOUD_PROJECT=$(PROJECT) uv run -q python -c 'import json, sys; from google.cloud import firestore; \
		from forms import FORMS; ref = firestore.Client(database="ourfos").collection(FORMS[sys.argv[1]].collection).document(sys.argv[2]); \
		print(json.dumps(ref.get().to_dict(), indent=2, default=str)); \
		[print(f"runs/{run.id}", json.dumps(run.to_dict(), indent=2, default=str)) for run in ref.collection("runs").stream()]' $(FORM) $(ID)

# Each case, form/fixture:what it should end as, a correction's @ the case it corrects. Dev only: prod is tested by
# hand, by Tino, on Ourfos
SMOKE := requisition/happy:posted requisition/happy-gcs:done requisition/google-doc:done requisition/mifos-off:skipped \
	requisition/classify-jailbreak:handed_over requisition/classify-400:handed_over \
	vehicle_log/happy:done loan_approval/happy:done write_off/happy:done \
	correction/correct-stale@happy:refused correction/correct@happy:corrected correction/reverse-only@happy-gcs:reversed \
	correction/correct-unposted@mifos-off:refused correction/correct-timeout@google-doc:handed_over

# Up to three tries each: after a first deploy, IAM takes a minute to catch up. happy posts to Mifos's demo tenant,
# for real: done, with a transaction that isn't the stub's. Each try its own submission, so a retry never runs on a
# submission an earlier try posted. The one that passed is kept, so the corrections after know which to correct:
# happy's for real, happy-gcs's and google-doc's on the stub, mifos-off's never posted. Corrections are never retried
# (docs/phase12/tdd.md, Smoke)
smoke: check-env
	@[ "$(ENV)" = dev ] || { echo "make smoke is dev's only: prod is tested by hand, on Ourfos" >&2; exit 1; }
	@code=$$(curl -s -o /dev/null -w '%{http_code}' "$(API_URL)/api/me"); echo "ui, signed out: $$code"; \
		case $$code in 302|401|403) ;; *) exit 1 ;; esac
	@rm -rf .build/smoke && mkdir -p .build/smoke; stamp=$$(python3 -c 'import time; print(time.time_ns())'); \
	for case in $(SMOKE); do \
		path=$${case%%:*}; want=$${case#*:}; form=$${path%%/*}; fixture=$${path#*/}; on=$${fixture#*@}; fixture=$${fixture%%@*}; \
		for try in 1 2 3; do \
			sub=smoke-$$fixture-$$stamp-$$try; \
			if [ $$form = correction ]; then \
				sub=$$(cat .build/smoke/requisition-$$on.id); \
				result=$$($(MAKE) -s wait WORKFLOW=correction ID=$$($(MAKE) -s correct-start FIXTURE=$$fixture ID=$$sub) 2>/dev/null); \
			else \
				result=$$($(MAKE) -s wait FORM=$$form ID=$$($(MAKE) -s start FORM=$$form FIXTURE=$$fixture SUBMISSION=$$sub \
					$$([ $$fixture = mifos-off ] && echo MIFOS=false)) 2>/dev/null); \
			fi; \
			echo "$$path: $$result"; echo "$$result" > .build/smoke/$$form-$$fixture.json; \
			case $$want in \
				posted) echo "$$result" | grep '"status":"done"' | grep '"mifos_transaction_id":"' | grep -qv '"stub-txn-' ;; \
				corrected) echo "$$result" | grep '"status":"corrected"' | grep '"reversal":"' | grep '"mifos_transaction_id":"' | grep -qv '"stub-txn-' ;; \
				skipped) echo "$$result" | grep '"status":"done"' | grep -q '"skipped":"mifos"' ;; \
				*) echo "$$result" | grep -q "\"status\":\"$$want\"" ;; \
			esac && { echo $$sub > .build/smoke/$$form-$$fixture.id; break; }; \
			[ $$form = correction ] && exit 1; [ $$try = 3 ] && exit 1; sleep 30; \
		done; \
	done
	@python3 scripts/smoke_checks.py $(PROJECT) .build/smoke

# Reads agents/expenser/.env. services/ on the path, since the agent fetches files through it, and agents/ for
# expenser.evals' custom metrics
ADK := cd agents && PYTHONPATH=../services:. uv run -q --project ../services adk

agent:
	$(ADK) run expenser

agent-web:
	$(ADK) web

check: tf-fmt-check tf-validate-ci lock-check lint test types-check web-check

# npm ci whenever the lock changes, and only then. npm writes this file on every install
web/node_modules/.package-lock.json: web/package-lock.json
	cd web && npm ci --no-audit --no-fund

# The API's models → OpenAPI → web's TypeScript. Generated, committed, never edited
types: web/node_modules/.package-lock.json
	@mkdir -p .build
	cd services && uv run -q python -c 'import json; from api.main import app; print(json.dumps(app.openapi(), indent=1))' > ../$(OPENAPI)
	cd services && uv run -q python -c 'import json; from forms import FORMS; print(json.dumps({k: f.model.model_json_schema() for k, f in FORMS.items()}, ensure_ascii=False))' > ../$(FORM_SCHEMAS)
	cd web && npm run -s types >/dev/null

# Fails when the committed types aren't what the API's models make
types-check: types
	@git diff --exit-code -- $(SCHEMA) $(FORM_SCHEMAS) || { echo "$(SCHEMA) or $(FORM_SCHEMAS) is stale: run make types and commit them" >&2; exit 1; }

web-check: web/node_modules/.package-lock.json
	cd web && npm run -s lint && npm run -s typecheck && npm run -s test && npm run -s build

# The UI on localhost:5173, its /api proxied to the API run here on your ADC, reading dev's Firestore as you
#. Never prod's. Both stop with ctrl-c
web: types
	@[ "$(ENV)" = dev ] || { echo "make web reads dev's data only" >&2; exit 1; }
	@echo "UI: http://localhost:5173  API: http://localhost:$(API_PORT)/docs  as $(or $(ACT_AS),your ADC account)"
	@trap 'kill 0' INT TERM EXIT; \
	(cd services && AUTH=local ENVIRONMENT=local GOOGLE_CLOUD_PROJECT=$(PROJECT) REGION=$(REGION) ACT_AS=$(ACT_AS) ATTACHMENTS_BUCKET=$(PROJECT)-attachments POST_TO_MIFOS=true \
		uv run -q uvicorn api.main:app --reload --port $(API_PORT)) & \
	cd web && API_PORT=$(API_PORT) npm run -s dev

# ADK's own eval, by hand: paid, about 20 cents for every case once, so never part of test, check or a build.
# Reads agents/expenser/.env like `make agent`. Exits non-zero if any case failed; the failures are listed
evals:
	@status=0; for run in $$(seq $(RUNS)); do \
		( $(ADK) eval expenser $(EVALS)/requisitions.evalset.json$(if $(CASE),:$(CASE)) \
			--config_file_path $(EVALS)/test_config.json --log_level warning $(if $(DETAIL),--print_detailed_results) ) || status=1; \
	done; python3 agents/expenser/evals/report.py $(RUNS); exit $$status

# Which cases failed which metric, from the results ADK itself keeps: its last RUNS runs
eval-report:
	@python3 agents/expenser/evals/report.py $(RUNS)

eval-cases:
	@python3 -c 'import json; [print(c["eval_id"]) for c in json.load(open("agents/expenser/evals/requisitions.evalset.json"))["eval_cases"]]'

test:
	cd services && uv run -q pytest -q -p no:warnings

lint:
	$(RUFF) check .
	$(RUFF) format --check .

lock-check:
	cd services && uv lock --check

# Tracked files plus what package made, so Cloud Shell has the same build
copy: build package
	gcloud cloud-shell ssh --command "mkdir -p $(CLOUDSHELL_DEST)"
	{ git ls-files; echo $(REQUIREMENTS) | tr ' ' '\n'; } \
		| COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -czf - -T - | gcloud cloud-shell ssh --command "tar -xzf - -C $(CLOUDSHELL_DEST)"

copy-to-cloudshell: copy

tf-init: check-env
	cd $(TF_DIR) && terraform init -input=false -backend-config=bucket=$(PROJECT)-tfstate

tf-fmt-check:
	terraform fmt -check -recursive $(TF_DIR)

# No backend and no credentials: validate checks configuration, not state
tf-validate-ci:
	cd $(TF_DIR) && export TF_DATA_DIR=.terraform-validate && terraform init -backend=false -input=false >/dev/null && terraform validate

tf-plan: tf-init package
	cd $(TF_DIR) && terraform plan -input=false -lock-timeout=5m $(TF_VARS)

tf-apply: tf-init package
	cd $(TF_DIR) && terraform apply -lock-timeout=5m $(TF_VARS)

tf-destroy: tf-init
	cd $(TF_DIR) && terraform destroy $(TF_VARS)

tf-output: tf-init
	cd $(TF_DIR) && terraform output

clean:
	rm -rf .build $(REQUIREMENTS) web/dist

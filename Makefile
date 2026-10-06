ENV ?= dev
VALID_ENVS := dev prod
PROJECT := ourfos-$(ENV)
REGION := africa-south1
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
	! -path '*/.pytest_cache/*' ! -path '*/tests/*' ! -path '*/.adk/*' ! -path 'agents/expenser/evals/*' ! -name requirements.txt ! -name .env | LC_ALL=C sort)
TAG := $(shell cat $(SERVICES_SRC) | (sha1sum 2>/dev/null || shasum) | cut -c1-12)
IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT)/ourfos/ourfos-services:$(TAG)
TRIGGER_ZIP := .build/trigger.zip
SERVICES_BUILD := .build/services
WHEELS := .build/wheels
REQUIREMENTS := services/requirements.txt functions/trigger/requirements.txt
TF_ARGS ?=
# make evals: which cases (comma separated eval_ids, all when empty), and how many times over
CASE ?=
RUNS ?= 1
EVALS := expenser/evals
TF_VARS := -var-file=env/$(ENV).tfvars -var services_image=$(IMAGE) $(TF_ARGS)
TRIGGER_URL = $$(gcloud functions describe trigger --region $(REGION) --project $(PROJECT) --format 'value(url)')
# The trigger's ?workflow= names the form, as its webhook always has, and the form names its workflow
WORKFLOW = $(if $(filter requisition,$(FORM)),expense,intake)
# A fixture run's submission: its own each time, unless you name one to run on again
SUBMISSION ?=
# The trigger's bearer token, read when used and never echoed
TOKEN = $$(gcloud secrets versions access latest --secret trigger-token --project $(PROJECT))
SERVICES_URL = $$(gcloud run services describe ourfos-services --region $(REGION) --project $(PROJECT) --format 'value(status.url)')

.DEFAULT_GOAL := help
.PHONY: help check-env package build stage deploy destroy run start wait logs doc smoke evals eval-cases eval-report check test lint lock-check \
	agent agent-web copy copy-to-cloudshell tf-init tf-fmt-check tf-validate-ci tf-plan tf-apply tf-destroy tf-output clean

help:
	@echo "make deploy              build the services image, then terraform apply"
	@echo "make run [FORM=requisition] [FIXTURE=happy] [TEST=1] [SUBMISSION=<id>]  run workflows/fixtures/<FORM>/<FIXTURE>.json,"
	@echo "                         wait, show its logs. TEST=1: a test run. SUBMISSION: run on that submission again"
	@echo "make logs ID=<execution> everything logged for one execution"
	@echo "make doc [FORM=requisition] ID=<submission>  its document and its runs, from Firestore"
	@echo "make smoke               no token 401, no ?workflow= 400, then requisition's happy, happy-gcs and google-doc done, jailbreak,"
	@echo "                         400 and invalid handed_over, and every other form's happy done and invalid handed_over (what CI runs)"
	@echo "make check               fmt, validate, lock, lint and test (what a PR runs)"
	@echo "make evals [CASE=a,b] [RUNS=1]  adk eval: expenser against real requisitions, paid (docs/phase7)"
	@echo "make eval-cases          the eval_ids CASE takes"
	@echo "make eval-report         which cases failed which metric, and what they cost, in the last RUNS runs"
	@echo "make test                the trigger's cleaners and token, the services' steps, emails and attachments"
	@echo "make package             requirements.txt from uv.lock, and $(TRIGGER_ZIP)"
	@echo "make build               Cloud Build the services image, if this hash is new"
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
# the image (docs/phase11/adr.md 1). In Cloud Build, git swaps a token in for ssh
$(WHEELS): services/uv.lock
	rm -rf $@ && cd services && uvx -q --from pip pip wheel -q --no-deps -w ../$@ \
		"$$(uv export --frozen --no-hashes --no-dev -q --only-emit-package mifos-connector | grep '^mifos-connector @')"

# Fixed mtimes so the zip, and so the function, only changes when the code does
# The models come from services/, so the trigger and the service share one shape
$(TRIGGER_ZIP): functions/trigger/main.py functions/trigger/auth.py functions/trigger/form.py services/submission.py services/requisition.py services/forms.py functions/trigger/requirements.txt
	rm -rf .build/trigger $@ && mkdir -p .build/trigger
	cp $^ .build/trigger/
	touch -t 198001010000 .build/trigger/* && cd .build/trigger && zip -q -X ../trigger.zip *

package: $(REQUIREMENTS) $(TRIGGER_ZIP) $(WHEELS)

# services/ with expenser and the connector's wheel beside it, as the image sees them. Never a local .env or venv
stage: services/requirements.txt $(WHEELS)
	rm -rf $(SERVICES_BUILD) && mkdir -p $(SERVICES_BUILD)
	cp -R $(WHEELS) $(SERVICES_BUILD)/wheels
	COPYFILE_DISABLE=1 tar -cf - --exclude .venv --exclude __pycache__ --exclude .pytest_cache --exclude tests \
		-C services . | tar -xf - -C $(SERVICES_BUILD)
	COPYFILE_DISABLE=1 tar -cf - --exclude .env --exclude __pycache__ --exclude .adk --exclude expenser/evals -C agents expenser | tar -xf - -C $(SERVICES_BUILD)

# As ourfos-build rather than the compute account (roles/editor), staged in our
# africa-south1 bucket rather than the US default
build: check-env
	@gcloud artifacts docker images describe $(IMAGE) --project $(PROJECT) >/dev/null 2>&1 \
		&& echo "$(IMAGE) already built" \
		|| { $(MAKE) -s stage && gcloud builds submit $(SERVICES_BUILD) --project $(PROJECT) --region $(REGION) --tag $(IMAGE) \
			--service-account projects/$(PROJECT)/serviceAccounts/ourfos-build@$(PROJECT).iam.gserviceaccount.com \
			--gcs-source-staging-dir gs://$(PROJECT)-ourfos-sources/builds --gcs-log-dir gs://$(PROJECT)-ourfos-sources/logs; }

deploy: build tf-apply

destroy: tf-destroy

# An invalid form answers 400 but still starts a run, which hands over. Each run its own response_id, or every
# run after the first would find the first's thread and send no first email. The submission's id goes to stderr
start:
	@python3 -c 'import json, sys, time; d = json.load(open(sys.argv[1])); \
		d["response_id"] = sys.argv[3] or f"fixture-{sys.argv[2]}-{time.time_ns()}"; print(json.dumps(d))' \
		workflows/fixtures/$(FORM)/$(FIXTURE).json $(FIXTURE) "$(SUBMISSION)" \
		| curl -s -X POST -H 'content-type: application/json' -H "Authorization: Bearer $(TOKEN)" \
		--data @- "$(TRIGGER_URL)?workflow=$(FORM)$(if $(TEST),&test=true)" \
		| python3 -c 'import sys, json; r = json.load(sys.stdin); print("submission", r.get("id", "(the run\x27s own)"), file=sys.stderr); print(r["execution_id"])'

wait:
	@gcloud workflows executions wait $(ID) --workflow $(WORKFLOW) --location $(REGION) --project $(PROJECT) \
		--format 'value(state, result, error.payload)'

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

# Up to three tries each: after a first deploy, IAM takes a minute to catch up
smoke: check-env
	@code=$$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' \
		--data @workflows/fixtures/requisition/happy.json "$(TRIGGER_URL)?workflow=requisition"); echo "no token: $$code"; [ "$$code" = 401 ]
	@code=$$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' -H "Authorization: Bearer $(TOKEN)" \
		--data @workflows/fixtures/requisition/happy.json "$(TRIGGER_URL)"); echo "no workflow: $$code"; [ "$$code" = 400 ]
	@for case in requisition/happy:done requisition/happy-gcs:done requisition/google-doc:done \
		requisition/classify-jailbreak:handed_over requisition/classify-400:handed_over requisition/invalid:handed_over \
		vehicle_log/happy:done vehicle_log/invalid:handed_over loan_approval/happy:done loan_approval/invalid:handed_over \
		write_off/happy:done write_off/invalid:handed_over; do \
		path=$${case%%:*}; want=$${case#*:}; form=$${path%%/*}; fixture=$${path#*/}; \
		for try in 1 2 3; do \
			result=$$($(MAKE) -s wait FORM=$$form ID=$$($(MAKE) -s start FORM=$$form FIXTURE=$$fixture) 2>/dev/null); \
			echo "$$path: $$result"; \
			echo "$$result" | grep -q "\"status\":\"$$want\"" && break; \
			[ $$try = 3 ] && exit 1; sleep 30; \
		done; \
	done

# Reads agents/expenser/.env. services/ on the path, since the agent fetches files through it, and agents/ for
# expenser.evals' custom metrics
ADK := cd agents && PYTHONPATH=../services:. uv run -q --project ../services adk

agent:
	$(ADK) run expenser

agent-web:
	$(ADK) web

check: tf-fmt-check tf-validate-ci lock-check lint test

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
	cd functions/trigger && uv run -q pytest -q
	cd services && uv run -q pytest -q -p no:warnings

lint:
	$(RUFF) check .
	$(RUFF) format --check .

lock-check:
	cd services && uv lock --check
	cd functions/trigger && uv lock --check

# Tracked files plus what package made, so Cloud Shell has the same build
copy: build package
	gcloud cloud-shell ssh --command "mkdir -p $(CLOUDSHELL_DEST)"
	{ git ls-files; echo $(TRIGGER_ZIP) $(REQUIREMENTS) | tr ' ' '\n'; } \
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
	rm -rf .build $(REQUIREMENTS)

ENV ?= dev
VALID_ENVS := dev prod
PROJECT := ourfos-$(ENV)
REGION := africa-south1
TF_DIR := terraform
FIXTURE ?= happy
CLOUDSHELL_DEST ?= ~/lekka-ourfos
RUFF := uvx ruff@0.16.9

# One Terraform data dir per env, so dev's state can never be planned against prod
export TF_DATA_DIR := .terraform-$(ENV)

# The image tag is a hash of what goes in it, so an unchanged service is never rebuilt.
# No git, since Cloud Shell gets a plain copy, and sha1sum or shasum, whichever the image has
SERVICES_SRC := $(shell find services agents/expenser -type f ! -path '*/.venv/*' ! -path '*/__pycache__/*' \
	! -name requirements.txt ! -name .env | LC_ALL=C sort)
TAG := $(shell cat $(SERVICES_SRC) | (sha1sum 2>/dev/null || shasum) | cut -c1-12)
IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT)/ourfos/ourfos-services:$(TAG)
TRIGGER_ZIP := .build/trigger.zip
SERVICES_BUILD := .build/services
REQUIREMENTS := services/requirements.txt functions/trigger/requirements.txt
TF_ARGS ?=
TF_VARS := -var-file=env/$(ENV).tfvars -var services_image=$(IMAGE) $(TF_ARGS)
TRIGGER_URL = $$(gcloud functions describe trigger --region $(REGION) --project $(PROJECT) --format 'value(url)')

.DEFAULT_GOAL := help
.PHONY: help check-env package build stage deploy destroy run start wait logs doc smoke check test lint lock-check \
	agent agent-web copy copy-to-cloudshell tf-init tf-fmt-check tf-validate-ci tf-plan tf-apply tf-destroy tf-output clean

help:
	@echo "make deploy              build the services image, then terraform apply"
	@echo "make run [FIXTURE=happy] run workflows/fixtures/<FIXTURE>.json, wait, show its logs"
	@echo "make logs ID=<execution> everything logged for one execution"
	@echo "make doc ID=<execution>  its requisition document, from Firestore"
	@echo "make smoke               happy ends done, jailbreak and 400 end handed_over (what CI runs)"
	@echo "make check               fmt, validate, lock, lint and test (what a PR runs)"
	@echo "make test                the trigger's cleaner"
	@echo "make package             requirements.txt from uv.lock, and $(TRIGGER_ZIP)"
	@echo "make build               Cloud Build the services image, if this hash is new"
	@echo "make copy                build, then sync the repo to Cloud Shell"
	@echo "make agent|agent-web     expenser locally, in the terminal or the browser"
	@echo "make destroy             terraform destroy"
	@echo "make tf-init|tf-plan|tf-apply|tf-destroy|tf-output"
	@echo "ENV=$(ENV) -> $(PROJECT)"

check-env:
	@case " $(VALID_ENVS) " in *" $(ENV) "*) ;; *) echo "ENV must be one of: $(VALID_ENVS)" >&2; exit 1 ;; esac

# File targets, so a later CI step without uv reuses what an earlier one made
%/requirements.txt: %/uv.lock %/pyproject.toml
	cd $* && uv export --frozen --no-hashes --no-dev -q -o requirements.txt

# Fixed mtimes so the zip, and so the function, only changes when the code does
# requisition.py comes from services/, so the trigger and the service share one shape
$(TRIGGER_ZIP): functions/trigger/main.py functions/trigger/form.py services/requisition.py functions/trigger/requirements.txt
	rm -rf .build/trigger $@ && mkdir -p .build/trigger
	cp $^ .build/trigger/
	touch -t 198001010000 .build/trigger/* && cd .build/trigger && zip -q -X ../trigger.zip *

package: $(REQUIREMENTS) $(TRIGGER_ZIP)

# services/ with expenser beside it, as the image sees them. Never a local .env or venv
stage: services/requirements.txt
	rm -rf $(SERVICES_BUILD) && mkdir -p $(SERVICES_BUILD)
	COPYFILE_DISABLE=1 tar -cf - --exclude .venv --exclude __pycache__ -C services . | tar -xf - -C $(SERVICES_BUILD)
	COPYFILE_DISABLE=1 tar -cf - --exclude .env --exclude __pycache__ -C agents expenser | tar -xf - -C $(SERVICES_BUILD)

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

start:
	@curl -sf -X POST -H 'content-type: application/json' --data @workflows/fixtures/$(FIXTURE).json $(TRIGGER_URL) \
		| python3 -c 'import sys, json; print(json.load(sys.stdin)["execution_id"])'

wait:
	@gcloud workflows executions wait $(ID) --workflow requisition --location $(REGION) --project $(PROJECT) \
		--format 'value(state, result, error.payload)'

# Starts a run, waits for it to finish, then shows its logs (which land a few seconds late)
run:
	@id=$$($(MAKE) -s start) && echo "execution $$id" && $(MAKE) -s wait ID=$$id && sleep 5 && $(MAKE) -s logs ID=$$id

logs:
	gcloud logging read 'jsonPayload.execution_id="$(ID)"' --project $(PROJECT) --freshness 1d --order asc \
		--format 'table(timestamp, severity, resource.type, jsonPayload.message)'

# With your application default credentials
doc:
	@cd services && GOOGLE_CLOUD_PROJECT=$(PROJECT) uv run -q python -c 'import json, sys; from google.cloud import firestore; \
		doc = firestore.Client(database="ourfos").collection("requisitions").document(sys.argv[1]).get(); \
		print(json.dumps(doc.to_dict(), indent=2, default=str))' $(ID)

# Up to three tries each: after a first deploy, IAM takes a minute to catch up
smoke: check-env
	@for case in happy:done classify-jailbreak:handed_over classify-400:handed_over; do \
		fixture=$${case%%:*}; want=$${case#*:}; \
		for try in 1 2 3; do \
			result=$$($(MAKE) -s wait ID=$$($(MAKE) -s start FIXTURE=$$fixture) 2>/dev/null); \
			echo "$$fixture: $$result"; \
			echo "$$result" | grep -q "\"status\":\"$$want\"" && break; \
			[ $$try = 3 ] && exit 1; sleep 30; \
		done; \
	done

# Reads agents/expenser/.env
agent:
	cd agents && uv run -q --project ../services adk run expenser

agent-web:
	cd agents && uv run -q --project ../services adk web

check: tf-fmt-check tf-validate-ci lock-check lint test

test:
	cd functions/trigger && uv run -q pytest -q

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

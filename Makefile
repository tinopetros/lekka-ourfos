PROJECT ?= ourfos-dev
REGION ?= africa-south1
TF_DIR ?= terraform
FIXTURE ?= happy
CLOUDSHELL_DEST ?= ~/lekka-ourfos

# The image tag is a hash of services/, so an unchanged service is never rebuilt
# No git here: Cloud Shell gets a plain copy
TAG := $(shell find services -type f -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -name requirements.txt | LC_ALL=C sort | xargs cat | shasum | cut -c1-12)
IMAGE := $(REGION)-docker.pkg.dev/$(PROJECT)/ourfos/ourfos-services:$(TAG)
TRIGGER_ZIP := .build/trigger.zip
TF_ARGS ?=
TF_VARS := $(TF_ARGS) -var project_id=$(PROJECT) -var region=$(REGION) -var services_image=$(IMAGE)

.DEFAULT_GOAL := help
.PHONY: help package build deploy destroy run logs copy copy-to-cloudshell tf-init tf-plan tf-apply tf-destroy tf-output clean

help:
	@echo "make deploy              build the services image, then terraform apply"
	@echo "make run [FIXTURE=happy] curl the trigger with workflows/fixtures/<FIXTURE>.json"
	@echo "make logs ID=<execution> everything logged for one execution"
	@echo "make package             requirements.txt from uv.lock, and $(TRIGGER_ZIP)"
	@echo "make build               Cloud Build the services image, if this hash is new"
	@echo "make copy                build, then sync the repo to Cloud Shell"
	@echo "make destroy             terraform destroy"
	@echo "make tf-init|tf-plan|tf-apply|tf-destroy|tf-output"
	@echo "PROJECT=$(PROJECT) REGION=$(REGION)"

# Fixed mtimes so the zip, and so the function, only changes when the code does
package:
	cd services && uv export --frozen --no-hashes --no-dev -q -o requirements.txt
	cd functions/trigger && uv export --frozen --no-hashes --no-dev -q -o requirements.txt
	rm -rf .build/trigger $(TRIGGER_ZIP) && mkdir -p .build/trigger
	cp functions/trigger/main.py functions/trigger/requirements.txt .build/trigger/
	touch -t 198001010000 .build/trigger/* && cd .build/trigger && zip -q -X ../trigger.zip *

build: package
	@gcloud artifacts docker images describe $(IMAGE) --project $(PROJECT) >/dev/null 2>&1 \
		&& echo "$(IMAGE) already built" \
		|| gcloud builds submit services --project $(PROJECT) --region $(REGION) --tag $(IMAGE)

deploy: build tf-apply

destroy: tf-destroy

run:
	curl -s -X POST -H 'content-type: application/json' \
		--data @workflows/fixtures/$(FIXTURE).json $$(cd $(TF_DIR) && terraform output -raw trigger_url)

logs:
	gcloud logging read 'jsonPayload.execution_id="$(ID)"' --project $(PROJECT) --freshness 1d --order asc \
		--format 'table(timestamp, severity, resource.type, jsonPayload.message)'

# Tracked files plus what package made, so Cloud Shell has the same build
copy: build
	gcloud cloud-shell ssh --command "mkdir -p $(CLOUDSHELL_DEST)"
	{ git ls-files; echo $(TRIGGER_ZIP) services/requirements.txt functions/trigger/requirements.txt | tr ' ' '\n'; } \
		| COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -czf - -T - | gcloud cloud-shell ssh --command "tar -xzf - -C $(CLOUDSHELL_DEST)"

copy-to-cloudshell: copy

tf-init:
	cd $(TF_DIR) && terraform init -reconfigure -backend-config=bucket=$(PROJECT)-tfstate

tf-plan: package
	cd $(TF_DIR) && terraform plan $(TF_VARS)

tf-apply: package
	cd $(TF_DIR) && terraform apply $(TF_VARS)

tf-destroy:
	cd $(TF_DIR) && terraform destroy $(TF_VARS)

tf-output:
	cd $(TF_DIR) && terraform output

clean:
	rm -rf .build services/requirements.txt functions/trigger/requirements.txt

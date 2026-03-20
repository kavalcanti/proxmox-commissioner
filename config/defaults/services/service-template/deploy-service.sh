#!/bin/bash

# This is an example file to streamline the service deployment process.
# Scripted provisioning template for the service-template service

# 1. Commission the VM and generate the inventory
bash ./scripts/service-commission.sh service-template
bash ./scripts/inventory-generate.sh service-template

# 2. Secure the VM
bash ./scripts/run-playbook.sh service-template 00-initial.yml
bash ./scripts/run-playbook.sh service-template 10-base-security.yml

# 3. Push service files and run post-deploy automation
bash ./scripts/run-playbook.sh service-template 25-file-push.yml
bash ./scripts/run-playbook.sh service-template 27-post-deploy.yml

# Run other playbooks or actions as needed
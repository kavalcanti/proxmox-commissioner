#!/bin/bash

# Scripted provisioning template for the service-template service

# 1. Commission the VM and generate the inventory
bash ./scripts/service-commission.sh service-template
bash ./scripts/inventory-generate.sh service-template

# 2. Secure the VM
bash ./scripts/run-playbook.sh service-template 00-initial.yml
bash ./scripts/run-playbook.sh service-template 10-base-security.yml

# Run onther playbooks or actions as needed
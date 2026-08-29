SHELL := /bin/bash

.PHONY: check syntax test deploy-dry-run

check: syntax test deploy-dry-run

syntax:
	@for script in pi/scripts/*.sh scripts/*.sh tests/*.sh; do \
		bash -n "$$script"; \
	done
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck pi/scripts/*.sh scripts/*.sh tests/*.sh; \
	else \
		echo "shellcheck not installed; skipped"; \
	fi

test:
	@bash tests/test-scripts.sh

deploy-dry-run:
	@bash pi/scripts/deploy.sh --dry-run

SHELL := /bin/bash

.PHONY: check syntax test deploy-dry-run web-test web-build

check: syntax test deploy-dry-run web-test web-build

syntax:
	@for script in pi/scripts/*.sh scripts/*.sh tests/*.sh; do \
		bash -n "$$script"; \
	done
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck --severity=error pi/scripts/*.sh scripts/*.sh tests/*.sh; \
	else \
		echo "shellcheck not installed; skipped"; \
	fi

test:
	@bash tests/test-scripts.sh

deploy-dry-run:
	@bash pi/scripts/deploy.sh --dry-run

web-test:
	@cd web && uv run --frozen python -m pytest

web-build:
	@cd web && uv run --frozen python build.py

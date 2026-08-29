SHELL := /bin/bash

# This is a personal project and must never deploy or commit with work
# credentials. Both are pinned here because the machine's global git identity
# and SSH key belong to the work account.
FIREBASE_ACCOUNT ?= sskillman@gmail.com
GIT_NAME ?= Shawn Skillman
GIT_EMAIL ?= ssskillman@users.noreply.github.com

.PHONY: check syntax test deploy-dry-run web-test web-build deploy setup-identity

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

deploy: web-build
	@firebase deploy --only hosting --account "$(FIREBASE_ACCOUNT)"

# Repo-local git config is not carried by a clone, so re-run this after cloning
# or the work identity is inherited from the global config.
setup-identity:
	@git config --local user.name "$(GIT_NAME)"
	@git config --local user.email "$(GIT_EMAIL)"
	@git config --local --unset-all credential.helper 2>/dev/null || true
	@git config --local --add credential.helper ""
	@git config --local --add credential.helper '!gh auth git-credential'
	@firebase login:use "$(FIREBASE_ACCOUNT)" >/dev/null 2>&1 || true
	@echo "git:      $$(git config user.name) <$$(git config user.email)>"
	@echo "firebase: $$(firebase login:list 2>/dev/null | sed -n 's/.*Logged in as //p') (this directory only)"

SHELL := /bin/bash

# Machine-local deploy settings, gitignored. This is where ANIMAL_ID_API_ORIGIN
# lives so a plain `make pi-deploy` cannot rebuild /identify without it and
# silently revert the page to "the photo-processing server is offline".
#
# Deliberately not .env: that name is the Pi's /etc/owlcam/owlcam.env template
# (.env.example), and one file feeding two machines invites a config mix-up.
# See deploy.env.example.
-include deploy.env
export ANIMAL_ID_API_ORIGIN

# This is a personal project and must never deploy or commit with work
# credentials. Both are pinned here because the machine's global git identity
# and SSH key belong to the work account.
FIREBASE_ACCOUNT ?= sskillman@gmail.com
GIT_NAME ?= Shawn Skillman
GIT_EMAIL ?= ssskillman@users.noreply.github.com
GITHUB_USER ?= ssskillman

.PHONY: check syntax test deploy-dry-run web-test web-build animal-id-test deploy pi-deploy require-api-origin setup-identity

check: syntax test deploy-dry-run web-test web-build animal-id-test

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
	@python3 -m unittest discover -s pi/tests -p 'test_*.py'

deploy-dry-run:
	@bash pi/scripts/deploy.sh --dry-run

web-test:
	@cd web && uv run --frozen python -m pytest

web-build:
	@cd web && uv run --frozen python build.py

animal-id-test:
	@cd animal_identifier && uv run --frozen pytest

deploy: web-build
	@firebase deploy --only hosting --account "$(FIREBASE_ACCOUNT)"

# Refuses rather than warns: the failure it prevents is invisible on the built
# page, so a warning would be scrolled past and the site shipped offline.
require-api-origin:
	@if [ -z "$(ANIMAL_ID_API_ORIGIN)" ]; then \
		echo "ANIMAL_ID_API_ORIGIN is not set, so /identify would build with no"; \
		echo "API origin and report the photo-processing server as offline."; \
		echo; \
		echo "Set it in deploy.env (see deploy.env.example), or for a one-off:"; \
		echo "  ANIMAL_ID_API_ORIGIN=https://host.tailnet.ts.net:8443 make pi-deploy"; \
		exit 1; \
	fi
	@echo "identify API origin: $(ANIMAL_ID_API_ORIGIN)"

# The Pi serves the page beside the stream so both share one origin, so a web
# change is not live until the built site reaches the Pi.
#
# require-api-origin is first on purpose: prerequisites run left to right, and
# checking after web-build would leave the offline page on disk.
pi-deploy: require-api-origin web-build
	@bash pi/scripts/deploy.sh

# Repo-local git config is not carried by a clone, so re-run this after cloning
# or the work identity is inherited from the global config.
#
# The credential helper names the account explicitly instead of using
# '!gh auth git-credential', which serves whichever account gh happens to be
# switched to. Working in a work repo flips that global, and the next push here
# fails with "Permission to ssskillman/owlcam.git denied to skillman-iterable".
# The leading empty helper is required: it resets the inherited osxkeychain
# helpers, which otherwise answer first and win with the work credential.
setup-identity:
	@git config --local user.name "$(GIT_NAME)"
	@git config --local user.email "$(GIT_EMAIL)"
	@git config --local --unset-all credential.helper 2>/dev/null || true
	@git config --local --add credential.helper ""
	@git config --local --add credential.helper '!f() { test "$$1" = get && printf "username=$(GITHUB_USER)\npassword=%s\n" "$$(gh auth token --user $(GITHUB_USER))"; }; f'
	@firebase login:use "$(FIREBASE_ACCOUNT)" >/dev/null 2>&1 || true
	@echo "git:      $$(git config user.name) <$$(git config user.email)>"
	@echo "github:   $(GITHUB_USER) (pinned, independent of gh's active account)"
	@echo "firebase: $$(firebase login:list 2>/dev/null | sed -n 's/.*Logged in as //p') (this directory only)"

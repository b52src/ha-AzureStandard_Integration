# ──────────────────────────────────────────────────────────────────────────────
# Azure Standard Integration — development helpers
# Usage:
#   make commit MSG="phase 14: description"
#   make release VERSION=0.1.5
#   make push
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: commit release push status

# Default target — show what's pending
status:
	@git status --short
	@echo ""
	@echo "Latest tags:"
	@git tag --list | sort -V | tail -5

# Stage everything and commit with a message
# Usage: make commit MSG="phase 14: what changed"
commit:
	@test -n "$(MSG)" || (echo "ERROR: MSG is required — make commit MSG=\"your message\"" && exit 1)
	git add -A
	git commit -m "$(MSG)"

# Bump manifest.json + CHANGELOG, tag, and push
# Usage: make release VERSION=0.1.5
release:
	@test -n "$(VERSION)" || (echo "ERROR: VERSION is required — make release VERSION=0.1.5" && exit 1)
	@echo "Bumping version to $(VERSION) in manifest.json …"
	@sed -i '' 's/"version": "[^"]*"/"version": "$(VERSION)"/' \
		custom_components/azure_standard/manifest.json
	@echo "Staging manifest.json …"
	git add custom_components/azure_standard/manifest.json
	@# Commit only if there are staged changes (manifest bump)
	git diff --cached --quiet || git commit -m "v$(VERSION): bump manifest version"
	@echo "Tagging v$(VERSION) …"
	git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	$(MAKE) push
	@echo ""
	@echo "✓ Released v$(VERSION) — Forgejo Actions will create the release page."

# Push current branch + all tags
push:
	git push origin main
	git push origin --tags

# Full phase workflow shortcut:
#   make phase MSG="phase 14: description" VERSION=0.1.5
phase: commit release

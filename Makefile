.PHONY: help run dev lint format test deploy

# Default goal
.DEFAULT_GOAL := help

help: ## Show available commands
	@echo "\nAvailable Make commands:\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

run: ## Run Job Hunter AI locally
	uv run python -m job_applicator

lint: ## Run Ruff linter and formatter
	uv run ruff check src --fix
	uv run ruff format src

test: ## Run test suite
	uv run pytest

deploy: ## Automatically bump patch tag and push to trigger CI/CD deploy (or specify TAG=v1.0.0)
	@LATEST_TAG=$$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0"); \
deploy: ## Automatically bump patch tag, create empty release commit, and push to trigger CI/CD deploy (or specify TAG=v1.0.0)
	@LATEST_TAG=$$(git tag -l "v*" --sort=-v:refname | head -n 1); \
	LATEST_TAG=$${LATEST_TAG:-v0.0.0}; \
	if [ -n "$(TAG)" ]; then \
		NEXT_TAG="$(TAG)"; \
	else \
		VERSION=$${LATEST_TAG#v}; \
		MAJOR=$$(echo $$VERSION | cut -d. -f1); \
		MINOR=$$(echo $$VERSION | cut -d. -f2); \
		PATCH=$$(echo $$VERSION | cut -d. -f3); \
		NEXT_PATCH=$$((PATCH + 1)); \
		NEXT_TAG="v$$MAJOR.$$MINOR.$$NEXT_PATCH"; \
	fi; \
	echo "🚀 Previous Tag: $$LATEST_TAG"; \
	echo "🏷️  Creating Next Tag: $$NEXT_TAG"; \
	echo "🚀 Latest Tag: $$LATEST_TAG"; \
	echo "🏷️  Next Release Tag: $$NEXT_TAG"; \
	git commit --allow-empty -m "chore(release): $$NEXT_TAG" && \
	git tag "$$NEXT_TAG" && \
	git push origin HEAD && \
	git push origin "$$NEXT_TAG" && \
	echo "✅ Tag $$NEXT_TAG pushed successfully! GitHub Actions CI/CD deployment started."
	echo "✅ Created release commit and pushed $$NEXT_TAG successfully! CI/CD deploy started."


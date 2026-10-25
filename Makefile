# Shortcuts. Each target is a plain command you can also run by hand (see README.md).
VP := $(shell command -v vp 2>/dev/null || echo $(CURDIR)/frontend/node_modules/.bin/vp)
HATCHET_TENANT := 707d0855-80ab-4e1f-a156-f1c4546cbf52

.PHONY: up down setup hatchet-token migrate superuser api worker web test acceptance check

up:            ## Start Postgres, Redis and Hatchet
	docker compose up -d

down:          ## Stop them (data is kept in volumes)
	docker compose down

setup: up      ## First-time setup: deps, env, migrations, Hatchet token
	cd backend && uv sync
	cd frontend && $(VP) install
	cd acceptance && $(VP) install && $(VP) exec playwright install chromium
	test -f backend/.env || cp backend/.env.example backend/.env
	@grep -q '^FIELD_ENCRYPTION_KEY=.' backend/.env || { \
		KEY=$$(cd backend && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
		sed -i.bak "s|^FIELD_ENCRYPTION_KEY=.*|FIELD_ENCRYPTION_KEY=$$KEY|" backend/.env && rm backend/.env.bak; \
		echo "FIELD_ENCRYPTION_KEY generated in backend/.env"; }
	$(MAKE) migrate hatchet-token

hatchet-token: ## Create a Hatchet API token and write it into backend/.env
	@TOKEN=$$(docker compose exec -T hatchet /hatchet-admin token create --config /config --tenant-id $(HATCHET_TENANT) | tail -1); \
	sed -i.bak "s|^HATCHET_CLIENT_TOKEN=.*|HATCHET_CLIENT_TOKEN=$$TOKEN|" backend/.env && rm backend/.env.bak; \
	echo "HATCHET_CLIENT_TOKEN written to backend/.env"

migrate:
	cd backend && uv run python manage.py migrate

superuser:
	cd backend && uv run python manage.py createsuperuser

api:           ## Django + Channels (Daphne) on :8000
	cd backend && uv run python manage.py runserver 8000

worker:        ## Hatchet worker (restart it after changing task code)
	cd backend && uv run python manage.py hatchet_worker

web:           ## Vite+ dev server on :5173
	cd frontend && $(VP) dev

test:
	cd backend && uv run pytest -q

acceptance:    ## Executable specs (needs make up/api/worker/web running). HEADED=1 to watch
	cd acceptance && $(VP) run test

check:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && $(VP) check
	cd acceptance && $(VP) run typecheck

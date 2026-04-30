# Medical Shift Scheduling System

Institutional medical shift scheduling system for doctors, availability, fairness-aware calendar generation, missions, Telegram operations, WhatsApp notifications, imports, reports, and auditability.

## Project Status

Implementation is starting from the documented specs in `docs/specs/`.

## Local Development

Backend:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/uvicorn backend.app.main:app --reload
```

Bootstrap or reset the admin account:

```bash
./.venv/bin/python -m backend.app.cli reset-admin-password --email admin@example.local
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Tests:

```bash
./scripts/test.sh unit
./scripts/test.sh all
```

Phase-specific tests:

```bash
./scripts/test.sh phase 0
./scripts/test.sh phase 1
```

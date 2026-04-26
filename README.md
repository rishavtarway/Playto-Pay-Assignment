# Playto Pay — KYC Pipeline

A small but real KYC pipeline for Playto Pay. Merchants sign up, complete a
multi-step KYC application (personal details, business details, document
upload), and submit it for review. Reviewers see an oldest-first queue with
SLA flags and can approve, reject, or request more information.

**Stack:** Django 5 + DRF (backend) · React + Vite + Tailwind (frontend) ·
PostgreSQL in prod / SQLite in dev · token auth.

## Test credentials (after `manage.py seed`)

| Role     | Email                  | Password    | Notes                                  |
| -------- | ---------------------- | ----------- | -------------------------------------- |
| Reviewer | reviewer@playto.test   | reviewer123 | Sees the full queue + metrics          |
| Merchant | draft@playto.test      | merchant123 | State = draft, half-filled             |
| Merchant | review@playto.test     | merchant123 | State = under_review, all 3 docs, **AT RISK** (>24h) |

## Local development

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py seed
python manage.py runserver 0.0.0.0:8000

# 2. Frontend (in a second terminal)
cd frontend
npm install
npm run dev    # opens http://localhost:5173 with /api proxied to :8000
```

Open http://localhost:5173 and sign in with one of the seed accounts.

## Run the tests

```bash
cd backend
python -m pytest -q
```

The required test (illegal transition `approved → draft`) lives at
`backend/kyc/tests/test_state_machine.py`.

## Run with Docker (bonus)

```bash
docker compose up --build
# → http://localhost:8000   (API + SPA, seeded)
```

This brings up Postgres, runs migrations, runs the seed command, and serves
the built frontend from the same Django process.

## Deploy to Render

The repo includes `render.yaml`. From the Render dashboard click
**New → Blueprint**, point it at this repo, and Render will create:

- a free **web service** (Django + built React)
- a free **PostgreSQL** instance
- a 1 GB persistent **disk** mounted at `backend/media/` for uploaded files

The build command builds the React bundle and runs migrations + seed, so the
deployed app is ready to log in to immediately.

Set `DJANGO_ALLOWED_HOSTS` to your Render hostname (e.g. `playto-kyc.onrender.com`)
once you have it.

## API tour

All endpoints are prefixed with `/api/v1/`. Errors come back as
`{"error": "<code>", "detail": ...}` with a useful HTTP status.

```
POST /auth/signup/                     # { email, password, role } → { token, user }
POST /auth/login/                      # { email, password } → { token, user }
GET  /auth/me/                         # current user

# Merchant
GET    /submissions/me/                # get-or-create your draft
PATCH  /submissions/me/                # save draft fields
POST   /submissions/me/documents/      # multipart upload (kind, file)
DELETE /submissions/me/documents/<id>/
POST   /submissions/me/submit/         # draft → submitted

# Reviewer
GET  /reviews/queue/                   # oldest-first, with SLA flag
GET  /reviews/<id>/                    # full detail
POST /reviews/<id>/start/              # submitted → under_review (round-robin)
POST /reviews/<id>/approve/
POST /reviews/<id>/reject/             # { reason }
POST /reviews/<id>/request-info/       # { reason }
GET  /reviews/metrics/                 # in_queue, avg wait, 7d approval rate
```

## What's where

```
backend/
  config/                     # settings, urls, custom DRF exception handler
  accounts/                   # User model + auth views
  kyc/
    state_machine.py          # SINGLE source of truth for transitions
    validators.py             # file size + extension + magic-byte sniff
    permissions.py            # IsMerchant, IsReviewer, IsMerchantOwner
    assignment.py             # round-robin reviewer pick (bonus)
    serializers.py
    views.py                  # merchant + reviewer endpoints
    management/commands/seed.py
    tests/                    # state machine, uploads, auth tests
frontend/
  src/
    api/client.js             # axios w/ token interceptor
    auth/                     # AuthContext + ProtectedRoute
    pages/                    # Login, Signup, MerchantWizard, ReviewerDashboard, ReviewerDetail
    components/               # Header, StateBadge, DocumentDropzone (drag-drop)
docker-compose.yml
render.yaml
EXPLAINER.md                  # answers to the five EXPLAINER questions
```

## Bonuses included

- ✅ Docker + docker-compose
- ✅ Real SMTP email on every state change (off by default — set `EMAIL_HOST`)
- ✅ Drag-and-drop document upload
- ✅ Reviewer round-robin assignment

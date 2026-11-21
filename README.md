# TalentIQ — Blind, evidence-led hiring

Hide who a candidate is, quote the proof in their résumé, score it with plain maths — and let the human decide.

- **Blind review:** name, email, phone, university and pronouns are removed before anything is evaluated. The identity is stored encrypted and only shown after you **shortlist**.
- **Evidence, not vibes:** Mistral **Codestral** (`codestral-2508`) quotes the résumé sentence that proves each skill. Python then checks every quote exists *word for word*. Invented claims earn zero.
- **Deterministic score:** Python adds up the points (verified = full weight, partial = half, missing = 0). The same résumé always gets the same score.
- **Works without AI too:** no API key? A simple keyword matcher is used instead.

**Stack:** Django REST + LangGraph (backend) · Next.js + React (frontend) · PostgreSQL / SQLite

> New to the code? Read **[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)** — one page that follows a résumé through the whole system. Every file also starts with a plain-English comment explaining what it does.

---

## Run it on your laptop

You need Python 3.11+ and Node 20+.

```bash
# 1) settings (put your Mistral key in .env — this file is git-ignored)
cp .env.example .env

# 2) backend  -> http://localhost:8000
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo       # sample role + 6 fake candidates
python manage.py runserver

# 3) frontend (new terminal)  -> http://localhost:3000
cd frontend
npm install
npm run dev
```

Or with Docker: `docker compose up --build`.

Run the tests: `cd backend && python manage.py test evaluations`

---

## Deploy for free: Render (API) + Vercel (website)

Do it in this order, because each side needs the other's address.

### 1. API on Render
1. Push this repo to GitHub (see below).
2. Render dashboard → **New → Blueprint** → choose the repo. Render reads `render.yaml`.
3. When asked, paste **`MISTRAL_API_KEY`**. Leave `CORS_ALLOWED_ORIGINS` as a placeholder for now (e.g. `http://localhost:3000`).
4. Wait for the deploy. Open `https://<your-service>.onrender.com/api/health/` — it should say `{"status":"ok"}`.

### 2. Website on Vercel
1. Vercel → **Add New → Project** → import the same repo.
2. Set **Root Directory** to `frontend`.
3. Add environment variable **`NEXT_PUBLIC_API_URL`** = your Render URL (no trailing slash).
4. Deploy. You get an address like `https://talentiq.vercel.app`.

### 3. Connect them
Back on Render → your service → **Environment** → set **`CORS_ALLOWED_ORIGINS`** to your Vercel address → save (it redeploys). Done.

### Free-tier things to know
- Render free services **sleep after 15 minutes idle**; the first visit takes up to about a minute. The website retries automatically and shows a hint.
- Render's free **Postgres expires after 30 days** (and only one is allowed per account). If that bites, delete the `databases:` block and the `DATABASE_URL` entry in `render.yaml`: the app then uses SQLite and re-creates the demo data on every start (uploads don't survive restarts).
- Uploads are limited to 30 per hour per visitor (`UPLOAD_RATE_LIMIT`) so strangers can't drain your Mistral credits.

---

## Settings (environment variables)

| Variable | What it does |
|---|---|
| `MISTRAL_API_KEY` | Turns on Codestral. Empty = offline keyword matcher |
| `MISTRAL_MODEL` | Default `codestral-2508` |
| `DJANGO_SECRET_KEY` | Keep secret. Don't change it after data exists |
| `PII_ENCRYPTION_KEY` | Optional. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Postgres address. Empty = local SQLite file |
| `CORS_ALLOWED_ORIGINS` | Website addresses allowed to call the API |
| `NEXT_PUBLIC_API_URL` | (frontend) where the API lives |
| `UPLOAD_RATE_LIMIT` | Default `30/hour` |
| `SEED_DEMO` | `0` = don't create demo data on start |

## API

`GET /api/health/` · `GET|POST /api/jobs/` · `GET /api/jobs/<id>/` · `POST /api/jobs/<id>/applications/` (multipart `resume`) · `GET /api/applications/<id>/` · `POST /api/applications/<id>/decision/` with `{"decision":"shortlist"|"reject"}`

## Not production-ready (on purpose)

This is a portfolio project. Before real hiring use: add login and roles, retention/deletion rules, audited identity reveal, managed encryption keys, fairness testing and a compliance review. Demo résumés are fictional — don't upload real candidate data to a public demo.

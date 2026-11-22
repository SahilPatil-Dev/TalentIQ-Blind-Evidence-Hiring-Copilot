# TalentIQ — Blind, evidence-led hiring

TalentIQ helps a hiring team screen résumés **without seeing who the candidate is**. It hides identity, asks an AI to quote the exact résumé sentence that proves each skill, checks the quote is real, and scores with plain maths. A person makes every decision.

**Live:** https://frontend-liard-three-63.vercel.app

## What it does

**Hiring**
- **Blind review:** name, email, phone, university and pronouns are removed before anything is evaluated.
- **Evidence matrix:** every point comes from a quoted résumé sentence. No quote, no points.
- **Verified quotes:** the AI only suggests quotes; Python checks each one exists word for word and does the scoring, so the same résumé always gets the same score.
- **Ranked candidates and interview questions** aimed at the gaps.
- **Human decision:** shortlist or archive, always with a written reason.

**Governance**
- **Login and roles:** Administrator, Recruiter, Reviewer (read-only), Auditor (no candidate data). The first account becomes admin; later accounts need approval. Lockout after 5 wrong passwords.
- **Audited identity reveal:** only for shortlisted candidates, with a reason; who, when and why are logged.
- **Audit log:** append-only and hash-chained, with an integrity check and CSV export.
- **Retention and deletion:** per-outcome limits, automatic cleanup, manual erasure, legal hold.
- **Managed encryption keys:** identities are encrypted with versioned data keys locked by a master key; rotate and re-encrypt from the UI.
- **Fairness testing:** changes names, universities and pronouns on one résumé and checks the score cannot change; plus a four-fifths-rule calculator.
- **Compliance review:** a live checklist of controls plus items only people can confirm. Not legal advice.

## Tech

Django 5 + Django REST Framework · LangGraph · Mistral Codestral · PostgreSQL (SQLite locally) · Fernet encryption (`cryptography`) · PyMuPDF · Next.js 15 + React 19 + TypeScript · Render (API) · Vercel (website) · GitHub Actions CI

## Run it locally

Needs Python 3.11+ and Node 20+.

```bash
cp .env.example .env          # add MISTRAL_API_KEY (optional: works offline without it)

# backend -> http://localhost:8000
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver

# frontend (new terminal) -> http://localhost:3000
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 (the landing page), click Get started, register (you become the admin), and sign in. Or run everything with `docker compose up --build`.

Tests: `cd backend && python manage.py test evaluations`

## Deploy

- **API on Render:** New → Blueprint → pick this repo (`render.yaml`). Set `MISTRAL_API_KEY`, `DATABASE_URL`, `KEY_ENCRYPTION_KEY` and `CORS_ALLOWED_ORIGINS` (your Vercel URL).
- **Website on Vercel:** import the repo, set Root Directory to `frontend`, set `NEXT_PUBLIC_API_URL` to your Render URL.
- Generate the master key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Before real hiring

Software can't do these for you: a data protection impact assessment, telling candidates an automated tool is used, data processing agreements with Mistral, Render and Vercel, and an independent bias audit where the law requires one. Redaction is pattern-based and misses some details (the Fairness page lists them). Demo résumés are fictional; don't upload real candidate data to a public demo.

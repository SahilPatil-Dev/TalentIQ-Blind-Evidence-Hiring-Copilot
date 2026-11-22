# How TalentIQ works (one page)

## The big picture

```
 Browser (Next.js, /frontend)                 API (Django, /backend)
 ───────────────────────────                  ─────────────────────────────
  Dashboard  ── GET  /api/jobs/ ───────────▶  views.jobs
  New role   ── POST /api/jobs/ ───────────▶  serializer checks weights = 100
  Role page  ── GET  /api/jobs/3/ ─────────▶  role + ranked candidates
  Drop a CV  ── POST /api/jobs/3/applications ▶ THE MAIN FLOW (below)
  Candidate  ── GET  /api/applications/7/ ──▶  evidence (+ identity if shortlisted)
  Shortlist  ── POST /api/applications/7/decision/
```

## The main flow: what happens to one résumé

`backend/evaluations/views.py → upload_application`

1. **Read the file** (PDF / TXT / MD) into text.
2. **Redact** — `services/privacy.py`: name, email, phone, university and pronouns are replaced with `[EMAIL_REDACTED]` etc. The removed values are **encrypted** and saved separately.
3. **Evaluate** — `services/evaluator.py` (a LangGraph "assembly line"):
   - `extract`  ask Codestral for one exact quote per rubric criterion (`services/mistral.py`). No API key? use keyword matching.
   - `validate` is every quote really in the résumé, word for word?
   - `retry`    if not, ask once more.
   - `score`    drop anything still unsupported, add up the points **in Python**, write 3 interview questions.
4. **Save** the candidate as *Needs review*. The response contains **no identity**.
5. **You decide** in the UI. A decision needs a written reason. After a **Shortlist**, an admin or recruiter can call `views.reveal_identity` with a reason; the API logs it (`services/audit.py`) before decrypting and returning the identity. Archived candidates stay sealed.

**Why the AI doesn't score:** models can invent facts. So the AI only *suggests quotes*; Python verifies them and does the arithmetic. Same résumé → same score.

## Where things live

| Want to change… | Edit |
|---|---|
| How scores are calculated | `backend/evaluations/services/evaluator.py` → `calculate_score` |
| What the AI is told | `backend/evaluations/services/mistral.py` → `SYSTEM_PROMPT` |
| What gets redacted | `backend/evaluations/services/privacy.py` |
| API endpoints | `backend/evaluations/urls.py` + `views.py` |
| Settings / keys | `backend/talentiq/settings.py` (values come from `.env`) |
| Demo data | `backend/evaluations/management/commands/seed_demo.py` |
| Colours, fonts, spacing | top of `frontend/src/app/globals.css` (`:root`) |
| A page | `frontend/src/app/**/page.tsx` |
| Calls to the API | `frontend/src/lib/api.ts` |
| Animations | `globals.css` section 10, plus `CountUp.tsx`, `ScoreRing.tsx`, `RedactionDemo.tsx` |

## Frontend flow in one sentence

`layout.tsx` wraps every page in the sidebar (`Shell`) → each `page.tsx` calls `api.*` when it opens → shows a skeleton while loading, an error box if it fails, otherwise the data.

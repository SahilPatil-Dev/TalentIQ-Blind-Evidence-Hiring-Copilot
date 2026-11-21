#!/usr/bin/env bash
# Publishes this project to a NEW repo under your GitHub account.
#
# Needs: git, and ONE of:
#   (a) the GitHub CLI `gh`, logged in as SahilPatil-Dev  ->  gh auth login
#   (b) a repo you created by hand at https://github.com/new (empty, no README)
#
# Run from the project root:   bash scripts/publish-to-github.sh
set -euo pipefail

OWNER="SahilPatil-Dev"
REPO="TalentIQ-Blind-Evidence-Hiring-Copilot"

cd "$(dirname "$0")/.."

# Safety: the .env file holds your API key and must never be uploaded.
if git check-ignore -q .env 2>/dev/null || grep -qx ".env" .gitignore; then :; else
  echo "Refusing to continue: .env is not in .gitignore"; exit 1
fi

[ -d .git ] || git init -b main
git add -A
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "Refusing to continue: .env is staged!"; exit 1
fi
git commit -m "TalentIQ: blind, evidence-led hiring (Django + LangGraph + Next.js)" || true

if command -v gh >/dev/null 2>&1; then
  gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push \
    --description "Blind, evidence-led hiring: redact identity, quote the proof, score with plain maths. Django + LangGraph + Codestral + Next.js."
else
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$OWNER/$REPO.git"
  git branch -M main
  git push -u origin main
fi
echo "Done: https://github.com/$OWNER/$REPO"

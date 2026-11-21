#!/bin/sh
# Starts the API. Used by Docker AND by Render, so there is one way to run it.
#   1. create / update the database tables
#   2. add the sample role + candidates (skip with SEED_DEMO=0)
#   3. run the web server (gunicorn) on the port the host gives us
set -e

python manage.py migrate --noinput

if [ "${SEED_DEMO:-1}" = "1" ]; then
  python manage.py seed_demo
fi

# 1 worker + 4 threads keeps memory low enough for Render's free 512 MB.
# --timeout 120 gives the AI model plenty of time to answer.
exec gunicorn talentiq.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 1 --threads 4 --timeout 120

#!/usr/bin/env bash
# build.sh — runs on Render/Railway before start command
set -e

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Applying migrations ==="
python manage.py migrate --run-syncdb

echo "=== Seeding demo data ==="
python manage.py seed_demo || echo "Seed already done or failed — continuing"

echo "=== Build complete ==="

#!/usr/bin/env bash
# Basin deployment script — run after pushing code changes to git.
# Run as root or as a user with sudo on the appliance.
set -euo pipefail

BASIN_HOME="/opt/basin"
REPO_DIR="$BASIN_HOME/repo"
VENV="$BASIN_HOME/venv"

echo "==> Pulling latest code"
git -C "$REPO_DIR" pull origin main

echo "==> Installing/updating Python dependencies"
source "$VENV/bin/activate"
pip install -q -r "$REPO_DIR/backend/requirements.txt"

echo "==> Running database migrations"
cd "$REPO_DIR/backend"
alembic upgrade head

echo "==> Building frontend"
cd "$REPO_DIR/frontend"
npm ci --silent
npm run build

echo "==> Restarting services"
systemctl restart basin-api basin-worker basin-beat

echo "==> Deploy complete ($(git -C "$REPO_DIR" log -1 --format='%h %s'))"

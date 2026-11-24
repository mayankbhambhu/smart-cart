#!/usr/bin/env bash
# Start the API + the website locally (SQLite, sandbox payments).
#   backend/api  -> the REST + WebSocket API (port 8000), shared by the website and the phone app
#   backend/web  -> the website's Python server (port 8001): shop at /, Store Operations at /store,
#                   Admin at /admin, one login page for everyone
#   web/         -> the dashboards' HTML templates, CSS and JS
#   app/         -> the phone app (started separately with Expo)
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -q -r backend/api/requirements.txt -r backend/web/requirements.txt; }
(cd backend/api && ../../.venv/bin/python -m app.seed)
trap 'kill 0' EXIT
# --host 0.0.0.0 lets phones on the same Wi-Fi reach the API (needed by the mobile app)
# --reload-dir keeps the auto-reloader away from .venv (otherwise it restarts in a loop)
(cd backend/api && ../../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app) &
(cd backend && ../.venv/bin/uvicorn web.main:app --port 8001 --reload --reload-dir web --reload-dir ../web) &
sleep 2
echo ""
echo "  Website          http://localhost:8001   (one login page; it opens the right section for each person)"
echo "    shoppers       asha@example.com, rohan@example.com                          -> the shop"
echo "    store staff    owner.blr01@ / manager.blr01@ / floor1.blr01@ / worker1.blr01@freshflow.app -> /store"
echo "    admin          admin@freshflow.app                                           -> /admin"
echo "  API + docs       http://localhost:8000/docs"
echo "  Password for every demo account: Password@123"
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)
if [ -n "$LAN_IP" ]; then
  echo ""
  echo "  Mobile app: in a second terminal run   cd app && npm install && npx expo start"
  echo "  (phone and this computer on the same Wi-Fi; the app finds the API at http://$LAN_IP:8000)"
fi
wait

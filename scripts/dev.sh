#!/usr/bin/env bash
# Start the API + all three dashboards locally (SQLite, sandbox payments).
set -e
# --reload-dir keeps the auto-reloader away from .venv (otherwise it restarts in a loop)
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -q -r backend/requirements.txt -r web/requirements.txt; }
(cd backend && ../.venv/bin/python -m app.seed)
trap 'kill 0' EXIT
# --host 0.0.0.0 lets phones on the same Wi-Fi reach the API (needed by the mobile app)
(cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app) &
.venv/bin/uvicorn web.customer.app:app --port 8001 --reload --reload-dir web &
.venv/bin/uvicorn web.store.app:app --port 8002 --reload --reload-dir web &
.venv/bin/uvicorn web.admin.app:app --port 8003 --reload --reload-dir web &
sleep 2
echo ""
echo "  API + docs       http://localhost:8000/docs"
echo "  Customer         http://localhost:8001   (asha@example.com)"
echo "  Store operations http://localhost:8002   (owner.blr01@ / manager.blr01@ / floor1.blr01@ / worker1.blr01@freshflow.app)"
echo "  Admin            http://localhost:8003   (admin@freshflow.app)"
echo "  Password for every demo account: Password@123"
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)
if [ -n "$LAN_IP" ]; then
  echo ""
  echo "  Mobile app: in a second terminal run   cd mobile && npm install && npx expo start"
  echo "  (phone and this computer on the same Wi-Fi; the app finds the API at http://$LAN_IP:8000)"
fi
wait

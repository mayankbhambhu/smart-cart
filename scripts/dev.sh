#!/usr/bin/env bash
# Start the API + all three dashboards locally (SQLite, sandbox payments).
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -q -r backend/requirements.txt -r web/requirements.txt; }
(cd backend && ../.venv/bin/python -m app.seed)
trap 'kill 0' EXIT
(cd backend && ../.venv/bin/uvicorn app.main:app --port 8000 --reload) &
.venv/bin/uvicorn web.customer.app:app --port 8001 --reload &
.venv/bin/uvicorn web.store.app:app --port 8002 --reload &
.venv/bin/uvicorn web.admin.app:app --port 8003 --reload &
sleep 2
echo ""
echo "  API + docs       http://localhost:8000/docs"
echo "  Customer         http://localhost:8001   (asha@example.com)"
echo "  Store operations http://localhost:8002   (owner.blr01@ / manager.blr01@ / floor1.blr01@ / worker1.blr01@freshflow.app)"
echo "  Admin            http://localhost:8003   (admin@freshflow.app)"
echo "  Password for every demo account: Password@123"
wait

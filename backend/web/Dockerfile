# The website: shop at /, Store Operations at /store, Admin at /admin, one login page.
# Build from the repository root (it needs backend/web for the server and web/ for the pages):
#   docker build -f backend/web/Dockerfile .
FROM python:3.13-slim
WORKDIR /srv
COPY backend/web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/web ./web
COPY web ./ui
ENV PORT=8001 WEB_UI_DIR=/srv/ui
CMD ["sh", "-c", "uvicorn web.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]

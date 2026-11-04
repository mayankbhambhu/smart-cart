# One image, three dashboards: set APP=customer | store | admin
FROM python:3.13-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./web
ENV APP=customer PORT=8001
CMD ["sh", "-c", "uvicorn web.${APP}.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]

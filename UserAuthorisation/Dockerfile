# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY UserAuthorisation/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY UserAuthorisation /app
RUN rm -f /app/.env || true
EXPOSE 8002
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8002}"]

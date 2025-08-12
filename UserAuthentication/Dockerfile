# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
# Do not bake .env into images (use Railway env vars)
RUN rm -f /app/.env || true
EXPOSE 8001
# Use Railway-assigned $PORT if present
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}"]

# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY UserGroupManagement/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY UserGroupManagement /app
RUN rm -f /app/.env || true
EXPOSE 8003
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8003}"]

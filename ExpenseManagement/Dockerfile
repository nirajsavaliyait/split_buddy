# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY ExpenseManagement/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ExpenseManagement /app
RUN rm -f /app/.env || true
EXPOSE 8004
CMD ["sh", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8004}"]

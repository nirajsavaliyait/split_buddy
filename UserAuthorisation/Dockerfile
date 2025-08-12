# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
RUN rm -f /app/.env || true
# Railway sets PORT; expose 8080 for clarity (container binds to $PORT)
EXPOSE 8080
CMD ["python", "start.py"]

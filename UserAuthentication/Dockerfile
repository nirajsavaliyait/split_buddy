# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY UserAuthentication/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY UserAuthentication /app
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

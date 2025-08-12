# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY UserGroupManagement/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY UserGroupManagement /app
EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]

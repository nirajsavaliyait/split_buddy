# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY ExpenseManagement/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ExpenseManagement /app
EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]

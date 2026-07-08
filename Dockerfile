# Single image serves BOTH the API service (default CMD) and the hourly
# pipeline Cloud Run Job (command overridden to `python pipeline.py`).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    BQ_DATASET=vaayu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# API service by default. The Cloud Run Job overrides this with pipeline.py.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}

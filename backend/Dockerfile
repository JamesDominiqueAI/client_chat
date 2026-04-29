FROM python:3.12-slim

WORKDIR /app

COPY backend/api/pyproject.toml /app/backend/api/pyproject.toml
COPY backend/api/requirements.txt /app/backend/api/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/api/requirements.txt

COPY backend /app/backend
COPY data /app/data

EXPOSE 8010
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8010"]

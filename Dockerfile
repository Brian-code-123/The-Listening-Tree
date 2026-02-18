# Lightweight single-stage build — no ML models needed
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY run.py translations.py ./
COPY templates/ templates/
COPY static/ static/

EXPOSE 5000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "5000"]
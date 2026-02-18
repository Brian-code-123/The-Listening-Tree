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

CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120"]
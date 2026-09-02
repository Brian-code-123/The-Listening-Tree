# ===========================================================================
# The Listening Tree — Dockerfile (production)
#
# Single-stage build.  No ML models are bundled; voice recognition
# is handled client-side by the browser's Web Speech API.
#
# Build:  docker build -t the-listening-tree .
# Run:    docker run -p 5000:5000 the-listening-tree
# ===========================================================================

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY run.py translations.py ./
COPY app/ app/
COPY templates/ templates/
COPY static/ static/

EXPOSE 5000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "5000"]
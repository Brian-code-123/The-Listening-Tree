# ===========================================================================\n# The Listening Tree — Dockerfile (production)\n#\n# Single-stage build.  No ML models are bundled; voice recognition\n# is handled client-side by the browser's Web Speech API.\n#\n# Build:  docker build -t the-listening-tree .\n# Run:    docker run -p 5000:5000 the-listening-tree\n# ===========================================================================

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY run.py translations.py ./
COPY templates/ templates/
COPY static/ static/

EXPOSE 5000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "5000"]
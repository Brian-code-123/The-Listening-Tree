# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies (added git, wget, unzip here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    git \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Vosk model (moved to builder stage)
RUN mkdir -p voice_models && \
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -O model.zip && \
    unzip model.zip -d voice_models && \
    rm model.zip

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Copy system deps from builder
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/lib /usr/lib

# Copy Python deps from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Vosk model from builder
COPY --from=builder /app/voice_models /app/voice_models

# Copy app code
COPY . .

EXPOSE 5000

CMD ["python run.py"]
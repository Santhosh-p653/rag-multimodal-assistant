FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential for general building, ffmpeg for audio transcription)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding and whisper models during build phase for instant container startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', compute_type='int8', device='cpu')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
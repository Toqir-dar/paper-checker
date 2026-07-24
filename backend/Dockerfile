FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs Docker containers as UID 1000 with a writable
# home directory only — root-owned cache/install paths fail at runtime.
RUN useradd -m -u 1000 appuser
USER appuser
WORKDIR /home/appuser/app

ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH \
    HF_HOME=/home/appuser/.cache/huggingface

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=appuser:appuser app ./app

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]

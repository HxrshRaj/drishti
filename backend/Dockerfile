FROM python:3.11-slim

WORKDIR /app

# CPU-only torch first (smaller image, matches this project's default
# no-GPU environment; see docs/benchmarks.md for the GPU path).
RUN pip install --no-cache-dir torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV DEVICE=cpu \
    DATA_SOPS_DIR=/data/sops \
    DATA_IMAGES_DIR=/data/images \
    DATA_LABELS_FILE=/data/labels/labels.jsonl \
    MEMORY_DB_PATH=/data/memory/drishti.db

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

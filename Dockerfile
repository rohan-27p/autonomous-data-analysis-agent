FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AUTODATA_ENV=production \
    AUTODATA_STORAGE_DIR=/tmp/autodata/runtime \
    AUTODATA_UPLOAD_DIR=/tmp/autodata/uploads

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && \
    pip install .

EXPOSE 7860

CMD ["uvicorn", "autodata_agent.api.app:app", "--host", "0.0.0.0", "--port", "7860"]

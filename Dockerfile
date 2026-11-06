FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    POLARS_MAX_THREADS=4 \
    POLARS_CSV_CHUNK_SIZE=4194304 \
    POLARS_CSV_CHUNK_PREFETCH_LIMIT=2 \
    POLARS_IDEAL_MORSEL_SIZE=50000 \
    INPUT_CSV_PATH=/app/ad_data.csv \
    OUTPUT_DIR=/output

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

CMD ["sleep", "infinity"]

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    POLARS_MAX_THREADS=4 \
    INPUT_CSV_PATH=/app/ad_data.csv \
    OUTPUT_DIR=/output

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY ad_data.csv ./ad_data.csv

RUN python -m pip install --no-cache-dir .

CMD ["flinter-challenge"]

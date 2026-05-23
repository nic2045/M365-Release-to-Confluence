# Single image that can run either the batch CLI or the review UI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".[all]"

# Run as a non-root user; persist state/changelog/review on /data.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser /data
USER appuser
WORKDIR /data

EXPOSE 8765

# Default: show help. Override the command for batch runs or the UI, e.g.:
#   docker run --env-file .env -v $PWD/data:/data IMAGE \
#     m365-to-confluence --source roadmap --state-file /data/m365_state.json
#   docker run -p 8765:8765 -v $PWD/data:/data IMAGE \
#     m365-to-confluence-ui --host 0.0.0.0 --review-file /data/review.json
CMD ["m365-to-confluence", "--help"]

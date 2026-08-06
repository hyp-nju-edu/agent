FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY sentinel/ sentinel/

RUN pip install --no-cache-dir ".[all]"

COPY sentinel/server/static/ static/

ENV SENTINEL_WORKSPACE=/workspace
RUN mkdir -p /workspace

EXPOSE 8000

CMD ["uvicorn", "sentinel.server.app:app", "--host", "0.0.0.0", "--port", "8000"]

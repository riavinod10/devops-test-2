# Multi-stage build:
#   base    -> runtime dependencies
#   test    -> base + dev deps + tests (used by Jenkins: docker build --target test)
#   runtime -> slim, non-root production image (default target)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY pytest.ini .
COPY app ./app
COPY tests ./tests
RUN python -m compileall -q app
CMD ["pytest", "-v", "--junitxml=reports/junit.xml"]

FROM base AS runtime
ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION} \
    APP_ENV=docker \
    PORT=5000
RUN useradd --system --uid 10001 --no-create-home appuser
COPY app ./app
USER 10001
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"
# Single worker keeps the in-memory store consistent; threads give concurrency.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app.main:app"]

# Editorial review app (forage serve), built for Fly.io.
#
# Artifacts are baked in, and individual books can be overlaid from the volume:
#   /app/artifacts  alignments + trimmed plans, versioned with the deploy
#   /app/books      trimmed book metadata (title, author)
#   /data/artifacts per-book artifact overrides, refreshed without redeploy
#   /data/books     per-book metadata overrides, refreshed without redeploy
#   /data           Fly volume: the comment database and published edits.json
#
# Build the artifact payload first — the image must not carry all of work/:
#   python scripts/package_review_artifacts.py
#
# Then:
#   fly launch --no-deploy          # once, to create the app
#   fly volumes create forage_review_data --size 1
#   fly secrets set FORAGE_SECRET_KEY=... FORAGE_REVIEW_TOKEN=... FORAGE_ADMIN_TOKEN=...
#   fly deploy
#
# Locally the same image runs with:
#   docker run -p 8000:8000 -e FORAGE_SECRET_KEY=dev -e FORAGE_REVIEW_TOKEN=dev \
#     -v forage-review:/data forage-review

FROM python:3.12-slim

# PIP_DEFAULT_TIMEOUT / PIP_RETRIES: remote builders drop connections
# mid-download; ride it out rather than failing a deploy on one slow wheel.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=8 \
    FORAGE_WORK_DIR=/app/artifacts \
    FORAGE_BOOKS_DIR=/app/books \
    FORAGE_ARTIFACT_OVERLAY_DIR=/data/artifacts \
    FORAGE_BOOKS_OVERLAY_DIR=/data/books \
    FORAGE_REVIEW_DB=/data/review.db \
    FORAGE_EDITS_DIR=/data/edits

WORKDIR /app

COPY pyproject.toml README.md ./
COPY forage ./forage
COPY prompts ./prompts
COPY spec ./spec

# The review app reads JSON off disk and serves HTML: it needs fastapi and
# uvicorn, and none of the pipeline's model SDKs or parsing stack. Installing
# the package without its dependencies keeps the image small and the build
# fast. (`epub_reader` is the only webapp-reachable module that imports
# anything heavy, and it does so lazily inside a property nothing here calls.)
#
# Build with --build-arg INSTALL_MODE=full once pipeline stages move behind the
# admin token — that installs everything the CLI needs.
#
# The retry loop is not paranoia: a dropped connection mid-wheel surfaces as a
# hash mismatch, which pip's own PIP_RETRIES does not cover because it happens
# after the download completes.
ARG INSTALL_MODE=web
RUN set -e; \
    install() { \
        if [ "$INSTALL_MODE" = "full" ]; then \
            pip install ".[web]"; \
        else \
            pip install --no-deps . && pip install fastapi "uvicorn[standard]"; \
        fi; \
    }; \
    for attempt in 1 2 3 4; do \
        if install; then exit 0; fi; \
        echo "pip install failed (attempt $attempt) — retrying"; \
        sleep 10; \
    done; \
    exit 1

# Produced by scripts/package_review_artifacts.py; a few MB, not all of work/.
COPY deploy/artifacts ./artifacts
COPY deploy/books ./books

EXPOSE 8000

# Runs as root so the mounted volume (root-owned by default on Fly) is
# writable without an ownership dance at boot. The VM is single-tenant.
#
# --proxy-headers/--forwarded-allow-ips: TLS terminates at Fly's proxy, so
# uvicorn's own view of scheme and client address needs the forwarded headers
# too. The app reads them itself (FORAGE_TRUST_PROXY) — this keeps the ASGI
# scope honest for anything that consults it directly, such as access logs.
# One worker: SQLite is a single file and the artifact read path is cached
# per process. Scale by region, not by machine — see fly.toml.
CMD ["uvicorn", "forage.webapp.app:get_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]

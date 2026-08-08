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

# gosu drops privileges in the entrypoint after the volume is chowned; the
# service account owns nothing else in the image.
RUN set -e; \
    apt-get update; \
    apt-get install -y --no-install-recommends gosu; \
    rm -rf /var/lib/apt/lists/*; \
    useradd --system --uid 10001 --create-home forage

WORKDIR /app

COPY pyproject.toml README.md requirements-web.txt ./
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
# Web mode installs from requirements-web.txt rather than resolving fastapi and
# uvicorn fresh: an unpinned build ships whatever PyPI served that minute, and
# a bad release would reach production with nothing in the diff to show it.
# Regeneration instructions are in the header of that file.
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
            pip install --no-deps . && pip install -r requirements-web.txt; \
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

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

# The entrypoint starts as root only long enough to take ownership of the
# mounted volume, then hands off to the `forage` account: the process parsing
# request bodies from the open internet has no business running as uid 0, even
# on a single-tenant VM.
#
# --proxy-headers/--forwarded-allow-ips: TLS terminates at Fly's proxy, so
# uvicorn's own view of scheme and client address needs the forwarded headers
# too. The app reads them itself (FORAGE_TRUST_PROXY) — this keeps the ASGI
# scope honest for anything that consults it directly, such as access logs.
# One worker: SQLite is a single file and the artifact read path is cached
# per process. Scale by region, not by machine — see fly.toml.
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "forage.webapp.app:get_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]

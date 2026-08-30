FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN bash bootstrap_upstreams.sh \
    && .venv-stanford/bin/python init_cognition.py

CMD ["bash", "runtime.sh"]

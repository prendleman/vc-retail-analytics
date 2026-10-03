# Always-on host for VC Retail Analytics (Fly.io / any Docker host).
# Runs the stdlib app + Cloudflare Tunnel so vc.datasharkbi.com does not need your laptop.
FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && curl -fsSL -o /usr/local/bin/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  && chmod +x /usr/local/bin/cloudflared

# Snowflake connector so the hosted app can offer the Snowflake backend toggle (credential via Fly secrets).
COPY requirements-cloud.txt ./requirements-cloud.txt
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY app ./app
COPY scripts/start_hosted.sh ./scripts/start_hosted.sh
COPY sql ./sql
RUN chmod +x ./scripts/start_hosted.sh \
  && mkdir -p /app/data

ENV HOST=0.0.0.0
ENV PORT=8770
ENV PYTHONUNBUFFERED=1

EXPOSE 8770
CMD ["./scripts/start_hosted.sh"]

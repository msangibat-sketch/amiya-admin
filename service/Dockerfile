FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget unzip && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Download the compressed asset library (spreads/letters/fonts/caption data)
# from the GitHub Release, since it's too large to commit directly to the repo.
RUN wget -q "https://github.com/msangibat-sketch/amiya-admin/releases/download/assets-v3/amiya-assets-20260814T034835Z-1-001.zip" -O /tmp/assets.zip \
    && mkdir -p /app/assets \
    && unzip -q /tmp/assets.zip -d /tmp/assets_extracted \
    && (cp -r /tmp/assets_extracted/amiya-assets/* /app/assets/ || cp -r /tmp/assets_extracted/*/* /app/assets/) \
    && rm -rf /tmp/assets.zip /tmp/assets_extracted

ENV ASSET_ROOT=/app/assets
ENV OUTPUT_ROOT=/app/output
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "main.py"]

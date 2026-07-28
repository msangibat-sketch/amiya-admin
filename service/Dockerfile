FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Asset library gets baked in at build time here (or synced at startup --
# see sync_assets() in main.py if you'd rather pull from cloud storage).
# For now this assumes /app/assets is populated before/during the build.

ENV ASSET_ROOT=/app/assets
ENV OUTPUT_ROOT=/app/output

EXPOSE 8000
CMD ["python", "main.py"]

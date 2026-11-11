FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# System deps (optional minimal) and Debian security updates newer than the base image
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Install deps
COPY requirements.txt .
# pip is only needed for the build; removing it keeps its CVEs out of the image.
RUN pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip uninstall -y pip

# Copy app
COPY . .

EXPOSE 8000

# Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

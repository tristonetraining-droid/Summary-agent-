FROM python:3.12-slim

WORKDIR /app

# System deps for Chromium + pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 libfontconfig1 \
    fonts-liberation wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install only Chromium (skip Firefox + WebKit)
RUN playwright install chromium

# Copy source
COPY . .

# Create necessary directories
RUN mkdir -p samples output

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn service:app --host 0.0.0.0 --port ${PORT:-8000}"]

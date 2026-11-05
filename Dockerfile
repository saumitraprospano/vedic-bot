FROM python:3.12-slim

WORKDIR /app

# Install essential build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Set default port
ENV PORT=10000
EXPOSE 10000

# Start 1 Gunicorn worker with multiple threads (strictly 1 trading thread instance)
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 0 app:app

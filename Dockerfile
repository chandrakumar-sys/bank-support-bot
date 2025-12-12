# ---- Base Image ----
FROM python:3.12-slim

# ---- Set working directory ----
WORKDIR /app

# ---- Install system dependencies ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# ---- Copy project files ----
COPY requirements.txt /app/requirements.txt
COPY app /app/app

# ---- Install Python dependencies ----
RUN pip install --no-cache-dir -r /app/requirements.txt

# ---- Create log directory ----
RUN mkdir -p /var/log && touch /var/log/bankbot.log

# ---- Environment variables ----
ENV PYTHONUNBUFFERED=1
ENV LOG_FILE=/var/log/bankbot.log

# ---- Start the bot ----
CMD ["python", "app/main.py"]

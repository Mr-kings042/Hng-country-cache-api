# Use an official lightweight Python image
FROM python:3.10-slim

WORKDIR /app

# Install system deps required for Pillow and common wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Upgrade pip and install Python dependencies used by the project
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
       fastapi \
       "uvicorn[standard]" \
       sqlalchemy \
       aiosqlite \
       aiomysql \
       httpx \
       python-dotenv \
       pillow

# Expose app port
EXPOSE 8000

# Run the app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
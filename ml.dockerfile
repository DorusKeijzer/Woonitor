FROM python:3.12-slim

# Install system dependencies (for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml poetry.lock ./

# Configure Poetry to install to system
RUN poetry config virtualenvs.create false

# Install only writer deps
RUN poetry install --with ml --no-root --no-interaction --no-ansi

# Copy application code
COPY . .

# Default command
CMD ["python", "machine_learning/predict_price.py"]


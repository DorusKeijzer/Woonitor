# scrapers/Dockerfile
FROM python:3.11-slim

# Install Poetry
RUN pip install poetry

# Set workdir
WORKDIR /app

# Copy poetry files first for caching
COPY pyproject.toml poetry.lock ./

# Install dependencies without dev
RUN poetry config virtualenvs.create false \
 && poetry install --no-root --no-dev

# Copy your actual source code
COPY src/ ./src/


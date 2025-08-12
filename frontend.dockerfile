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

# Install only dashboard deps
RUN poetry install --only default,dashboard --no-root --no-interaction --no-ansi

# Copy the Streamlit app code
COPY dashboard/ .

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app
CMD ["poetry", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]


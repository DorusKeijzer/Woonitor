FROM python:3.12

# Install Poetry
RUN pip install poetry

# Set working directory
WORKDIR /app

# Copy pyproject.toml and poetry.lock first (for better caching)
COPY pyproject.toml poetry.lock ./

# Configure Poetry to not create a virtual environment (install directly to system)
RUN poetry config virtualenvs.create false

# Install dependencies directly to the system Python
RUN poetry install --no-root
# Copy the rest of your application code
COPY . .


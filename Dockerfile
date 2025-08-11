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

# Install Playwright browsers
RUN playwright install --with-deps

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxrandr2 libgbm1 libpangocairo-1.0-0 libgtk-3-0 \
    libasound2 libxdamage1 libxfixes3 libxshmfence1 libxshmfence1 \
    xvfb xauth \
    fonts-liberation fonts-noto-color-emoji fonts-noto fonts-freefont-ttf \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the rest of your application code
COPY . .

# Simple command using system Python
CMD ["bash", "-c", "Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99 && python scrapers/crawler.py"]

FROM python:3.12-slim

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxrandr2 libgbm1 libpangocairo-1.0-0 libgtk-3-0 \
    libasound2 libxdamage1 libxfixes3 libxshmfence1 xvfb xauth \
    fonts-liberation fonts-noto-color-emoji fonts-noto fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml poetry.lock ./

# Configure Poetry to install to system
RUN poetry config virtualenvs.create false

# Install only scraper deps
RUN poetry install --with scraper --no-root --no-interaction --no-ansi

# Install Playwright browsers
RUN playwright install --with-deps

# Copy application code
COPY . .

# Set default command
CMD ["bash", "-c", "Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99 && python scrapers/crawler.py"]


# Use a full-featured Python base image for wider package availability.
FROM python:3.12

# Install system dependencies for Playwright, a virtual display server, and fonts.
RUN apt-get update && apt-get install -y \
    curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libgbm1 libpangocairo-1.0-0 \
    libgtk-3-0 libasound2 libxdamage1 libxfixes3 libxshmfence1 libglu1-mesa libgl1-mesa-glx \
    xvfb xauth \
    fonts-liberation fonts-noto-color-emoji fonts-noto fonts-freefont-ttf \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set the working directory for the application
WORKDIR /app

# Copy poetry files first for caching
COPY pyproject.toml poetry.lock ./

# Install Python dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-root

# Install Playwright browsers.
RUN poetry run playwright install --with-deps

# Copy app source code
COPY src/ ./src/

# run  crawler script using xvfb-run.

CMD ["bash", "-c", "Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render & export DISPLAY=:99 && poetry run python src/crawler.py && sleep infinity"]

# Use a full-featured Python base image for wider package availability.
# The `slim` image is often missing the necessary dependencies for graphical applications.
FROM python:3.12

# Install system dependencies for Playwright and a virtual display server.
# This single RUN command keeps the layer count low and is more efficient.
# xvfb and x11-xauth are essential for xvfb-run to work.
RUN apt-get update && apt-get install -y \
    curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxrandr2 libgbm1 libpangocairo-1.0-0 \
    libgtk-3-0 libasound2 libxdamage1 libxfixes3 libxshmfence1 libglu1-mesa libgl1-mesa-glx \
    xvfb xauth \
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

# Install Playwright browsers. This is a crucial step.
RUN poetry run playwright install --with-deps

# Copy app source code
COPY src/ ./src/

# Set the default command to run your crawler script.
# Use xvfb-run to launch the application with a virtual display.
# Note the corrected 'xvfb-run' command.
CMD ["xvfb-run", "python", "src/crawler.py"]

# Use a base Python image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /usr/src/app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the rest of your application files
COPY . .

# Specify the command to run your application
CMD ["uv", "run", "python", "main.py"]
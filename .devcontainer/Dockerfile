FROM mcr.microsoft.com/devcontainers/python:1-3.10-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    equivs \
    apt-utils \
    sudo \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Switch to vscode user
USER vscode

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
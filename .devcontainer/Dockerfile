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

# Set up workspace
WORKDIR /workspace

# Create a directory for UV cache
RUN mkdir -p /home/vscode/.cache/uv

# Set up shell prompt
RUN echo 'export PS1="\[\e[32m\]bdapt-dev\[\e[m\] \[\e[34m\]\w\[\e[m\] \$ "' >> ~/.bashrc

# Create helpful aliases
RUN echo 'alias ll="ls -la"' >> ~/.bashrc && \
    echo 'alias la="ls -A"' >> ~/.bashrc && \
    echo 'alias l="ls -CF"' >> ~/.bashrc && \
    echo 'alias bdapt-dev="uv run python -m bdapt"' >> ~/.bashrc && \
    echo 'alias test="uv run pytest"' >> ~/.bashrc && \
    echo 'alias test-cov="uv run pytest --cov=bdapt --cov-report=html"' >> ~/.bashrc && \
    echo 'alias format="uv run black . && uv run isort ."' >> ~/.bashrc && \
    echo 'alias lint="uv run mypy bdapt"' >> ~/.bashrc 
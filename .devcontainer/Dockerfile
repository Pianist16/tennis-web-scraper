FROM mcr.microsoft.com/devcontainers/python:3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN GECKODRIVER_VERSION=$(wget -qO- https://api.github.com/repos/mozilla/geckodriver/releases/latest | grep tag_name | cut -d '"' -f 4) \
    && wget -q "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz" \
    && tar -xzf geckodriver-*-linux64.tar.gz \
    && mv geckodriver /usr/local/bin/ \
    && rm geckodriver-*-linux64.tar.gz

RUN pip install --upgrade pip

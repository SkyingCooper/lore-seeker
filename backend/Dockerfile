FROM python:3.12-slim

WORKDIR /app

#RUN apt-get update && apt-get install -y \
#    gcc libpq-dev curl \
#    && rm -rf /var/lib/apt/lists/*

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# Playwright 依赖
RUN pip install playwright
RUN playwright install-deps chromium || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .
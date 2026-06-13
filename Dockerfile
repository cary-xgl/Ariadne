FROM python:3.12-slim

ARG APT_MIRROR=https://mirrors.aliyun.com/debian
ARG APT_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV TZ=Asia/Shanghai

RUN set -eux; \
    for file in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$file" ]; then \
            sed -i \
                -e "s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|http://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|http://deb.debian.org/debian|${APT_MIRROR}|g" \
                -e "s|https://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|https://security.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" \
                -e "s|https://deb.debian.org/debian|${APT_MIRROR}|g" \
                "$file"; \
        fi; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple \
    "fastapi>=0.115.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.8.0" \
    "pydantic-settings>=2.4.0" \
    "uvicorn[standard]>=0.30.0"

CMD ["uvicorn", "ariadne.api:app", "--host", "0.0.0.0", "--port", "8000"]

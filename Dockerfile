FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.8.0" \
    "pydantic-settings>=2.4.0" \
    "uvicorn[standard]>=0.30.0"

CMD ["uvicorn", "ariadne.api:app", "--host", "0.0.0.0", "--port", "8000"]

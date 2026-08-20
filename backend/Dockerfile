# ============================================
# Finance & Savings Agent — Backend Dockerfile
# Flask + Pydantic (انظر قسم 3 بالتوثيق للسبب)
# ============================================

FROM python:3.12-slim

WORKDIR /app

# متطلبات النظام (psycopg2 محتاج libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

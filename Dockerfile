FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MARCALETTI_DB=/dati/marcaletti.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY cened ./cened
COPY web ./web
COPY progetti ./progetti
RUN useradd -r -u 1000 app && mkdir -p /dati && chown app /dati
USER app
EXPOSE 8000
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

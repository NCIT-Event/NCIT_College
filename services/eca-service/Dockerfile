# Build from the repo root:  docker build -f services/eca-service/Dockerfile .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN useradd --create-home --uid 10001 app && mkdir -p /srv/media && chown app /srv/media
COPY libs/ncit-common /tmp/ncit-common
COPY services/eca-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt /tmp/ncit-common && rm -rf /tmp/ncit-common
COPY services/eca-service/app ./app
COPY services/eca-service/migrations ./migrations
COPY services/eca-service/alembic.ini services/eca-service/wsgi.py ./
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && flask --app wsgi seed && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --access-logfile - wsgi:app"]

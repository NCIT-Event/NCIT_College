# Build from the repo root:  docker build -f services/auth-service/Dockerfile .
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN useradd --create-home --uid 10001 app
COPY libs/ncit-common /tmp/ncit-common
COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt /tmp/ncit-common && rm -rf /tmp/ncit-common
COPY services/auth-service/app ./app
COPY services/auth-service/migrations ./migrations
COPY services/auth-service/alembic.ini services/auth-service/wsgi.py ./
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && flask --app wsgi bootstrap && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --access-logfile - wsgi:app"]

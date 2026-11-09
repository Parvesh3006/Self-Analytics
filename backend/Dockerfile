FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 TASK_MODE=celery
COPY requirements.txt requirements-crawl.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-crawl.txt \
    && playwright install --with-deps chromium
COPY . .

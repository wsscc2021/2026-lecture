FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN useradd --no-create-home --shell /bin/false appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# DB I/O 대기가 많으므로 워커 2개로 충분; 연결 폭증 방지
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]

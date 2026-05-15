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

# sleep 으로 대기하는 요청이 많으므로 스레드 기반 동시성 사용
# --threads 8: 최대 8개 요청을 동시에 sleep 처리
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:5000", "app:app"]

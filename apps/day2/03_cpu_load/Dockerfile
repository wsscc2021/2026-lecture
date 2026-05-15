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

# 워커 프로세스 목록(_workers)이 프로세스 내 상태이므로 단일 워커만 사용
# 멀티 워커 시 /stop 이 다른 워커의 프로세스를 종료하지 못함
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "app:app"]

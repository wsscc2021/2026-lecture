FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# requirements를 소스보다 먼저 복사 — 코드 변경 시 pip install 레이어 재사용
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# 비루트 사용자 실행 — 컨테이너 탈출 시 호스트 영향 최소화
RUN useradd --no-create-home --shell /bin/false appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "app:app"]

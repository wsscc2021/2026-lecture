#!/usr/bin/env python3
"""
05 Slow Response — 응답 지연 애플리케이션

기본 응답 시간이 40초인 애플리케이션.
K8s Readiness Probe 타임아웃, Load Balancer 연결 제한,
클라이언트 타임아웃 설정 실습에 활용한다.

Endpoints:
  GET /              40초 후 응답 (기본 지연)
  GET /slow          지연 시간 직접 지정  ?seconds=N  (기본 40)
  GET /fast          즉시 응답 (비교용)
  GET /health        즉시 응답 (Probe 동작 확인용)

실습 포인트:
  # 기본 40초 응답 확인
  curl -w "\nTotal: %{time_total}s\n" http://localhost:5000/

  # 타임아웃 설정 실습
  curl --max-time 5 http://localhost:5000/        # 5초 후 타임아웃
  curl --max-time 5 http://localhost:5000/fast    # 즉시 성공

  # K8s Readiness Probe 미통과 → 트래픽 차단 시뮬레이션
  curl http://localhost:5000/slow?seconds=0       # 즉시 응답으로 전환
"""

import os
import time

from flask import Flask, jsonify, request

app = Flask(__name__)

DEFAULT_DELAY = float(os.environ.get("DEFAULT_DELAY", 40))


@app.route("/")
def index():
    start = time.monotonic()
    time.sleep(DEFAULT_DELAY)
    elapsed = time.monotonic() - start
    return jsonify({
        "service":     "slow-response",
        "delay_sec":   DEFAULT_DELAY,
        "elapsed_sec": round(elapsed, 2),
        "message":     f"{DEFAULT_DELAY}초 후 응답",
    })


@app.route("/slow")
def slow():
    seconds = float(request.args.get("seconds", DEFAULT_DELAY))
    seconds = max(0.0, min(seconds, 300.0))  # 최대 5분으로 제한
    start   = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - start
    return jsonify({
        "service":     "slow-response",
        "delay_sec":   seconds,
        "elapsed_sec": round(elapsed, 2),
    })


@app.route("/fast")
def fast():
    return jsonify({
        "service": "slow-response",
        "message": "즉시 응답",
        "delay_sec": 0,
    })


@app.route("/health")
def health():
    # Probe는 /health 로 설정 → 지연 없이 항상 즉시 응답
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[slow-response] default delay = {DEFAULT_DELAY}s, listening on :{port}")
    # threaded=True: 지연 중인 요청이 다른 요청을 차단하지 않도록
    app.run(host="0.0.0.0", port=port, threaded=True)

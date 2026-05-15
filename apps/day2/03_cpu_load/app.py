#!/usr/bin/env python3
"""
03 CPU Load — CPU 부하 발생 애플리케이션

Endpoints:
  GET /              현재 CPU 부하 상태 조회
  POST /load         CPU 부하 시작
                     body: {"duration": 30, "workers": 2}
                       duration: 부하 지속 시간(초), 기본 30
                       workers:  병렬 워커 수, 기본 CPU 코어 수
  POST /stop         실행 중인 모든 부하 중지
  GET  /health       헬스체크

모니터링:
  top               → %Cpu us 항목 확인
  docker stats      → CPU % 확인 (컨테이너 실행 시)
"""

import multiprocessing
import os
import time
from multiprocessing import Process

from flask import Flask, jsonify, request

app = Flask(__name__)

# 실행 중인 워커 프로세스 목록
_workers: list[Process] = []


def _cpu_burn(duration: int) -> None:
    """주어진 시간(초) 동안 CPU를 100% 사용하는 순수 계산 루프."""
    end = time.monotonic() + duration
    while time.monotonic() < end:
        # 소수 판별 반복 계산 — 컴파일러 최적화로 제거되지 않도록 결과를 사용
        _ = sum(i * i for i in range(5000))


@app.route("/")
def index():
    alive = [p for p in _workers if p.is_alive()]
    return jsonify({
        "service":          "cpu-load",
        "active_workers":   len(alive),
        "cpu_count":        multiprocessing.cpu_count(),
    })


@app.route("/load", methods=["POST"])
def start_load():
    body     = request.get_json(force=True) or {}
    duration = int(body.get("duration", 30))
    workers  = int(body.get("workers",  multiprocessing.cpu_count()))

    # 이미 실행 중인 워커 정리
    for p in _workers:
        if p.is_alive():
            p.terminate()
    _workers.clear()

    for _ in range(workers):
        p = Process(target=_cpu_burn, args=(duration,), daemon=True)
        p.start()
        _workers.append(p)

    return jsonify({
        "status":   "started",
        "workers":  workers,
        "duration": duration,
        "pids":     [p.pid for p in _workers],
    })


@app.route("/stop", methods=["POST"])
def stop_load():
    stopped = 0
    for p in _workers:
        if p.is_alive():
            p.terminate()
            stopped += 1
    _workers.clear()
    return jsonify({"status": "stopped", "terminated": stopped})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

#!/usr/bin/env python3
"""
04 Memory Load — 메모리 부하 발생 애플리케이션

Endpoints:
  GET  /memory               현재 메모리 사용량 조회
  POST /memory/allocate      지정한 크기만큼 메모리 할당 (유지)
                             body: {"mb": 256}
  POST /memory/release       할당된 메모리 전체 해제
  POST /memory/leak          메모리 누수 시뮬레이션 (해제 없이 계속 할당)
                             body: {"mb": 50, "interval": 1}
  POST /memory/leak/stop     누수 시뮬레이션 중지
  GET  /health               헬스체크

모니터링:
  top               → RES, %MEM 항목 확인
  docker stats      → MEM USAGE / LIMIT (컨테이너 실행 시)
  free -h           → used / available 변화 확인
"""

import os
import threading
import time

from flask import Flask, jsonify, request

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

app = Flask(__name__)

# 할당된 메모리 블록을 보관 (GC 방지용 참조 유지)
_allocated: list[bytearray] = []
_leak_stop  = threading.Event()
_leak_thread: threading.Thread | None = None


def _current_rss_mb() -> float:
    if HAS_PSUTIL:
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    # fallback: /proc/self/status
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except Exception:
        pass
    return 0.0


def _memory_info() -> dict:
    info: dict = {
        "process_rss_mb":  round(_current_rss_mb(), 1),
        "allocated_blocks": len(_allocated),
        "allocated_mb":    round(sum(len(b) for b in _allocated) / 1024 / 1024, 1),
    }
    if HAS_PSUTIL:
        vm = psutil.virtual_memory()
        info["system_total_mb"]     = round(vm.total     / 1024 / 1024, 1)
        info["system_available_mb"] = round(vm.available / 1024 / 1024, 1)
        info["system_used_percent"] = vm.percent
    return info


@app.route("/memory")
def index():
    return jsonify({"service": "memory-load", **_memory_info()})


@app.route("/memory/allocate", methods=["POST"])
def allocate():
    body = request.get_json(force=True) or {}
    mb   = int(body.get("mb", 256))
    if mb <= 0:
        return jsonify({"error": "mb must be positive"}), 400

    block = bytearray(mb * 1024 * 1024)
    # 페이지 폴트를 유발해 실제 물리 메모리에 매핑
    for i in range(0, len(block), 4096):
        block[i] = 1
    _allocated.append(block)

    return jsonify({"status": "allocated", "mb": mb, **_memory_info()})


@app.route("/memory/release", methods=["POST"])
def release():
    count = len(_allocated)
    _allocated.clear()
    return jsonify({"status": "released", "blocks_freed": count, **_memory_info()})


def _leak_worker(mb_per_step: int, interval: float) -> None:
    while not _leak_stop.is_set():
        block = bytearray(mb_per_step * 1024 * 1024)
        for i in range(0, len(block), 4096):
            block[i] = 1
        _allocated.append(block)
        _leak_stop.wait(timeout=interval)


@app.route("/memory/leak", methods=["POST"])
def start_leak():
    global _leak_thread
    body     = request.get_json(force=True) or {}
    mb       = int(body.get("mb", 50))
    interval = float(body.get("interval", 1.0))

    if _leak_thread and _leak_thread.is_alive():
        return jsonify({"error": "leak already running — POST /memory/leak/stop first"}), 409

    _leak_stop.clear()
    _leak_thread = threading.Thread(
        target=_leak_worker, args=(mb, interval), daemon=True
    )
    _leak_thread.start()
    return jsonify({"status": "leak started", "mb_per_step": mb, "interval_sec": interval})


@app.route("/memory/leak/stop", methods=["POST"])
def stop_leak():
    _leak_stop.set()
    return jsonify({"status": "leak stopped", **_memory_info()})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

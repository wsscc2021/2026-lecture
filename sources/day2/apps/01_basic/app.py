#!/usr/bin/env python3
"""
01 Basic — 기본 응답 애플리케이션

Endpoints:
  GET /basic          hostname, timestamp, 요청 정보 반환
  GET /health         헬스체크 (K8s Liveness/Readiness Probe용)
  GET /basic/env      컨테이너 환경변수 (Pod 이름·네임스페이스 확인에 유용)
  GET /basic/headers  요청 헤더 에코
"""

import datetime
import os
import socket

from flask import Flask, jsonify, request

app = Flask(__name__)

SERVICE_NAME = os.environ.get("SERVICE_NAME", "basic-app")
VERSION      = os.environ.get("VERSION", "1.0.0")


@app.route("/basic")
def index():
    return jsonify({
        "service":   SERVICE_NAME,
        "version":   VERSION,
        "hostname":  socket.gethostname(),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "client_ip": request.remote_addr,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})


@app.route("/basic/env")
def env():
    return jsonify(dict(os.environ))


@app.route("/basic/headers")
def headers():
    return jsonify(dict(request.headers))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[{SERVICE_NAME}] listening on :{port}")
    app.run(host="0.0.0.0", port=port)

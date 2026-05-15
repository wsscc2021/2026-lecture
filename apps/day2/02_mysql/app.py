#!/usr/bin/env python3
"""
02 MySQL — 데이터베이스 읽기/쓰기 애플리케이션

사전 준비:
  docker run -d --name demo-mysql \
    -e MYSQL_ROOT_PASSWORD=demo \
    -e MYSQL_DATABASE=demo \
    -p 3306:3306 mysql:8.0

  docker exec -i demo-mysql mysql -uroot -pdemo demo < init.sql

환경변수:
  DB_HOST     (기본: 127.0.0.1)
  DB_PORT     (기본: 3306)
  DB_USER     (기본: root)
  DB_PASSWORD (기본: demo)
  DB_NAME     (기본: demo)

Endpoints:
  GET  /users          전체 사용자 목록
  POST /users          사용자 생성  body: {"name": "...", "email": "..."}
  GET  /users/<id>     특정 사용자 조회
  PUT  /users/<id>     사용자 수정  body: {"name": "...", "email": "..."}
  DELETE /users/<id>   사용자 삭제
  GET  /health         DB 연결 상태 포함 헬스체크
"""

import os

import mysql.connector
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "127.0.0.1"),
    "port":     int(os.environ.get("DB_PORT", 3306)),
    "user":     os.environ.get("DB_USER",     "root"),
    "password": os.environ.get("DB_PASSWORD", "demo"),
    "database": os.environ.get("DB_NAME",     "demo"),
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


# ── Users ──────────────────────────────────────────────────────────────────

@app.route("/users", methods=["GET"])
def list_users():
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(rows)


@app.route("/users", methods=["POST"])
def create_user():
    body = request.get_json(force=True)
    name  = body.get("name", "").strip()
    email = body.get("email", "").strip()
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("INSERT INTO users (name, email) VALUES (%s, %s)", (name, email))
    conn.commit()
    user_id = cur.lastrowid
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return jsonify(user), 201


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if not user:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)


@app.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    body  = request.get_json(force=True)
    name  = body.get("name", "").strip()
    email = body.get("email", "").strip()
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s", (name, email, user_id))
    conn.commit()
    if cur.rowcount == 0:
        cur.close(); conn.close()
        return jsonify({"error": "not found"}), 404
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return jsonify(user)


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    deleted = cur.rowcount
    cur.close(); conn.close()
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": user_id})


# ── Health ─────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT 1")
        cur.close(); conn.close()
        db_status = "ok"
    except Exception as e:
        db_status = str(e)

    status_code = 200 if db_status == "ok" else 503
    return jsonify({"status": "ok" if db_status == "ok" else "error",
                    "db": db_status}), status_code


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

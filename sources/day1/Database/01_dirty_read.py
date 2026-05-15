#!/usr/bin/env python3
"""
실습 01 — Dirty Read (READ UNCOMMITTED)

시나리오:
  T1이 Alice의 잔액을 0으로 수정하고 아직 커밋하지 않은 상태에서
  T2가 잔액을 읽으면 0을 반환한다(Dirty Read).
  이후 T1이 ROLLBACK하면 T2가 읽은 값(0)은 실제로 존재하지 않았던 데이터가 된다.

실행:
  pip install mysql-connector-python
  python3 01_dirty_read.py
"""

import threading
import time
import mysql.connector

DB = dict(host="127.0.0.1", port=3306, user="root", password="demo",
          database="isolation_demo", autocommit=False)

# ── 출력 헬퍼 ──────────────────────────────────────────────────────────────
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RESET  = "\033[0m"

def log(tx: str, msg: str, color: str = RESET) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"  {ts}  [{tx}]  {color}{msg}{RESET}", flush=True)

# ── 공통 ───────────────────────────────────────────────────────────────────
def new_conn(isolation: str) -> mysql.connector.MySQLConnection:
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation}")
    cur.close()
    return conn

def reset() -> None:
    conn = mysql.connector.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM accounts")
    cur.execute("INSERT INTO accounts VALUES (1, 'Alice', 1000), (2, 'Bob', 500)")
    cur.close()
    conn.close()

# ── 이벤트 (스레드 간 타이밍 동기화) ──────────────────────────────────────
e_t1_updated   = threading.Event()  # T1이 UPDATE 완료
e_t2_read_done = threading.Event()  # T2가 READ 완료

# ── T1: 잔액 수정 후 ROLLBACK ──────────────────────────────────────────────
def t1() -> None:
    conn = new_conn("READ UNCOMMITTED")
    cur  = conn.cursor()

    log("T1", "START TRANSACTION")
    cur.execute("START TRANSACTION")

    cur.execute("UPDATE accounts SET balance = 0 WHERE id = 1")
    log("T1", "UPDATE balance = 0  (아직 COMMIT 안 함)", YELLOW)

    e_t1_updated.set()      # T2에게 읽어도 된다고 알림
    e_t2_read_done.wait()   # T2가 읽을 때까지 대기

    log("T1", "ROLLBACK  ← 수정 취소", RED)
    conn.rollback()
    cur.close()
    conn.close()

# ── T2: T1 커밋 전 잔액 읽기 ──────────────────────────────────────────────
def t2() -> None:
    conn = new_conn("READ UNCOMMITTED")
    cur  = conn.cursor()

    e_t1_updated.wait()     # T1이 UPDATE할 때까지 대기

    log("T2", "START TRANSACTION (READ UNCOMMITTED)")
    cur.execute("START TRANSACTION")

    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    balance = cur.fetchone()[0]
    log("T2", f"SELECT balance → {balance}  {'← Dirty Read!' if balance == 0 else ''}", RED if balance == 0 else GREEN)

    e_t2_read_done.set()    # T1에게 읽기 완료 알림

    conn.commit()
    cur.close()
    conn.close()

# ── 실행 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  실습 01: Dirty Read (READ UNCOMMITTED)")
    print("=" * 60)

    reset()
    print(f"\n[초기 상태]  Alice 잔액 = 1000\n")

    th1 = threading.Thread(target=t1)
    th2 = threading.Thread(target=t2)
    th1.start()
    th2.start()
    th1.join()
    th2.join()

    # 최종 DB 값 확인
    conn = mysql.connector.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    final = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n[최종 DB 값]  Alice 잔액 = {final}")
    print("\n[정리]")
    print("  T2는 0을 읽었지만 T1이 ROLLBACK하여 실제 DB 값은 1000 그대로.")
    print("  T2가 읽은 0은 존재하지 않았던 데이터 → Dirty Read")

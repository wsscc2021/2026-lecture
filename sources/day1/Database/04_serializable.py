#!/usr/bin/env python3
"""
실습 04 — SERIALIZABLE: Lost Update 방지

시나리오: 콘서트 좌석 예약 (남은 좌석 = 1)
  T1과 T2가 동시에 마지막 좌석을 예약하려 한다.

비교 A: REPEATABLE READ — Lost Update 발생 가능
  두 트랜잭션이 동시에 "좌석 있음"을 확인하고 모두 예약에 성공한다.

비교 B: SERIALIZABLE — Lost Update 방지
  T1이 읽기 시 공유락을 걸어 T2의 읽기/수정을 직렬화한다.
  한 트랜잭션만 예약에 성공하고 나머지는 재시도 또는 실패한다.

실행:
  python3 04_serializable.py
"""

import threading
import time
import mysql.connector

DB = dict(host="127.0.0.1", port=3306, user="root", password="demo",
          database="isolation_demo", autocommit=False)

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"

def log(tx, msg, color=RESET):
    ts = time.strftime("%H:%M:%S")
    print(f"  {ts}  [{tx}]  {color}{msg}{RESET}", flush=True)

def new_conn(isolation):
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation}")
    cur.execute("SET innodb_lock_wait_timeout = 5")
    cur.close()
    return conn

def reset():
    conn = mysql.connector.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS events")
    cur.execute("""
        CREATE TABLE events (
            id    INT PRIMARY KEY,
            name  VARCHAR(50),
            seats INT
        )
    """)
    cur.execute("INSERT INTO events VALUES (1, 'Concert', 1)")
    cur.close()
    conn.close()

def get_seats():
    conn = mysql.connector.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT seats FROM events WHERE id = 1")
    seats = cur.fetchone()[0]
    cur.close()
    conn.close()
    return seats

# ── 비교 A: REPEATABLE READ ───────────────────────────────────────────────

e_a_both_read = threading.Barrier(2)  # 두 트랜잭션이 동시에 seats를 읽은 후 진행

def demo_a_user(name):
    conn = new_conn("REPEATABLE READ")
    cur  = conn.cursor()

    log(name, "START TRANSACTION (REPEATABLE READ)")
    cur.execute("START TRANSACTION")

    cur.execute("SELECT seats FROM events WHERE id = 1")
    seats = cur.fetchone()[0]
    log(name, f"SELECT seats → {seats}", GREEN if seats > 0 else RED)

    e_a_both_read.wait()  # 두 트랜잭션이 모두 읽은 뒤 동시에 UPDATE

    if seats > 0:
        cur.execute("UPDATE events SET seats = seats - 1 WHERE id = 1")
        conn.commit()
        log(name, "예약 성공! COMMIT", GREEN)
    else:
        conn.rollback()
        log(name, "좌석 없음. ROLLBACK", RED)

    cur.close()
    conn.close()

# ── 비교 B: SERIALIZABLE ─────────────────────────────────────────────────

e_b_both_start = threading.Barrier(2)

def demo_b_user(name):
    conn = new_conn("SERIALIZABLE")
    cur  = conn.cursor()

    e_b_both_start.wait()  # 두 트랜잭션 동시 시작

    log(name, "START TRANSACTION (SERIALIZABLE)")
    cur.execute("START TRANSACTION")

    try:
        cur.execute("SELECT seats FROM events WHERE id = 1")
        seats = cur.fetchone()[0]
        log(name, f"SELECT seats → {seats}  ← 공유락 획득", CYAN)

        if seats > 0:
            cur.execute("UPDATE events SET seats = seats - 1 WHERE id = 1")
            conn.commit()
            log(name, "예약 성공! COMMIT", GREEN)
        else:
            conn.rollback()
            log(name, "좌석 없음. ROLLBACK", RED)

    except mysql.connector.errors.OperationalError as e:
        if "Lock wait timeout" in str(e) or "Deadlock" in str(e):
            conn.rollback()
            log(name, f"락 충돌 → ROLLBACK (재시도 필요)", RED)
        else:
            raise
    finally:
        cur.close()
        conn.close()

# ── 실행 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  실습 04: SERIALIZABLE — Lost Update 방지")
    print("  시나리오: 콘서트 좌석 1개, 동시 예약 시도 2명")
    print("=" * 60)

    # ── 비교 A: REPEATABLE READ ──
    reset()
    print(f"\n{'─'*50}")
    print("  [비교 A] REPEATABLE READ — Lost Update 발생")
    print(f"{'─'*50}")
    print(f"  초기 좌석 = 1\n")

    ta = [threading.Thread(target=demo_a_user, args=(f"User{i+1}",)) for i in range(2)]
    for t in ta: t.start()
    for t in ta: t.join()

    print(f"\n  최종 seats = {get_seats()}  (음수면 초과 예약 발생)")
    print("  두 트랜잭션이 동시에 seats=1을 읽고 모두 UPDATE → seats가 -1이 될 수 있음")

    # ── 비교 B: SERIALIZABLE ──
    reset()
    print(f"\n{'─'*50}")
    print("  [비교 B] SERIALIZABLE — 직렬 실행 보장")
    print(f"{'─'*50}")
    print(f"  초기 좌석 = 1\n")

    tb = [threading.Thread(target=demo_b_user, args=(f"User{i+1}",)) for i in range(2)]
    for t in tb: t.start()
    for t in tb: t.join()

    print(f"\n  최종 seats = {get_seats()}  (0이면 정상: 1명만 예약 성공)")
    print("\n[정리]")
    print("  REPEATABLE READ: 스냅샷 기반 읽기, 두 트랜잭션이 같은 값을 읽고 모두 UPDATE")
    print("  SERIALIZABLE: 읽기에 공유락 → 먼저 읽은 트랜잭션이 끝날 때까지 다른 쪽 대기")
    print("  실무 대안: REPEATABLE READ + SELECT ... FOR UPDATE (행 단위 배타락)")

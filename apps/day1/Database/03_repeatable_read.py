#!/usr/bin/env python3
"""
실습 03 — REPEATABLE READ + Gap Lock (InnoDB)

데모 A: Non-Repeatable Read 방지
  T1이 REPEATABLE READ에서 잔액을 두 번 읽는다.
  T2가 중간에 수정·커밋해도 T1의 두 번째 SELECT는 첫 번째와 동일한 값을 반환한다.

데모 B: Gap Lock — Phantom Read 방지
  T1이 amount > 100 범위에 FOR UPDATE(Gap Lock)를 건다.
  T2가 해당 범위에 INSERT를 시도하면 T1이 커밋할 때까지 블로킹된다.

실행:
  python3 03_repeatable_read.py
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
    cur.close()
    return conn

def reset():
    conn = mysql.connector.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM accounts")
    cur.execute("INSERT INTO accounts VALUES (1, 'Alice', 1000), (2, 'Bob', 500)")
    cur.execute("DELETE FROM orders")
    cur.execute("INSERT INTO orders (id, user_id, amount) VALUES (1,1,50),(2,1,100),(3,1,200)")
    cur.close()
    conn.close()

# ── 데모 A: Non-Repeatable Read 방지 ─────────────────────────────────────

e_a_t1_first  = threading.Event()
e_a_t2_commit = threading.Event()

def demo_a_t1():
    conn = new_conn("REPEATABLE READ")
    cur  = conn.cursor()

    log("T1", "START TRANSACTION (REPEATABLE READ)  ← Read View 고정")
    cur.execute("START TRANSACTION")

    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    first = cur.fetchone()[0]
    log("T1", f"첫 번째 SELECT balance → {first}", GREEN)

    e_a_t1_first.set()
    e_a_t2_commit.wait()

    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    second = cur.fetchone()[0]
    same = second == first
    log("T1", f"두 번째 SELECT balance → {second}  {'← 동일 (스냅샷 유지)' if same else '← 달라짐!'}", GREEN if same else RED)

    conn.commit()
    cur.close()
    conn.close()

def demo_a_t2():
    conn = new_conn("REPEATABLE READ")
    cur  = conn.cursor()

    e_a_t1_first.wait()

    log("T2", "UPDATE balance = 500")
    cur.execute("START TRANSACTION")
    cur.execute("UPDATE accounts SET balance = 500 WHERE id = 1")
    conn.commit()
    log("T2", "COMMIT", YELLOW)

    e_a_t2_commit.set()
    cur.close()
    conn.close()

# ── 데모 B: Gap Lock ───────────────────────────────────────────────────────

e_b_t1_locked    = threading.Event()   # T1이 Gap Lock 설정 완료
e_b_t2_attempted = threading.Event()   # T2가 INSERT 시도 완료 (블로킹 해제 후)
e_b_t1_commit    = threading.Event()   # T1 COMMIT 완료

def demo_b_t1():
    conn = new_conn("REPEATABLE READ")
    cur  = conn.cursor()

    log("T1", "START TRANSACTION (REPEATABLE READ)")
    cur.execute("START TRANSACTION")

    cur.execute("SELECT COUNT(*) FROM orders WHERE amount > 100")
    count = cur.fetchone()[0]
    log("T1", f"SELECT COUNT(*) WHERE amount > 100 → {count}건", GREEN)

    # Gap Lock: amount > 100 범위에 배타락 → 해당 범위 INSERT 차단
    cur.execute("SELECT * FROM orders WHERE amount > 100 FOR UPDATE")
    rows = cur.fetchall()
    log("T1", f"SELECT ... FOR UPDATE (amount > 100)  ← Gap Lock 설정", CYAN)
    log("T1", f"  잠긴 행: {[r[0] for r in rows]}", CYAN)

    e_b_t1_locked.set()    # T2에게 INSERT 시도 신호
    e_b_t2_attempted.wait()  # T2의 INSERT 시도 후 대기

    time.sleep(1)
    log("T1", "COMMIT  ← Gap Lock 해제", GREEN)
    conn.commit()
    e_b_t1_commit.set()
    cur.close()
    conn.close()

def demo_b_t2():
    conn = new_conn("REPEATABLE READ")
    cur  = conn.cursor()
    conn.connect_timeout = 10

    e_b_t1_locked.wait()

    log("T2", "INSERT INTO orders (amount=150) 시도  ← Gap Lock 범위, 블로킹 예상", YELLOW)
    e_b_t2_attempted.set()

    start = time.time()
    try:
        cur.execute("START TRANSACTION")
        cur.execute("INSERT INTO orders (user_id, amount) VALUES (1, 150)")
        conn.commit()
        elapsed = time.time() - start
        log("T2", f"INSERT 완료 (T1 COMMIT 후 {elapsed:.1f}초 대기)", GREEN)
    except mysql.connector.errors.OperationalError as e:
        log("T2", f"락 대기 타임아웃: {e}", RED)
    finally:
        cur.close()
        conn.close()

# ── 실행 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  실습 03: REPEATABLE READ + Gap Lock")
    print("=" * 60)

    # ── 데모 A ──
    reset()
    print(f"\n{'─'*50}")
    print("  [데모 A] Non-Repeatable Read 방지")
    print(f"{'─'*50}")
    print(f"  초기 상태: Alice 잔액 = 1000\n")

    ta1 = threading.Thread(target=demo_a_t1)
    ta2 = threading.Thread(target=demo_a_t2)
    ta1.start(); ta2.start()
    ta1.join();  ta2.join()

    print("\n  [정리] REPEATABLE READ는 트랜잭션 시작 시 Read View를 한 번만 생성한다.")
    print("         T2가 커밋해도 T1의 스냅샷은 변하지 않는다.")

    # ── 데모 B ──
    reset()
    print(f"\n{'─'*50}")
    print("  [데모 B] Gap Lock — Phantom Read 방지")
    print(f"{'─'*50}")
    print(f"  초기 상태: orders.amount = [50, 100, 200]\n")

    tb1 = threading.Thread(target=demo_b_t1)
    tb2 = threading.Thread(target=demo_b_t2)
    tb1.start(); tb2.start()
    tb1.join();  tb2.join()

    print("\n  [정리] InnoDB는 FOR UPDATE 시 인덱스 Gap에 락을 걸어")
    print("         범위 내 INSERT를 차단한다 → Phantom Read 방지")

#!/usr/bin/env python3
"""
실습 02 — Non-Repeatable Read (READ COMMITTED)

시나리오:
  T1이 READ COMMITTED 수준에서 잔액을 두 번 읽는다.
  그 사이에 T2가 잔액을 수정하고 커밋하면
  T1은 같은 SELECT 문임에도 다른 값을 반환받는다.

실행:
  python3 02_non_repeatable_read.py
"""

import threading
import time
import mysql.connector

DB = dict(host="127.0.0.1", port=3306, user="root", password="demo",
          database="isolation_demo", autocommit=False)

RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
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
    cur.close()
    conn.close()

e_t1_first_read = threading.Event()   # T1 첫 번째 SELECT 완료
e_t2_committed  = threading.Event()   # T2 COMMIT 완료

def t1():
    conn = new_conn("READ COMMITTED")
    cur  = conn.cursor()

    log("T1", "START TRANSACTION (READ COMMITTED)")
    cur.execute("START TRANSACTION")

    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    first = cur.fetchone()[0]
    log("T1", f"첫 번째 SELECT balance → {first}", GREEN)

    e_t1_first_read.set()   # T2에게 UPDATE해도 된다고 알림
    e_t2_committed.wait()   # T2 COMMIT 대기

    cur.execute("SELECT balance FROM accounts WHERE id = 1")
    second = cur.fetchone()[0]
    color = RED if second != first else GREEN
    log("T1", f"두 번째 SELECT balance → {second}  {'← 값이 달라짐! (Non-Repeatable Read)' if second != first else ''}", color)

    conn.commit()
    cur.close()
    conn.close()

def t2():
    conn = new_conn("READ COMMITTED")
    cur  = conn.cursor()

    e_t1_first_read.wait()  # T1 첫 번째 읽기 완료 대기

    log("T2", "START TRANSACTION")
    cur.execute("START TRANSACTION")
    cur.execute("UPDATE accounts SET balance = 500 WHERE id = 1")
    log("T2", "UPDATE balance = 500", YELLOW)
    conn.commit()
    log("T2", "COMMIT", GREEN)

    e_t2_committed.set()
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("  실습 02: Non-Repeatable Read (READ COMMITTED)")
    print("=" * 60)

    reset()
    print(f"\n[초기 상태]  Alice 잔액 = 1000\n")

    th1 = threading.Thread(target=t1)
    th2 = threading.Thread(target=t2)
    th1.start()
    th2.start()
    th1.join()
    th2.join()

    print("\n[정리]")
    print("  READ COMMITTED는 SELECT마다 새 스냅샷(Read View)을 생성한다.")
    print("  T2가 COMMIT한 후 T1이 두 번째 SELECT를 하면 새 값(500)이 보인다.")
    print("  → 같은 트랜잭션 내에서 같은 쿼리의 결과가 달라지는 Non-Repeatable Read")

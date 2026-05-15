# Database Fundamentals

## SQL & ACID / Transactions

### 관계형 데이터베이스 (Relational Database)

데이터를 **테이블(행·열)** 로 표현하고, 테이블 간 관계를 **외래 키(Foreign Key)** 로 정의. SQL로 데이터를 조회·조작한다.

```sql
-- 기본 CRUD
SELECT id, name FROM users WHERE age > 20 ORDER BY name;
INSERT INTO users (name, age) VALUES ('Alice', 25);
UPDATE users SET age = 26 WHERE id = 1;
DELETE FROM users WHERE id = 1;

-- 조인
SELECT o.id, u.name, o.amount
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.amount > 100;
```

### Transaction (트랜잭션)

```sql
BEGIN;                          -- 트랜잭션 시작

UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- 출금
UPDATE accounts SET balance = balance + 100 WHERE id = 2;  -- 입금

COMMIT;                         -- 성공 시 확정
-- ROLLBACK;                    -- 실패 시 전체 취소
```

### ACID

트랜잭션이 보장해야 하는 4가지 속성.

| 속성 | 의미 | 예시 |
|------|------|------|
| **Atomicity** (원자성) | 트랜잭션 내 모든 작업이 전부 성공하거나 전부 실패 | 계좌 이체: 출금과 입금 둘 다 성공하거나 둘 다 취소 |
| **Consistency** (일관성) | 트랜잭션 전후로 DB가 정의된 규칙(제약 조건)을 만족 | 잔액이 음수가 되는 이체는 거부 |
| **Isolation** (격리성) | 동시 실행 트랜잭션이 서로의 중간 상태를 볼 수 없음 | 두 사람이 동시에 마지막 좌석을 예약해도 하나만 성공 |
| **Durability** (지속성) | 커밋된 데이터는 시스템 장애 후에도 유지 | DB 서버가 재시작돼도 커밋된 주문은 보존 |

### Isolation Level (격리 수준)

격리 수준이 높을수록 정합성은 높지만 동시성(성능)이 낮아진다.

| 수준 | Dirty Read | Non-Repeatable Read | Phantom Read |
|------|:---:|:---:|:---:|
| READ UNCOMMITTED | 발생 | 발생 | 발생 |
| READ COMMITTED | 방지 | 발생 | 발생 |
| REPEATABLE READ | 방지 | 방지 | 발생 (InnoDB는 방지) |
| SERIALIZABLE | 방지 | 방지 | 방지 |

> MySQL InnoDB 기본값: **REPEATABLE READ**  
> PostgreSQL 기본값: **READ COMMITTED**

```sql
-- 현재 세션의 격리 수준 확인 및 변경 (MySQL)
SELECT @@transaction_isolation;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

---

#### READ UNCOMMITTED

트랜잭션이 커밋되지 않은 다른 트랜잭션의 변경 사항을 **즉시** 읽는다. 가장 낮은 격리 수준.

**Dirty Read 발생 시나리오**

```
T1: BEGIN
T1: UPDATE accounts SET balance = 0 WHERE id = 1   -- 아직 커밋 안 함

T2: BEGIN
T2: SELECT balance FROM accounts WHERE id = 1
    → 0 반환  ← 커밋되지 않은 T1의 변경을 읽음 (Dirty Read)

T1: ROLLBACK  ← T1이 롤백 → T2가 읽은 값(0)은 실제로 존재하지 않았던 데이터
```

- 실무에서는 거의 사용하지 않음
- 데이터 정합성보다 극단적 성능이 필요한 통계·로그 집계 정도에만 고려

---

#### READ COMMITTED

커밋이 완료된 데이터만 읽는다. Dirty Read를 방지하지만 **Non-Repeatable Read**가 발생한다.

**Non-Repeatable Read 발생 시나리오**

```
T1: BEGIN
T1: SELECT balance FROM accounts WHERE id = 1  → 1000

    T2: BEGIN
    T2: UPDATE accounts SET balance = 500 WHERE id = 1
    T2: COMMIT

T1: SELECT balance FROM accounts WHERE id = 1  → 500  ← 같은 쿼리, 다른 결과
T1: COMMIT
```

MVCC 관점: T1이 SELECT할 때마다 **새 Read View**를 생성 → 첫 번째 SELECT는 T2 커밋 전, 두 번째는 T2 커밋 후 버전을 읽는다.

- PostgreSQL, Oracle 기본값
- 웹 서비스처럼 짧은 트랜잭션이 많은 환경에 적합
- 같은 트랜잭션 내 두 번 읽은 값이 다를 수 있으므로, 읽은 값을 기반으로 UPDATE하는 로직은 주의 필요

---

#### REPEATABLE READ

트랜잭션이 **시작 시점의 스냅샷**을 끝까지 유지한다. Non-Repeatable Read를 방지하지만 Phantom Read가 발생할 수 있다(InnoDB는 Gap Lock으로 방지).

**REPEATABLE READ 동작**

```
T1: BEGIN  ← 이 시점에 Read View 고정

T1: SELECT balance FROM accounts WHERE id = 1  → 1000

    T2: BEGIN
    T2: UPDATE accounts SET balance = 500 WHERE id = 1
    T2: COMMIT

T1: SELECT balance FROM accounts WHERE id = 1  → 1000  ← 스냅샷 유지, T2 변경 보이지 않음
T1: COMMIT
```

**Phantom Read 발생 시나리오** (일반 RDBMS 기준)

```
T1: BEGIN
T1: SELECT COUNT(*) FROM orders WHERE amount > 100  → 5건

    T2: INSERT INTO orders (amount) VALUES (200)
    T2: COMMIT

T1: SELECT COUNT(*) FROM orders WHERE amount > 100  → 6건  ← 행 수가 달라짐 (Phantom Read)
T1: COMMIT
```

**InnoDB의 Gap Lock으로 Phantom Read 방지**

InnoDB는 REPEATABLE READ에서 범위 조건에 **Gap Lock**(인덱스 레코드 사이의 공백을 잠금)을 걸어 다른 트랜잭션의 INSERT를 차단한다.

```
인덱스: [100] [200] [300]
              ↑
         Gap Lock 범위: (100, 200) 사이에 INSERT 차단

T1: SELECT * FROM orders WHERE amount BETWEEN 100 AND 300 FOR UPDATE
    → amount 100~300 범위에 Gap Lock 설정

T2: INSERT INTO orders (amount) VALUES (150)
    → 대기 (T1이 해당 Gap을 잠금)
```

- MySQL InnoDB 기본값
- 대부분의 일반적인 서비스에 적합한 균형점

---

#### SERIALIZABLE

모든 트랜잭션을 **직렬(순차)로 실행한 것과 동일한 결과**를 보장하는 가장 강력한 격리 수준. 모든 읽기에 공유락을 걸어 다른 트랜잭션의 쓰기를 차단한다.

```
T1: BEGIN
T1: SELECT * FROM orders WHERE user_id = 1
    → 공유락(S-Lock) 설정 — 해당 범위에 다른 트랜잭션의 INSERT/UPDATE 차단

    T2: INSERT INTO orders (user_id, amount) VALUES (1, 500)
    → 대기 (T1이 커밋/롤백할 때까지)

T1: COMMIT  → T2 진행 가능
```

**Lost Update 방지 예시**

```
좌석 예약 시나리오 (남은 좌석: 1)

SERIALIZABLE:
  T1: SELECT seats FROM events WHERE id=1  → 1  (공유락)
  T2: SELECT seats FROM events WHERE id=1  → 대기 (T1 공유락과 충돌)
  T1: UPDATE events SET seats=0 WHERE id=1
  T1: COMMIT → T2 진행
  T2: SELECT seats → 0  → 예약 실패 처리

REPEATABLE READ (락 없이 스냅샷만):
  T1: SELECT → 1  T2: SELECT → 1  (동시에 읽음)
  T1: UPDATE seats=0, COMMIT
  T2: UPDATE seats=0, COMMIT  ← 두 번 예약 성공 (Lost Update 가능)
```

- 데이터 정합성이 최우선인 금융 거래 등에 사용
- 동시성이 크게 떨어지고 데드락 발생 가능성이 높음
- 대부분의 경우 `SELECT ... FOR UPDATE`로 필요한 행에만 배타락을 거는 방식으로 대체

### MVCC (Multi-Version Concurrency Control)

MVCC는 **데이터의 여러 버전을 동시에 유지**해 읽기와 쓰기가 서로를 차단하지 않도록 하는 동시성 제어 기법이다. 전통적인 락(Lock) 기반 방식은 읽기도 쓰기를 차단하지만, MVCC는 읽기가 항상 락 없이 진행된다.

```
락 기반:  읽기 ──(공유락)──→ 쓰기 차단
MVCC:     읽기 ──(스냅샷)──→ 이전 버전 읽음, 쓰기 차단 없음
```

### 동작 원리

트랜잭션이 시작되면 해당 시점의 **스냅샷(Snapshot)** 을 획득한다. 이후 다른 트랜잭션이 같은 행을 수정해 커밋하더라도, 현재 트랜잭션은 스냅샷 시점의 **이전 버전**을 계속 읽는다.

```
시간 →

T1 시작 (스냅샷: age=25)
           T2 시작
           T2: UPDATE users SET age=30 WHERE id=1
           T2 COMMIT  ← 새 버전(age=30) 저장
T1: SELECT age FROM users WHERE id=1
           → 25 반환  ← T1의 스냅샷 시점 버전을 읽음
T1 COMMIT
```

각 행에는 버전 정보가 붙는다.

| 구현 | 버전 저장 위치 |
|------|----------------|
| **MySQL InnoDB** | Undo Log에 이전 버전 저장. 행 헤더에 `trx_id`, `roll_ptr` 보관 |
| **PostgreSQL** | 테이블 내에 새 버전 행을 직접 삽입(`xmin`, `xmax` 컬럼으로 가시성 관리) |

### Read View

트랜잭션이 스냅샷을 획득할 때 생성되는 **가시성 판단 기준**. 어느 트랜잭션이 커밋한 데이터까지 보일지를 결정한다.

| Isolation Level | Read View 생성 시점 |
|-----------------|----------------------|
| READ COMMITTED | **각 SELECT 실행 시**마다 새 Read View 생성 → 최신 커밋 반영 |
| REPEATABLE READ | **트랜잭션 시작 시** 한 번만 생성 → 트랜잭션 내내 동일한 스냅샷 |

이것이 같은 MVCC 구현임에도 두 격리 수준의 동작이 다른 이유다.

### Undo Log (MySQL InnoDB)

행을 수정하면 이전 값을 **Undo Log**에 기록하고, 행 헤더의 `roll_ptr`이 Undo Log를 가리킨다. 오래된 버전이 필요한 트랜잭션이 없어지면 **Purge 스레드**가 Undo Log를 정리한다.

```
현재 행: age=30, trx_id=200, roll_ptr ──→ Undo Log(age=25, trx_id=100)
                                                              │
                                          Undo Log(age=20, trx_id=50) ← 더 오래된 버전
```

> 오래 실행되는 트랜잭션이 있으면 Purge가 지연돼 Undo Log가 비대해지고 성능이 저하된다 (`history list length` 모니터링 권장).

```sql
-- InnoDB Undo Log 누적 확인
SHOW ENGINE INNODB STATUS\G
-- 출력 중 "History list length" 값이 수천 이상이면 장기 트랜잭션 점검 필요
```

### MVCC와 락의 관계

MVCC는 읽기-쓰기 충돌을 해결하지만, **쓰기-쓰기 충돌**은 여전히 락으로 처리한다.

| 상황 | 처리 방식 |
|------|-----------|
| 읽기 vs 쓰기 | MVCC — 읽기는 이전 버전, 쓰기는 새 버전 → 서로 차단 없음 |
| 쓰기 vs 쓰기 | 락 — 같은 행에 동시 UPDATE 시 나중 트랜잭션은 앞 트랜잭션 커밋/롤백 대기 |

```sql
-- SELECT ... FOR UPDATE: MVCC 스냅샷이 아닌 최신 버전을 읽고 행에 배타락
-- 재고 차감처럼 "읽은 값 기반으로 즉시 수정"할 때 사용
BEGIN;
SELECT stock FROM products WHERE id=1 FOR UPDATE;  -- 배타락 획득
UPDATE products SET stock = stock - 1 WHERE id=1;
COMMIT;
```

---

## Index — 인덱스

### 개념

인덱스는 특정 열의 값과 해당 행의 위치(포인터)를 별도 자료구조에 저장해 **전체 테이블 스캔 없이** 빠르게 행을 찾게 해준다.

```
인덱스 없음: 100만 행 전체 스캔 → O(n)
인덱스 있음: B-tree 탐색 →        O(log n)
```

### B-Tree Index

대부분의 RDBMS(MySQL InnoDB, PostgreSQL)의 기본 인덱스 구조. 정렬된 트리 형태로 **범위 검색**, **정렬**, **등호 조건** 모두 효율적.

```
          [50]
         /    \
      [25]    [75]
      /  \    /  \
   [10] [30][60] [90]
```

- **등호**: `WHERE id = 30` → 루트부터 탐색, O(log n)
- **범위**: `WHERE id BETWEEN 25 AND 60` → 시작점 탐색 후 리프 노드를 순회
- **정렬**: `ORDER BY id` → 인덱스 순서 그대로 반환, 별도 정렬 불필요

### Index 사용 예시

```sql
-- 인덱스 생성
CREATE INDEX idx_users_email ON users(email);

-- 복합 인덱스 (왼쪽 열부터 순서대로 활용됨)
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at);

-- 인덱스 삭제
DROP INDEX idx_users_email ON users;

-- 실행 계획 확인 (type이 ALL이면 풀스캔)
EXPLAIN SELECT * FROM users WHERE email = 'a@example.com';
```

### 인덱스가 사용되지 않는 경우

```sql
-- 함수·연산을 열에 적용 → 인덱스 무효화
WHERE YEAR(created_at) = 2024         -- X
WHERE created_at >= '2024-01-01'      -- O

-- LIKE 앞에 와일드카드 → 인덱스 미사용
WHERE name LIKE '%lee'                -- X
WHERE name LIKE 'lee%'                -- O

-- 묵시적 타입 변환
WHERE user_id = '123'   -- user_id가 INT면 인덱스 무효
```

### 인덱스의 비용

인덱스는 **쓰기(INSERT/UPDATE/DELETE) 성능을 저하**시키고 저장 공간을 추가로 사용한다. 자주 조회되는 열, WHERE·JOIN·ORDER BY에 등장하는 열에만 적용.

---

## Replication & CAP

### Replication (복제)

데이터를 여러 서버에 복사해 **읽기 성능 향상**과 **장애 대비(고가용성)** 를 달성하는 구조.

```
                 쓰기
클라이언트 ──→ Primary (Master)
                    │
              Binlog 전파
             ┌──────┴──────┐
          Replica 1    Replica 2   ← 읽기 분산
```

| 구분 | 설명 |
|------|------|
| **Primary** | 쓰기 전담. 변경사항을 Binary Log로 기록 |
| **Replica** | Primary의 Binary Log를 받아 동일하게 적용. 읽기 전담 |
| **동기 복제** | Primary가 Replica의 쓰기 완료를 기다린 뒤 커밋 → 데이터 일관성 ↑, 지연 ↑ |
| **비동기 복제** | Primary가 먼저 커밋, Replica는 나중에 반영 → 속도 ↑, 데이터 손실 가능 |

**Failover**: Primary 장애 시 Replica 중 하나를 새 Primary로 승격. AWS RDS Multi-AZ는 이 과정을 자동화(60초 내 전환).

### CAP Theorem

분산 데이터베이스는 아래 세 속성 중 **동시에 두 가지만** 완전히 보장할 수 있다.

| 속성 | 의미 |
|------|------|
| **Consistency** (일관성) | 모든 노드에서 항상 동일한 최신 데이터를 반환 |
| **Availability** (가용성) | 일부 노드 장애에도 항상 응답 반환 |
| **Partition Tolerance** (분리 내성) | 네트워크 파티션(노드 간 통신 단절)이 발생해도 동작 |

네트워크 파티션은 현실에서 반드시 발생하므로 **P는 항상 필요**. 실제 선택은 **CP vs AP**.

```
CP (일관성 + 분리 내성)
  → 파티션 발생 시 응답 거부, 데이터 불일치 방지
  → 예: HBase, ZooKeeper, etcd

AP (가용성 + 분리 내성)
  → 파티션 발생 시 오래된 데이터라도 응답
  → 예: DynamoDB(기본), Cassandra, CouchDB
```

**Eventual Consistency (최종 일관성)**: AP 시스템에서 파티션이 해소되면 모든 노드가 결국 동일한 상태로 수렴한다는 보장. 짧은 시간 동안 읽기 불일치가 허용됨.

---

## AWS Database Services

### RDS (Relational Database Service)

관리형 관계형 DB 서비스. 패치, 백업, 스냅샷, Multi-AZ Failover를 AWS가 자동 관리.

| 엔진 | 특징 |
|------|------|
| MySQL / MariaDB | 범용. 오픈소스 |
| PostgreSQL | 확장성, JSON 지원, 복잡한 쿼리 |
| Oracle / SQL Server | 라이선스 포함 옵션 |

```
RDS Multi-AZ 구조:

  AZ-a                    AZ-b
┌──────────┐          ┌──────────┐
│ Primary  │──동기──→│ Standby  │  (자동 Failover)
└──────────┘  복제    └──────────┘
```

- **Multi-AZ**: Primary 장애 시 Standby가 자동 승격 (60초 내). **읽기 분산 불가** — Standby는 장애 대비용
- **Read Replica**: 비동기 복제로 읽기 부하 분산. 최대 5개 (MySQL 기준)

### Aurora

AWS가 개발한 고성능 관계형 DB. MySQL/PostgreSQL 호환. 스토리지가 **6개에 자동 복제**되어 내구성이 뛰어남.

```
Aurora 클러스터:
  Writer Endpoint → Primary 인스턴스
  Reader Endpoint → 최대 15개 Read Replica (자동 로드밸런싱)

스토리지 레이어: 3개 AZ × 2개 복사본 = 6개 복사본 (자동)
```

| 항목 | RDS MySQL | Aurora MySQL |
|------|-----------|--------------|
| 스토리지 자동 확장 | 수동 설정 | 자동 (최대 128 TiB) |
| Read Replica | 최대 5개 | 최대 15개 |
| Failover 시간 | ~60초 | ~30초 |
| 성능 | 기준 | 최대 5× (MySQL 대비) |

**Aurora Serverless v2**: 워크로드에 따라 컴퓨팅 용량을 자동 조절 (ACU 단위).


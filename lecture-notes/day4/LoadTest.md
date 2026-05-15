# Load Test

## 테스트 종류 비교

### 테스트 유형 정의

| 유형 | 목적 | 부하 패턴 |
|------|------|-----------|
| **Performance Test** | 시스템의 전반적인 성능 특성 측정 (응답 시간, 처리량) | 일반 운영 부하 |
| **Load Test** | 예상 최대 트래픽 하에서 SLO를 만족하는지 검증 | 목표 최대 부하까지 점진적 증가 후 유지 |
| **Stress Test** | 시스템이 한계를 초과했을 때 어떻게 동작하는지 확인 | 한계를 넘어 지속 증가 |
| **Spike Test** | 갑작스러운 트래픽 급증을 처리할 수 있는지 확인 | 순간적으로 매우 높은 부하 |
| **Soak Test** | 장시간 부하에서 메모리 누수·리소스 고갈을 탐지 | 중간 부하를 수 시간 유지 |

### 부하 패턴 비교

```
Load Test               Stress Test
  │ ▲                     │ ▲
  │ │  ──────────          │ │           ↗ (crash)
  │ │ ╱          ╲         │ │         ╱
  │ │╱              ╲      │ │       ╱
  └─┴──────────────────    └─┴─────────────────
   시간 →                  시간 →

Spike Test              Soak Test
  │ ▲                     │ ▲
  │ │   █                 │ │  ───────────────
  │ │   █                 │ │ ╱               ╲
  │ │   █                 │ │╱
  └─┴──────────────────    └─┴──────────────────
   시간 →                  시간 →
```

### 각 테스트에서 발견하는 문제

```
Load Test    → SLO 위반 지점, 처리량 한계, 응답 시간 저하
Stress Test  → 장애 발생 지점, 장애 후 복구 능력 (Auto Scaling 동작 확인)
Spike Test   → 급증 시 지연 급등, 큐 포화, 연결 거부
Soak Test    → 메모리 누수, 커넥션 풀 고갈, 파일 디스크립터 누수
```

---

## 핵심 지표 해석

### TPS / RPS

| 지표 | 정의 | 차이 |
|------|------|------|
| **RPS** (Requests Per Second) | 초당 HTTP 요청 수 | 단순 요청 단위 |
| **TPS** (Transactions Per Second) | 초당 완료된 비즈니스 트랜잭션 수 | 여러 요청이 하나의 트랜잭션일 수 있음 |

```
예시: 주문 트랜잭션
  1. GET /cart       → 1 request
  2. POST /orders    → 1 request
  3. POST /payments  → 1 request
  ────────────────────────────
  1 TPS = 3 RPS
```

**처리량 병목 판별**:
```
부하 증가 → RPS가 더 이상 증가하지 않고 평탄해짐
          → Latency가 동시에 급등
          → 시스템이 최대 처리량(Saturation Point)에 도달
```

### Latency (응답 시간)

단순 평균(Average)은 극단값에 의해 왜곡되므로 **백분위수(Percentile)** 로 측정한다.

| 지표 | 의미 | 사용 목적 |
|------|------|-----------|
| **P50** | 전체 요청의 50%가 이 시간 이하로 응답 | 일반 사용자 대다수 경험 |
| **P90** | 90%가 이 시간 이하 | 느린 케이스 탐지 시작점 |
| **P95** | 95%가 이 시간 이하 | SLO 기준으로 자주 사용 |
| **P99** | 99%가 이 시간 이하 | 꼬리 지연(Tail Latency) — 최악 케이스 |
| **P99.9** | 999개 중 999개 | 극단적 최악 케이스 (금융 등) |

```
P50  =  120ms   ← 대부분 사용자 경험
P95  =  450ms   ← SLO: P95 < 500ms → 통과
P99  = 2100ms   ← 2초 이상 — 요조사 필요
P99.9 = 8500ms  ← 특정 요청에 문제 있음
```

> **P99가 P50의 10배 이상**이면 Tail Latency 문제를 조사해야 한다.  
> 원인: GC Pause, DB Lock, 외부 API 타임아웃, HotSpot 쿼리

### Error Rate (오류율)

```
Error Rate = 오류 응답 수 / 전체 응답 수 × 100

오류 분류:
  4xx — 클라이언트 오류 (잘못된 요청, 인증 실패)
  5xx — 서버 오류 (처리 실패, 타임아웃)
  네트워크 오류 — 연결 거부, 리셋

로드 테스트 중 오류율 증가 패턴:
  부하 낮을 때 0% → 부하 증가 → 특정 시점에서 오류 급증
  → 해당 지점이 시스템의 임계 부하(Breaking Point)
```

### Timeout (타임아웃)

```
연결 타임아웃(Connection Timeout):
  → 서버가 연결 요청을 수락하지 못함
  → 원인: 서버 다운, 방화벽, 포트 고갈(ESTABLISHED 수 초과)

읽기 타임아웃(Read Timeout):
  → 연결은 됐으나 지정 시간 내 응답 없음
  → 원인: 서버 처리 과부하, DB 쿼리 슬로우, 외부 API 지연

타임아웃 급증 패턴:
  → 특정 부하 이상에서 타임아웃이 갑자기 증가
  → 처리 큐가 포화돼 요청이 쌓이는 신호
```

---

## 모니터링 지표 분석

로드 테스트는 **테스트 자체**와 **시스템 모니터링**을 동시에 진행해야 병목을 진단할 수 있다.

### 분석 계층 구조

```
1. 서비스 레이어  →  RPS, Latency, Error Rate          (RED 패턴)
        ↓ 이상 발견 시
2. 애플리케이션   →  JVM GC, Thread Pool, Connection Pool
        ↓
3. 인프라 레이어  →  CPU, Memory, Disk I/O, Network      (USE 패턴)
        ↓
4. 데이터베이스   →  QPS, Slow Query, Connections, Replication Lag
```

### 부하 단계별 정상 vs 비정상 패턴

```
[정상 동작]
부하 증가 → RPS 선형 증가, Latency 완만히 증가
           CPU/메모리 사용률 증가하지만 한계 내 유지

[CPU 병목]
CPU 사용률 → 100% 근접
Latency    → 급격히 증가
RPS        → 더 이상 증가하지 않음
Error Rate → 타임아웃 오류 증가

[메모리 병목]
Memory 사용률 → 90% 이상
GC Pause(JVM) → 빈도·시간 증가
Latency 스파이크 → GC와 상관관계
OOMKilled Pod → kubectl describe 시 OOMKilled 이유

[DB 병목]
DB CPU / Slow Query 수 → 증가
App Latency → 증가 (DB 응답 대기)
DB Connection 수 → 최대값 근접
Replication Lag → 증가

[네트워크 병목]
네트워크 처리량 → 한계 근접
패킷 드롭(retransmit) → 증가
서비스 Latency → 증가하나 CPU/메모리는 정상
```

### 로드 테스트 중 모니터링 체크리스트

```
애플리케이션:
  □ RPS 선형 증가 여부
  □ P95/P99 Latency 추이
  □ Error Rate (목표: < 1%)

인프라 (노드):
  □ CPU 사용률 (> 80% 지속 시 병목)
  □ Memory Available (< 10% 시 위험)
  □ Disk I/O Utilization
  □ Network TX/RX 처리량

K8s:
  □ Pod Restart / CrashLoopBackOff
  □ HPA 동작 여부 (스케일 아웃 타이밍)
  □ CPU Throttling 비율
  □ Pending Pod (스케일 아웃 지연 감지)

데이터베이스:
  □ Connections 수 / max_connections 비율
  □ Slow Query 수
  □ InnoDB Buffer Pool Hit Rate
  □ Replication Lag
```

---

## 로드 테스트 결과 기반 병목 원인 추정

### 증상 → 원인 → 해결 매핑

#### Case 1: Latency 급등 + CPU 100%

```
증상: 부하 증가 시 P99 Latency 10배 이상 증가, CPU 100%
원인 후보:
  1. 비효율적인 알고리즘 (O(n²) 루프)
  2. CPU 집약적 작업 (암호화, 이미지 처리)이 동기 처리
  3. 스레드/프로세스 수 부족으로 요청 큐잉

확인 방법:
  kubectl top pod                    # Pod CPU 사용률
  kubectl exec -it <pod> -- top -H   # 스레드별 CPU 확인
  # 프로파일링 도구 (py-spy for Python, async-profiler for JVM)

해결:
  - CPU 집약 작업을 비동기/별도 워커로 분리
  - Pod replicas 증가 또는 CPU requests/limits 상향
  - HPA 트리거 임계값 조정 (너무 늦게 스케일 아웃하지 않도록)
```

#### Case 2: Latency 급등 + CPU 정상 + DB Slow Query 증가

```
증상: 앱 CPU는 여유롭지만 Latency 증가, DB Slow Query 급증
원인 후보:
  1. N+1 쿼리 (루프 안에서 반복 DB 조회)
  2. 인덱스 없는 컬럼으로 WHERE 조건
  3. DB 커넥션 풀 고갈 (대기 발생)

확인 방법:
  SHOW PROCESSLIST;                      # 실행 중인 쿼리 확인
  SELECT * FROM performance_schema.events_statements_summary_by_digest
    ORDER BY sum_timer_wait DESC LIMIT 10; # 슬로우 쿼리 Top 10
  EXPLAIN SELECT ...;                    # 실행 계획 확인

해결:
  - 슬로우 쿼리에 인덱스 추가
  - N+1 쿼리를 JOIN 또는 배치 조회로 변경
  - DB 커넥션 풀 크기 조정
  - Read Replica로 읽기 분산
```

#### Case 3: Error Rate 급증 + Connection Refused

```
증상: 특정 RPS 이상에서 "Connection Refused" 오류 급증
원인 후보:
  1. 앱 워커 프로세스 수 부족 (큐 포화 → 신규 연결 거부)
  2. 파일 디스크립터 한계 초과 (ulimit)
  3. 포트 고갈 (TIME_WAIT 상태 연결이 포트 점유)

확인 방법:
  ss -s                                  # 소켓 상태 집계
  ss -tn | grep TIME-WAIT | wc -l        # TIME_WAIT 연결 수
  cat /proc/sys/net/ipv4/ip_local_port_range  # 가용 포트 범위
  ulimit -n                              # 파일 디스크립터 한계

해결:
  - gunicorn workers 수 증가 (CPU 코어 수 × 2 + 1 공식)
  - TIME_WAIT 재사용 활성화:
    echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse
  - 파일 디스크립터 한계 상향 (ulimit -n 65536)
```

#### Case 4: Latency 스파이크 (주기적 급등) + CPU 정상

```
증상: 대부분의 요청은 빠른데 주기적으로 P99가 급등
원인 후보:
  1. JVM GC (특히 Full GC)
  2. 주기적 배치 작업 (캐시 갱신, 로그 플러시)
  3. 네트워크 재전송 (패킷 손실)

확인 방법:
  # GC 로그 분석 (Java)
  -Xlog:gc*:file=/var/log/gc.log:time
  # Python → GC가 없으므로 다른 원인 탐색
  # 네트워크 재전송
  netstat -s | grep retransmit

해결:
  - GC 튜닝 (힙 크기, GC 알고리즘 변경)
  - 배치 작업 시간을 트래픽 낮은 시간대로 이동
```

---

## k6 기반 로드 테스트 실습

**k6**는 Go로 작성된 오픈소스 로드 테스트 도구. 스크립트는 JavaScript로 작성하며 Prometheus·Grafana와 통합해 실시간 시각화가 가능하다.

### 설치

```bash
# Linux
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# macOS
brew install k6

# Docker
docker run --rm -i grafana/k6 run - <script.js
```

### 기본 스크립트 구조

```javascript
// basic.js
import http from 'k6/http';
import { check, sleep } from 'k6';

// 테스트 설정
export const options = {
  vus: 10,          // 동시 가상 사용자 수
  duration: '30s',  // 테스트 지속 시간
};

// 각 VU가 반복 실행하는 함수
export default function () {
  const res = http.get('http://localhost:5000/');

  // 응답 검증
  check(res, {
    'status is 200':       (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(1);  // VU가 다음 반복 전 1초 대기 (실제 사용자 행동 시뮬레이션)
}
```

```bash
k6 run basic.js
```

### Stages — 점진적 부하 증가

```javascript
// ramp_up.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m',  target: 0   },  // 워밍업 없이 시작
    { duration: '2m',  target: 50  },  // 2분에 걸쳐 50 VU로 증가
    { duration: '5m',  target: 50  },  // 5분간 50 VU 유지 (Load Test)
    { duration: '2m',  target: 200 },  // 200 VU로 증가 (Stress Test)
    { duration: '3m',  target: 200 },  // 3분간 유지
    { duration: '2m',  target: 0   },  // 점진적 감소 (Cool Down)
  ],
};

export default function () {
  const res = http.get('http://localhost:5000/');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

### Thresholds — 합격/불합격 기준

```javascript
// with_thresholds.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 100 },
    { duration: '1m', target: 0   },
  ],
  thresholds: {
    // P95 응답 시간 500ms 이하
    http_req_duration: ['p(95)<500'],
    // P99 응답 시간 1초 이하
    'http_req_duration{expected_response:true}': ['p(99)<1000'],
    // 오류율 1% 이하
    errors: ['rate<0.01'],
    // 초당 요청 수 50 이상
    http_reqs: ['rate>50'],
  },
};

export default function () {
  const res = http.get('http://localhost:5000/');

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
  });

  errorRate.add(!ok);
  sleep(1);
}
```

### 시나리오: CRUD 워크플로우

```javascript
// crud_scenario.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = 'http://localhost:5000';
const HEADERS  = { 'Content-Type': 'application/json' };

export const options = {
  scenarios: {
    // 읽기 트래픽 (70%)
    read_users: {
      executor:           'constant-arrival-rate',
      rate:               70,           // 초당 70 요청
      timeUnit:           '1s',
      duration:           '5m',
      preAllocatedVUs:    50,
    },
    // 쓰기 트래픽 (30%)
    write_users: {
      executor:           'constant-arrival-rate',
      rate:               30,
      timeUnit:           '1s',
      duration:           '5m',
      preAllocatedVUs:    20,
    },
  },
  thresholds: {
    'http_req_duration{scenario:read_users}':  ['p(95)<200'],
    'http_req_duration{scenario:write_users}': ['p(95)<500'],
  },
};

export function read_users() {
  const res = http.get(`${BASE_URL}/users`);
  check(res, { 'list status 200': (r) => r.status === 200 });
  sleep(0.5);
}

export function write_users() {
  const payload = JSON.stringify({
    name:  `User-${Date.now()}`,
    email: `user-${Date.now()}@test.com`,
  });
  const res = http.post(`${BASE_URL}/users`, payload, { headers: HEADERS });
  check(res, { 'create status 201': (r) => r.status === 201 });
  sleep(1);
}
```

### 결과 해석

```
k6 run ramp_up.js 실행 후 출력 예시:

          /\      |‾‾| /‾‾/   /‾‾/
     /\  /  \     |  |/  /   /  /
    /  \/    \    |     (   /   ‾‾\
   /          \   |  |\  \ |  (‾)  |
  / __________ \  |__| \__\ \_____/

  execution: local
     script: ramp_up.js
     output: -

  scenarios: (100.00%) 1 scenario, 200 max VUs

✓ status 200

     checks.........................: 99.85%  ✓ 48120  ✗ 72
     data_received..................: 24 MB   80 kB/s
     data_sent......................: 5.5 MB  18 kB/s
   ✓ http_req_duration.............: avg=182ms  min=45ms  med=155ms
                                      max=4.2s   p(90)=320ms p(95)=450ms p(99)=920ms
     http_req_failed................: 0.15%   ✓ 0      ✗ 72
     http_reqs......................: 48192   160.6/s
     iteration_duration.............: avg=1.18s
     iterations.....................: 48192   160.6/s
     vus............................: 12      min=1    max=200
     vus_max........................: 200     min=200  max=200

결과 해석:
  checks 99.85%    → 0.15% 체크 실패 (임계값 1% → 통과)
  p(95)=450ms      → SLO P95 < 500ms → 통과
  p(99)=920ms      → 주의: 일부 요청이 1초 근접
  http_reqs 160/s  → 최대 처리량 약 160 RPS
  max=4.2s         → 극단적 최악 케이스 조사 필요
```

### Prometheus + Grafana 연동

```bash
# k6 결과를 Prometheus에 원격 쓰기
k6 run --out experimental-prometheus-rw \
  -e K6_PROMETHEUS_RW_SERVER_URL=http://prometheus:9090/api/v1/write \
  ramp_up.js

# 또는 k6 Cloud 대시보드 사용
k6 run --out cloud ramp_up.js
```

### 실습: day2 Flask 앱 대상 테스트

```javascript
// test_flask_apps.js — apps/day2 앱들을 대상으로 하는 테스트
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const cpuLatency = new Trend('cpu_load_latency');

export const options = {
  stages: [
    { duration: '30s', target: 10  },
    { duration: '1m',  target: 50  },
    { duration: '30s', target: 100 },
    { duration: '1m',  target: 100 },
    { duration: '30s', target: 0   },
  ],
  thresholds: {
    http_req_duration:   ['p(95)<1000'],
    http_req_failed:     ['rate<0.05'],
  },
};

export default function () {
  // 01_basic 앱 (port 5001)
  const basic = http.get('http://localhost:5001/');
  check(basic, { 'basic ok': (r) => r.status === 200 });

  // 02_mysql 앱 (port 5002) — 실제 DB 부하 발생
  const users = http.get('http://localhost:5002/users');
  check(users, { 'users ok': (r) => r.status === 200 });

  sleep(1);
}
```

```bash
# 각 앱 다른 포트로 실행
PORT=5001 python3 apps/day2/01_basic/app.py &
PORT=5002 python3 apps/day2/02_mysql/app.py &

# 로드 테스트 실행
k6 run test_flask_apps.js

# 동시에 다른 터미널에서 모니터링
watch -n1 'kubectl top pod'        # K8s 환경
# 또는
watch -n1 'docker stats --no-stream'
```

/**
 * 실습 2: Load Test — mysql-app CRUD 읽기/쓰기 시나리오
 *
 * 테스트 유형: Load Test (Scenarios 활용)
 * 대상 앱:    mysql-app
 * 목표:       읽기(80%) / 쓰기(20%) 트래픽 비율로 실제 서비스 패턴을 재현하고
 *             DB 병목 여부를 확인한다.
 *
 * 엔드포인트:
 *   GET  /mysql/users         — 전체 사용자 목록 (읽기)
 *   GET  /mysql/users/:id     — 특정 사용자 조회 (읽기)
 *   POST /mysql/users         — 사용자 생성 (쓰기)
 *   PUT  /mysql/users/:id     — 사용자 수정 (쓰기)
 *   GET  /health              — DB 연결 상태 확인
 *
 * 실행:
 *   k6 run -e BASE_URL=http://<INGRESS_HOST> scripts/02_load_mysql.js
 */

import http   from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const HEADERS  = { 'Content-Type': 'application/json' };

// 시나리오별 커스텀 메트릭
const readLatency  = new Trend('latency_read',  true);
const writeLatency = new Trend('latency_write', true);
const errorRate    = new Rate('error_rate');

export const options = {
  scenarios: {
    // 읽기 트래픽: 일정한 요청 속도 유지 (constant-arrival-rate)
    read_traffic: {
      executor:        'constant-arrival-rate',
      rate:            40,          // 초당 40 요청 (목표 RPS)
      timeUnit:        '1s',
      duration:        '5m',
      preAllocatedVUs: 30,          // 사전 할당 VU
      maxVUs:          60,          // 부족할 경우 최대 60까지 자동 확장
      tags:            { traffic: 'read' },
    },
    // 쓰기 트래픽: 읽기의 25% 수준
    write_traffic: {
      executor:        'constant-arrival-rate',
      rate:            10,          // 초당 10 요청
      timeUnit:        '1s',
      duration:        '5m',
      preAllocatedVUs: 10,
      maxVUs:          20,
      tags:            { traffic: 'write' },
      // 쓰기는 1분 지연 시작 — 읽기 베이스라인 먼저 확보
      startTime:       '1m',
    },
  },

  thresholds: {
    // 읽기: P95 200ms 이하
    'http_req_duration{traffic:read}':  ['p(95)<200', 'p(99)<500'],
    // 쓰기: P95 500ms 이하 (DB INSERT/UPDATE 포함)
    'http_req_duration{traffic:write}': ['p(95)<500', 'p(99)<1000'],
    // 전체 오류율 1% 미만
    error_rate:                         ['rate<0.01'],
  },
};

// ── 읽기 시나리오 ───────────────────────────────────────────────────────────
export function read_traffic() {
  const choice = Math.random();

  if (choice < 0.6) {
    // 60%: 전체 사용자 목록 조회
    const r = http.get(`${BASE_URL}/mysql/users`, {
      tags: { endpoint: 'list' },
    });
    readLatency.add(r.timings.duration);
    const ok = check(r, {
      'list: status 200':       (r) => r.status === 200,
      'list: body is array':    (r) => Array.isArray(JSON.parse(r.body)),
      'list: response < 200ms': (r) => r.timings.duration < 200,
    });
    errorRate.add(!ok);

  } else {
    // 40%: 특정 사용자 조회 (ID 1~3 — init.sql의 시드 데이터)
    const id = randomIntBetween(1, 3);
    const r  = http.get(`${BASE_URL}/mysql/users/${id}`, {
      tags: { endpoint: 'get_one' },
    });
    readLatency.add(r.timings.duration);
    const ok = check(r, {
      'get: status 200 or 404': (r) => r.status === 200 || r.status === 404,
    });
    errorRate.add(!ok);
  }

  sleep(0.1);
}

// ── 쓰기 시나리오 ───────────────────────────────────────────────────────────
export function write_traffic() {
  const ts      = Date.now();
  const payload = JSON.stringify({
    name:  `LoadUser-${ts}`,
    email: `load-${ts}@k6test.com`,
  });

  // 사용자 생성
  const created = http.post(`${BASE_URL}/mysql/users`, payload, {
    headers: HEADERS,
    tags:    { endpoint: 'create' },
  });
  writeLatency.add(created.timings.duration);

  const createOk = check(created, {
    'create: status 201':    (r) => r.status === 201,
    'create: has id':        (r) => JSON.parse(r.body).id !== undefined,
    'create: < 500ms':       (r) => r.timings.duration < 500,
  });
  errorRate.add(!createOk);

  // 생성 성공 시 해당 사용자를 바로 수정 (읽기-쓰기 연쇄 트랜잭션 시뮬레이션)
  if (createOk && created.status === 201) {
    const userId  = JSON.parse(created.body).id;
    const updated = http.put(
      `${BASE_URL}/mysql/users/${userId}`,
      JSON.stringify({ name: `Updated-${ts}`, email: `updated-${ts}@k6test.com` }),
      { headers: HEADERS, tags: { endpoint: 'update' } }
    );
    writeLatency.add(updated.timings.duration);
    check(updated, {
      'update: status 200': (r) => r.status === 200,
    });
  }

  sleep(0.5);
}

/**
 * 과제 관찰 포인트
 * ─────────────────
 * 1. 읽기(read_traffic)와 쓰기(write_traffic)의 P95 latency 차이를 측정하세요.
 * 2. 쓰기 트래픽이 시작(1분 경과)된 후 읽기 latency가 변화하는지 확인하세요.
 *    → DB Lock 경합이 발생하면 읽기 latency도 증가할 수 있습니다.
 * 3. 테스트 중 kubectl logs로 mysql-app 로그를 확인하고 DB 오류 여부를 확인하세요.
 * 4. GET /health 엔드포인트로 DB 연결 상태를 테스트 전후로 확인하세요.
 *
 * 과제 질문
 * ─────────
 * Q1. constant-arrival-rate executor와 ramping-vus executor의 차이를 설명하고,
 *     이 실습에서 constant-arrival-rate를 선택한 이유를 서술하세요.
 *
 * Q2. 쓰기 요청이 늘어날수록 읽기 latency가 증가한다면, 이를 해결하기 위한
 *     데이터베이스 아키텍처 방안을 2가지 이상 제안하세요.
 *
 * Q3. email 필드에 UNIQUE 제약이 있어 동시에 같은 이메일로 생성 요청이 오면
 *     409 Conflict가 발생합니다. 현재 스크립트에서 이 문제가 발생하지 않는 이유와,
 *     만약 발생한다면 스크립트를 어떻게 수정해야 하는지 설명하세요.
 */

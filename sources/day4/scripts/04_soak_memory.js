/**
 * 실습 4: Soak Test — memory-load 앱 메모리 누수 탐지
 *
 * 테스트 유형: Soak Test
 * 대상 앱:    memory-load (GET /memory, POST /memory/allocate, POST /memory/leak)
 * 목표:       장시간 중간 부하를 유지하면서 메모리 사용량이 지속 증가하는지,
 *             응답 시간이 시간이 지남에 따라 저하되는지 (Tail Latency Degradation) 탐지한다.
 *
 * 테스트 단계:
 *   Phase 1 (setup):    메모리 누수 시뮬레이션 시작 (50MB/초)
 *   Phase 2 (ramp, 2m): 부하 점진적 증가
 *   Phase 3 (soak, 8m): 중간 부하 장시간 유지 — 메모리 증가에 따른 성능 저하 관찰
 *   Phase 4 (teardown): 메모리 누수 중지, 메모리 해제
 *
 * 실행:
 *   k6 run -e BASE_URL=http://<INGRESS_HOST> scripts/04_soak_memory.js
 *
 * 병행 모니터링 (별도 터미널):
 *   # 메모리 사용량 30초 간격 확인
 *   watch -n 30 'curl -s http://<INGRESS_HOST>/memory | python3 -m json.tool'
 *
 *   # OOMKilled 이벤트 감지
 *   kubectl get pods -n demo -l app=memory-load -w
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Gauge } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const HEADERS  = { 'Content-Type': 'application/json' };

// 시간 경과에 따른 성능 저하를 추적하는 커스텀 메트릭
const memoryLatency   = new Trend('latency_memory_status', true);
const allocateLatency = new Trend('latency_allocate',      true);
const errorRate       = new Rate('error_rate');

// 현재 메모리 사용량 추적 (Gauge)
const allocatedMb = new Gauge('allocated_mb');

export const options = {
  stages: [
    { duration: '1m', target: 10 },  // Ramp-Up
    { duration: '8m', target: 10 },  // Soak — 장시간 중간 부하 유지
    { duration: '1m', target: 0  },  // Cool-Down
  ],

  thresholds: {
    // 초반과 후반의 P95 latency 차이를 눈으로 확인
    // Soak Test 목표: 초반 P95의 2배 이상 증가 시 메모리 누수 확인 필요
    latency_memory_status: ['p(95)<500'],
    error_rate:            ['rate<0.05'],
  },
};

// ── setup: 메모리 누수 시뮬레이션 시작 ─────────────────────────────────────
export function setup() {
  // 이전 누수가 실행 중이면 먼저 중지
  http.post(`${BASE_URL}/memory/leak/stop`, null, { headers: HEADERS });
  http.post(`${BASE_URL}/memory/release`,   null, { headers: HEADERS });
  sleep(2);

  // 초기 메모리 상태 기록
  const before = http.get(`${BASE_URL}/memory`);
  console.log(`=== 테스트 시작 전 메모리 상태 ===\n${before.body}`);

  // 메모리 누수 시뮬레이션 시작: 30MB씩 2초 간격으로 증가
  const r = http.post(
    `${BASE_URL}/memory/leak`,
    JSON.stringify({ mb: 30, interval: 2 }),
    { headers: HEADERS }
  );
  check(r, { 'leak started': (r) => r.status === 200 });
  console.log(`=== 메모리 누수 시작: 30MB/2초 ===\n${r.body}`);

  return { startTime: Date.now() };
}

// ── default: 메인 테스트 루프 ────────────────────────────────────────────────
export default function (data) {
  // GET /memory — 현재 메모리 상태 조회 + latency 추적
  const r = http.get(`${BASE_URL}/memory`);
  memoryLatency.add(r.timings.duration);

  const ok = check(r, {
    'memory status 200': (r) => r.status === 200,
  });
  errorRate.add(!ok);

  // 응답에서 현재 할당 메모리 파싱 → Gauge 메트릭으로 기록
  if (r.status === 200) {
    try {
      const body = JSON.parse(r.body);
      if (body.allocated_mb !== undefined) {
        allocatedMb.add(body.allocated_mb);
      }
    } catch (_) { /* 무시 */ }
  }

  // 매 10번 중 1번은 추가 메모리 할당 요청 (혼합 워크로드)
  if (Math.random() < 0.1) {
    const r2 = http.post(
      `${BASE_URL}/memory/allocate`,
      JSON.stringify({ mb: 10 }),
      { headers: HEADERS, tags: { endpoint: 'allocate' } }
    );
    allocateLatency.add(r2.timings.duration);
    check(r2, {
      'allocate: 200 or 500': (r) => r.status === 200 || r.status === 500,
    });
  }

  sleep(1);
}

// ── teardown: 메모리 누수 중지 및 해제 ──────────────────────────────────────
export function teardown(data) {
  console.log('=== 메모리 누수 중지 ===');
  http.post(`${BASE_URL}/memory/leak/stop`, null, { headers: HEADERS });
  sleep(1);

  console.log('=== 메모리 해제 ===');
  http.post(`${BASE_URL}/memory/release`, null, { headers: HEADERS });
  sleep(1);

  // 최종 메모리 상태 기록
  const after = http.get(`${BASE_URL}/memory`);
  console.log(`=== 테스트 종료 후 메모리 상태 ===\n${after.body}`);

  if (data) {
    const elapsed = ((Date.now() - data.startTime) / 1000).toFixed(0);
    console.log(`총 테스트 시간: ${elapsed}초`);
  }
}

/**
 * 과제 관찰 포인트
 * ─────────────────
 * 1. Latency 저하 패턴: Soak 구간 초반(2분)과 후반(8분)의 P95 latency를 비교하세요.
 *    → latency_memory_status 트렌드로 시간에 따른 변화를 확인할 수 있습니다.
 *
 * 2. OOMKilled 발생 여부:
 *    - memory-load Deployment의 limits.memory는 512Mi입니다.
 *    - 30MB/2초 속도로 누수 시 10분 동안 최대 900MB가 누적됩니다.
 *    - OOMKilled 발생 시 Pod 재시작과 함께 error_rate가 급증합니다.
 *
 * 3. OOMKilled 후 응답 패턴:
 *    - 재시작 직후 Readiness Probe 통과 전에도 요청이 들어오면 503이 반환됩니다.
 *    - error_rate 급증 시점과 kubectl get pods의 RESTARTS 증가를 비교하세요.
 *
 * 4. allocated_mb Gauge 메트릭으로 메모리 증가 추이를 확인하세요.
 *
 * 과제 질문
 * ─────────
 * Q1. Soak Test를 Load Test나 Stress Test와 분리하는 이유는 무엇인가요?
 *     어떤 종류의 버그를 짧은 테스트로는 발견할 수 없나요?
 *
 * Q2. OOMKilled 발생 시 k6 결과에서 어떤 지표가 먼저 이상 신호를 보이는가?
 *     (error_rate, p(99) latency, http_req_failed 중에서 관찰 후 서술)
 *
 * Q3. 메모리 누수 없이 단순히 요청이 증가할 때도 메모리가 증가할 수 있습니다.
 *     이 경우와 실제 메모리 누수를 어떻게 구별할 수 있나요?
 */

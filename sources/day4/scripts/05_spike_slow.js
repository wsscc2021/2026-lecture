/**
 * 실습 5: Spike Test — slow-response 앱 타임아웃·큐 포화 관찰
 *
 * 테스트 유형: Spike Test
 * 대상 앱:    slow-response (GET /slow, GET /slow/custom, GET /slow/fast, GET /health)
 * 목표:       갑작스러운 트래픽 급증(Spike)을 시뮬레이션하고, 40초 응답 지연 엔드포인트에
 *             요청이 몰릴 때 발생하는 타임아웃·연결 거부·큐 포화를 관찰한다.
 *
 * 테스트 단계:
 *   Phase 1 (정상, 1m):    낮은 부하 — 베이스라인
 *   Phase 2 (급증, 30s):   0 → 200 VU 급격히 증가 (Spike)
 *   Phase 3 (유지, 2m):    높은 부하 유지 — 서버 한계 확인
 *   Phase 4 (회복, 30s):   200 → 0 VU 급격히 감소
 *   Phase 5 (확인, 1m):    정상 부하로 복구 여부 확인
 *
 * 실행:
 *   k6 run -e BASE_URL=http://<INGRESS_HOST> scripts/05_spike_slow.js
 *
 * 주의: /slow 엔드포인트는 40초 응답이므로 k6 VU가 오랫동안 대기합니다.
 *       200 VU × 40초 대기 = 서버에 최대 200개 커넥션 동시 유지
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';

const errorRate       = new Rate('error_rate');
const timeoutCount    = new Counter('timeout_count');
const slowLatency     = new Trend('latency_slow',  true);
const fastLatency     = new Trend('latency_fast',  true);
const healthLatency   = new Trend('latency_health', true);

export const options = {
  stages: [
    { duration: '1m',  target: 5   },  // 베이스라인 (정상 트래픽)
    { duration: '30s', target: 200 },  // Spike: 급격한 VU 증가
    { duration: '2m',  target: 200 },  // 높은 부하 유지
    { duration: '30s', target: 5   },  // Spike 해제: 급격한 감소
    { duration: '1m',  target: 5   },  // 복구 확인
  ],

  thresholds: {
    // /slow/fast 는 즉시 응답하므로 Spike에서도 빠르게 응답해야 함
    'latency_fast':   ['p(95)<200'],
    // /health 는 항상 즉시 응답 (Readiness Probe와 동일 경로)
    'latency_health': ['p(95)<100'],
    // 전체 오류율 — Spike 시 타임아웃으로 급증할 수 있음 (관찰용)
    'error_rate':     ['rate<0.30'],  // 30% 이하 (완화된 기준)
  },
};

export default function () {
  const roll = Math.random();

  if (roll < 0.20) {
    // 20%: /slow — 40초 지연 엔드포인트
    //      타임아웃을 45초로 설정해 실제 응답을 기다림
    const r = http.get(`${BASE_URL}/slow`, {
      timeout: '45s',
      tags: { endpoint: 'slow' },
    });
    slowLatency.add(r.timings.duration);

    if (r.error_code !== 0) {
      timeoutCount.add(1);
    }

    const ok = check(r, {
      '/slow: status 200':         (r) => r.status === 200,
      '/slow: actually slow (>30s)':(r) => r.timings.duration > 30000,
    });
    errorRate.add(!ok);

  } else if (roll < 0.40) {
    // 20%: /slow/custom?seconds=5 — 짧은 지연 (5초)
    const r = http.get(`${BASE_URL}/slow/custom?seconds=5`, {
      timeout: '10s',
      tags: { endpoint: 'slow_custom' },
    });
    slowLatency.add(r.timings.duration);

    const ok = check(r, {
      '/slow/custom: status 200': (r) => r.status === 200,
      '/slow/custom: ~5s':        (r) => r.timings.duration > 4000 && r.timings.duration < 8000,
    });
    errorRate.add(!ok);

  } else if (roll < 0.70) {
    // 30%: /slow/fast — 즉시 응답
    const r = http.get(`${BASE_URL}/slow/fast`, {
      timeout: '5s',
      tags: { endpoint: 'fast' },
    });
    fastLatency.add(r.timings.duration);

    const ok = check(r, {
      '/slow/fast: status 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);

  } else {
    // 30%: /health — Probe와 동일한 즉시 응답 경로
    const r = http.get(`${BASE_URL}/health`, {
      timeout: '3s',
      tags: { endpoint: 'health' },
    });
    healthLatency.add(r.timings.duration);

    const ok = check(r, {
      '/health: status 200': (r) => r.status === 200,
    });
    errorRate.add(!ok);
  }

  // /slow 응답을 기다리는 VU는 sleep 없이 바로 다음 요청
  // → 실제 사용자가 버튼을 다시 누르는 상황 시뮬레이션
  if (roll >= 0.20) sleep(0.5);
}

/**
 * 과제 관찰 포인트
 * ─────────────────
 * 1. Spike 구간(30s)에서 /slow/fast 와 /health 의 latency 변화를 비교하세요.
 *    → 즉시 응답 엔드포인트도 서버 전체 부하가 높을 때 느려지는가?
 *
 * 2. timeout_count 급증 시점을 기록하세요.
 *    → 연결 수가 많아지면 새 요청이 거부(Connection Refused) 또는
 *       큐에 대기(Queuing)합니다. 어떤 패턴이 관찰되나요?
 *
 * 3. Spike 해제(200 → 5 VU) 후 latency가 즉시 정상화되는지 확인하세요.
 *    → /slow 엔드포인트 요청은 40초 동안 연결을 유지하므로,
 *       VU가 줄어도 기존 연결이 완료될 때까지 서버에 부하가 남아있습니다.
 *
 * 4. terminationGracePeriodSeconds: 60 설정이 Spike 해제 후 어떤 역할을 하는지
 *    kubectl describe deployment slow-response -n demo 결과와 함께 설명하세요.
 *
 * 과제 질문
 * ─────────
 * Q1. slow-response Deployment에 replicas: 2가 설정되어 있습니다.
 *     Spike 시 200 VU × 40초 지연 요청은 2개 Pod에 어떻게 분산되나요?
 *     Pod당 최대 동시 연결 수는 어떻게 결정되나요? (gunicorn workers 설정 참고)
 *
 * Q2. /health 경로는 Readiness Probe로도 사용됩니다. Spike 시 /health latency가
 *     급등하면 Readiness Probe가 실패할 수 있습니다. 이를 방지하기 위한
 *     설정(timeoutSeconds, failureThreshold)을 제안하세요.
 *
 * Q3. Spike Test에서 발견한 Breaking Point(동시 요청 한계)를 기반으로,
 *     이 서비스가 실제 트래픽 급증을 처리하려면 어떤 아키텍처 변경이 필요한지
 *     최소 2가지 방안을 서술하세요. (예: 연결 큐, Circuit Breaker, 수평 확장 등)
 */

/**
 * 실습 1: Load Test — basic 앱 기본 성능 측정
 *
 * 테스트 유형: Load Test
 * 대상 앱:    basic (GET /basic, /basic/env, /basic/headers)
 * 목표:       예상 최대 트래픽 하에서 SLO(P95 < 500ms, 오류율 < 1%)를 만족하는지 검증
 *
 * 부하 패턴:
 *   0 → 50 VU (2분)  : Ramp-Up  — 점진적 부하 증가
 *   50 VU     (5분)  : Steady   — 최대 부하 유지 (Load Test 구간)
 *   50 → 0 VU (1분)  : Cool-Down — 부하 해제
 *
 * 실행:
 *   k6 run -e BASE_URL=http://<INGRESS_HOST> scripts/01_load_basic.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';

// 커스텀 메트릭 — 엔드포인트별 응답 시간 추적
const basicLatency   = new Trend('latency_basic',   true);
const envLatency     = new Trend('latency_env',     true);
const headersLatency = new Trend('latency_headers', true);
const errorRate      = new Rate('error_rate');

export const options = {
  stages: [
    { duration: '2m', target: 50 },  // Ramp-Up
    { duration: '5m', target: 50 },  // Steady (Load Test 핵심 구간)
    { duration: '1m', target: 0  },  // Cool-Down
  ],

  // Thresholds: 테스트 합격 기준 — 하나라도 실패하면 exit code 99
  thresholds: {
    // 전체 P95 응답시간 500ms 이하 (SLO)
    http_req_duration:    ['p(95)<500'],
    // 전체 P99 응답시간 1초 이하
    'http_req_duration{expected_response:true}': ['p(99)<1000'],
    // 오류율 1% 미만 (SLO)
    error_rate:           ['rate<0.01'],
    // 초당 요청 수 20 이상 (최소 처리량 보장)
    http_reqs:            ['rate>20'],
  },
};

export default function () {
  group('basic endpoints', () => {

    // --- GET /basic ---
    const r1 = http.get(`${BASE_URL}/basic`, {
      tags: { endpoint: '/basic' },
    });
    basicLatency.add(r1.timings.duration);

    const ok1 = check(r1, {
      '/basic status 200':          (r) => r.status === 200,
      '/basic has hostname':         (r) => JSON.parse(r.body).hostname !== undefined,
      '/basic response time < 300ms':(r) => r.timings.duration < 300,
    });
    errorRate.add(!ok1);

    // --- GET /basic/env ---
    const r2 = http.get(`${BASE_URL}/basic/env`, {
      tags: { endpoint: '/basic/env' },
    });
    envLatency.add(r2.timings.duration);

    check(r2, {
      '/basic/env status 200': (r) => r.status === 200,
    });

    // --- GET /basic/headers ---
    const r3 = http.get(`${BASE_URL}/basic/headers`, {
      tags: { endpoint: '/basic/headers' },
    });
    headersLatency.add(r3.timings.duration);

    check(r3, {
      '/basic/headers status 200': (r) => r.status === 200,
    });
  });

  // VU당 요청 간격 — 실제 사용자 행동 시뮬레이션
  sleep(1);
}

/**
 * 과제 관찰 포인트
 * ─────────────────
 * 1. Steady 구간(5분) 동안 P95가 500ms를 넘는 시점이 있는가?
 * 2. RPS가 선형적으로 증가하는가, 아니면 어느 지점에서 평탄해지는가?
 * 3. latency_basic vs latency_env vs latency_headers — 어떤 엔드포인트가 가장 느린가?
 * 4. Cool-Down 구간에서 latency가 즉시 떨어지는가?
 *
 * 과제 질문
 * ─────────
 * Q1. Steady 구간에서 측정한 RPS가 50 VU × (1req / 1+응답시간(초)) 공식과 일치하는가?
 *     차이가 있다면 그 이유를 설명하세요.
 *
 * Q2. sleep(1)을 sleep(0)으로 바꾸면 결과가 어떻게 달라질지 예상하고, 실제로 실행하여 비교하세요.
 *
 * Q3. 50 VU에서 P95가 SLO를 만족했다면, SLO 위반이 발생하는 VU 수를 찾아보세요.
 *     (target을 100, 200으로 늘려가며 실험)
 */

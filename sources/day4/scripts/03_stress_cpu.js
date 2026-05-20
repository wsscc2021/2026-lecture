/**
 * 실습 3: Stress Test — cpu-load 앱 한계 부하 및 HPA Scale-Out 관찰
 *
 * 테스트 유형: Stress Test
 * 대상 앱:    cpu-load (GET /cpu, POST /cpu/load, POST /cpu/stop)
 * 목표:       VU를 한계까지 증가시켜 시스템 Breaking Point를 찾고,
 *             HPA가 Scale-Out하는 타이밍과 효과를 관찰한다.
 *
 * 테스트 단계:
 *   Phase 1 (워밍업, 2m):  CPU 부하 없이 베이스라인 측정
 *   Phase 2 (부하 주입):    POST /cpu/load로 백그라운드 CPU 연산 시작
 *   Phase 3 (스트레스, 5m): VU를 지속 증가시켜 한계 탐색
 *   Phase 4 (복구, 2m):    부하 해제 후 latency 회복 확인
 *
 * 실행:
 *   k6 run -e BASE_URL=http://<INGRESS_HOST> scripts/03_stress_cpu.js
 *
 * 병행 모니터링 (별도 터미널):
 *   kubectl get hpa cpu-load -n demo -w
 *   kubectl get pods -n demo -l app=cpu-load -w
 */

import http   from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const HEADERS  = { 'Content-Type': 'application/json' };

const errorRate    = new Rate('error_rate');
const timeoutCount = new Counter('timeout_count');

export const options = {
  stages: [
    // Phase 1: 베이스라인 (낮은 부하)
    { duration: '1m', target: 5   },
    { duration: '1m', target: 5   },
    // Phase 2-3: CPU 부하 주입 후 VU 점진적 증가 (Stress)
    { duration: '1m', target: 30  },
    { duration: '1m', target: 60  },
    { duration: '1m', target: 100 },
    { duration: '1m', target: 150 },
    { duration: '1m', target: 200 },
    // Phase 4: Cool-Down
    { duration: '2m', target: 0   },
  ],

  thresholds: {
    // 스트레스 테스트이므로 임계값은 관찰용 (실패해도 종료하지 않음)
    'http_req_duration': ['p(95)<2000'],
    'error_rate':        ['rate<0.10'],  // 10% 오류율까지 허용
  },
};

// ── setup: 테스트 시작 전 CPU 부하 주입 ──────────────────────────────────────
export function setup() {
  console.log('=== CPU 부하 시작 (duration: 600초, workers: 2) ===');
  const r = http.post(
    `${BASE_URL}/cpu/load`,
    JSON.stringify({ duration: 600, workers: 2 }),
    { headers: HEADERS }
  );
  check(r, { 'cpu load started': (r) => r.status === 200 });
  console.log(`CPU 부하 시작 응답: ${r.body}`);

  sleep(5); // 부하가 CPU에 반영될 때까지 대기
}

// ── default: VU가 반복 실행하는 메인 함수 ────────────────────────────────────
export default function () {
  // GET /cpu — 현재 CPU 워커 상태 조회
  const r = http.get(`${BASE_URL}/cpu`, {
    timeout: '5s',           // 5초 타임아웃 — 부하 시 연결 지연 감지
    tags: { phase: currentPhase() },
  });

  if (r.error_code === 1050 || r.error_code === 1101) {
    // 연결 타임아웃 또는 읽기 타임아웃
    timeoutCount.add(1);
  }

  const ok = check(r, {
    'status 200':            (r) => r.status === 200,
    'response time < 2s':    (r) => r.timings.duration < 2000,
    'has active_workers key':(r) => {
      try { return JSON.parse(r.body).active_workers !== undefined; }
      catch { return false; }
    },
  });
  errorRate.add(!ok);

  sleep(0.5);
}

// ── teardown: 테스트 종료 후 CPU 부하 중지 ───────────────────────────────────
export function teardown() {
  console.log('=== CPU 부하 중지 ===');
  const r = http.post(`${BASE_URL}/cpu/stop`, null, { headers: HEADERS });
  check(r, { 'cpu stopped': (r) => r.status === 200 });
  console.log(`CPU 부하 중지 응답: ${r.body}`);
}

// 현재 VU 수로 Phase를 추정하는 헬퍼 (태그용)
function currentPhase() {
  const vu = __VU;
  if (vu <= 5)   return 'baseline';
  if (vu <= 60)  return 'ramp';
  if (vu <= 150) return 'stress';
  return 'peak';
}

/**
 * 과제 관찰 포인트
 * ─────────────────
 * 1. Breaking Point: 어느 VU 수에서 오류율이 급격히 증가하는가?
 *    → 해당 시점의 RPS, P99 latency를 기록하세요.
 *
 * 2. HPA Scale-Out 타이밍:
 *    - CPU 부하가 HPA의 averageUtilization(50%)을 초과하는 시점은 언제인가?
 *    - Scale-Out 완료 후 latency가 회복되는가? 얼마나 걸리는가?
 *
 * 3. timeout_count 메트릭이 증가하는 시점을 기록하세요.
 *    → 이는 서버가 요청을 처리하지 못하고 큐가 포화된 신호입니다.
 *
 * 4. Phase 태그별 P95 latency 비교:
 *    baseline / ramp / stress / peak 각 구간의 성능 차이를 기록하세요.
 *
 * 과제 질문
 * ─────────
 * Q1. setup() 함수에서 CPU 부하를 미리 주입하는 이유는 무엇인가요?
 *     CPU 부하 없이 동일한 VU 수로 테스트하면 결과가 어떻게 달라지나요?
 *
 * Q2. HPA가 Scale-Out을 시작한 후에도 일정 시간 동안 latency가 높게 유지됩니다.
 *     그 이유를 EKS Pod 시작 과정(이미지 풀링 → 컨테이너 시작 → Readiness Probe)
 *     관점에서 설명하세요.
 *
 * Q3. Stress Test에서 Breaking Point 이후에도 부하를 계속 올려야 하는 이유는 무엇인가요?
 *     (힌트: 장애 후 복구 능력 확인)
 */

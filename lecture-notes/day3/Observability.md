# Observability

## Observability 기본 개념

**Observability(관찰가능성)** 란 시스템의 외부 출력(로그, 메트릭, 트레이스)만으로 내부 상태를 얼마나 잘 이해할 수 있는지를 나타내는 속성이다. 제어 이론에서 유래한 개념으로, 소프트웨어 엔지니어링에서는 **"프로덕션에서 발생한 문제를 코드를 직접 보지 않고도 진단할 수 있는가"** 로 해석된다.

### Monitoring vs Observability

| | Monitoring | Observability |
|-|-----------|---------------|
| 접근 방식 | 알려진 장애를 미리 정의해 감시 | 알 수 없는 장애도 데이터로 추론 |
| 질문 | "이 서비스가 다운됐는가?" | "왜 이 요청의 응답이 느린가?" |
| 전제 | 무엇이 잘못될지 미리 안다 | 무엇이 잘못될지 모른다 |
| 도구 | 대시보드, 임계값 알람 | 로그 검색, 분산 추적, 프로파일링 |

> Monitoring은 Observability의 부분집합이다. Observability가 높은 시스템은 모니터링도 잘 되지만, 모니터링이 잘 된다고 Observability가 높은 것은 아니다.

---

## Logs, Metrics, Traces — 관찰가능성의 세 기둥

### Logs (로그)

시스템에서 발생한 **이벤트의 시간 순서 기록**. 구조화(JSON) 또는 비구조화(텍스트) 형식.

```json
{
  "timestamp": "2026-05-18T10:23:45Z",
  "level": "ERROR",
  "service": "order-service",
  "trace_id": "abc-123",
  "message": "Failed to charge payment",
  "user_id": "u-456",
  "error": "timeout after 5000ms"
}
```

- **장점**: 가장 상세한 문맥 정보, 디버깅에 직접적
- **단점**: 데이터 양이 많아 저장·검색 비용이 큼
- **주요 도구**: Elasticsearch, Loki, CloudWatch Logs

### Metrics (메트릭)

시간에 따른 **수치 데이터의 집합**. 숫자로 표현 가능한 시스템 상태를 주기적으로 수집한다.

```
# Prometheus 형식
http_requests_total{method="GET", status="200", service="order"} 4821
http_request_duration_seconds{quantile="0.99"} 0.342
process_resident_memory_bytes 52428800
```

| 메트릭 타입 | 설명 | 예시 |
|------------|------|------|
| **Counter** | 단조 증가하는 누적 값 (재시작 시 0으로 리셋) | 총 요청 수, 총 오류 수 |
| **Gauge** | 증감이 가능한 순간 값 | 현재 메모리 사용량, 활성 연결 수 |
| **Histogram** | 값의 분포 측정 (버킷 단위 집계) | 요청 응답 시간 분포, P50/P95/P99 |
| **Summary** | 클라이언트 사이드 분위수 계산 | Histogram과 유사, 정확한 분위수 필요 시 |

- **장점**: 저장 비용 낮음, 집계·시각화 용이, 알람에 적합
- **단점**: 문맥 정보 없음 ("오류율이 높다"는 알지만 "왜"는 모름)
- **주요 도구**: Prometheus, CloudWatch Metrics, Datadog

### Traces (트레이스)

마이크로서비스 환경에서 하나의 요청이 **여러 서비스를 거치는 전체 경로**를 추적한다.

```
Trace ID: abc-123
│
├── Span: API Gateway          0ms ~ 2ms
│     └── Span: order-service  2ms ~ 45ms
│           ├── Span: DB query  5ms ~ 20ms   ← 병목 발견
│           └── Span: payment-service  25ms ~ 42ms
│                 └── Span: external API  26ms ~ 40ms
```

- **Trace**: 하나의 요청 전체 흐름 (고유 Trace ID)
- **Span**: 각 서비스/작업 단위 (시작 시간, 소요 시간, 태그)
- **Context Propagation**: 서비스 간 Trace ID를 HTTP 헤더(`traceparent`)로 전달

- **장점**: 요청 흐름 전체 가시화, 마이크로서비스 병목 진단
- **단점**: 구현 복잡도 높음 (계측 코드 필요), 샘플링 설계 필요
- **주요 도구**: Jaeger, Zipkin, AWS X-Ray, OpenTelemetry

### 세 기둥 비교

| | Logs | Metrics | Traces |
|-|------|---------|--------|
| **데이터 형태** | 텍스트/JSON 이벤트 | 시계열 숫자 | 요청 경로 트리 |
| **질문 유형** | 무슨 일이 있었나? | 얼마나 자주/많이? | 어디서 느려졌나? |
| **저장 비용** | 높음 | 낮음 | 중간 |
| **알람 적합성** | 낮음 | 높음 | 낮음 |
| **디버깅 적합성** | 높음 | 낮음 | 높음 |
| **수집 단위** | 이벤트 발생 시 | 주기적 (scrape) | 요청 단위 |

> **실전 패턴**: 알람(Metrics) → 대시보드 확인(Metrics) → 해당 시간대 로그 검색(Logs) → 문제 요청 트레이스 확인(Traces) 순서로 장애를 진단한다.

---

## SLI / SLO / SLA

### SLI (Service Level Indicator) — 서비스 수준 지표

서비스 품질을 측정하는 **실제 메트릭**. "지금 서비스가 얼마나 잘 동작하고 있는가"를 수치로 표현.

```
# 대표적인 SLI 예시
가용성(Availability) SLI:
  성공 요청 수 / 전체 요청 수 = 99.95%

지연(Latency) SLI:
  응답 시간 < 200ms인 요청 비율 = 97.3%

오류율(Error Rate) SLI:
  5xx 응답 수 / 전체 요청 수 = 0.05%
```

### SLO (Service Level Objective) — 서비스 수준 목표

SLI에 대한 **내부 목표값**. 팀이 달성하고자 하는 서비스 품질 기준.

```
가용성 SLO:   99.9% (월간 허용 다운타임 ≈ 43분)
지연 SLO:     P99 응답시간 < 500ms
오류율 SLO:   오류율 < 0.1%
```

**Error Budget (오류 예산)**

```
SLO = 99.9% → 허용 오류 = 0.1%
30일 기준 총 요청 수 = 1,000,000건
Error Budget = 1,000건

→ 이 예산 안에서 배포, 실험, 인프라 변경을 수행
→ 예산 소진 시: 기능 배포 중단, 안정성 작업 우선
```

### SLA (Service Level Agreement) — 서비스 수준 계약

서비스 제공자와 고객 간의 **법적·계약적 약속**. SLO보다 낮은 수준으로 설정해 여유를 확보.

```
내부 SLO: 99.9%  (팀 목표)
외부 SLA: 99.5%  (고객과 계약, 위반 시 크레딧 환급)
```

| | SLI | SLO | SLA |
|-|-----|-----|-----|
| 정의 | 측정값 | 내부 목표 | 외부 계약 |
| 결정자 | 엔지니어링 | 엔지니어링 + 제품팀 | 비즈니스 + 법무 |
| 위반 결과 | 대시보드 알람 | Error Budget 소진 | 패널티, 크레딧 환급 |

### AWS 주요 서비스 SLA 예시

| 서비스 | SLA |
|--------|-----|
| EC2 | 99.99% (월간) |
| RDS Multi-AZ | 99.95% |
| EKS | 99.95% |
| S3 | 99.9% |

---

## Alerting

### 좋은 알람의 조건

| 조건 | 나쁜 예 | 좋은 예 |
|------|--------|--------|
| **실행 가능** | CPU > 80% | 오류율 > 1% (즉시 조사 필요) |
| **낮은 노이즈** | 1분마다 알람 | 5분 평균 임계값 초과 시 |
| **증상 기반** | 내부 지표 알람 | 사용자 영향 지표 알람 |
| **명확한 우선순위** | 모든 알람이 CRITICAL | P1/P2/P3 분류 |

### 알람 설계 원칙

**증상(Symptom) 기반 알람 우선**

```
# 원인 기반 (나쁨): 원인이 다양해 알람이 너무 많아짐
- CPU > 90%
- 디스크 I/O > 80%
- 메모리 사용률 > 85%

# 증상 기반 (좋음): 사용자가 실제로 영향받을 때만 알람
- 오류율 > 1%  (5분 평균)
- P99 응답시간 > 2초  (5분 평균)
- 가용성 < 99.9%  (1시간 window)
```

**Alertmanager + Prometheus 예시**

```yaml
# Prometheus 알람 규칙
groups:
- name: slo-alerts
  rules:
  - alert: HighErrorRate
    expr: |
      sum(rate(http_requests_total{status=~"5.."}[5m]))
      /
      sum(rate(http_requests_total[5m])) > 0.01
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "오류율 1% 초과"
      description: "{{ $value | humanizePercentage }} 오류율 발생 중"

  - alert: HighLatency
    expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 0.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "P99 응답시간 500ms 초과"
```

### Dead Man's Switch (생존 신호 알람)

모니터링 시스템 자체가 다운됐을 때를 감지하기 위한 알람. 항상 발동해야 할 알람이 일정 시간 이상 오지 않으면 경보를 발생시킨다.

```yaml
# 항상 참인 규칙 — 이 알람이 오지 않으면 모니터링이 죽은 것
- alert: Watchdog
  expr: vector(1)
  labels:
    severity: none
  annotations:
    summary: "모니터링 시스템 정상 동작 확인용"
```

### Runbook

알람 발생 시 대응 절차를 문서화한 매뉴얼. 알람 annotation에 Runbook URL을 포함해 온콜 엔지니어가 즉시 대응 방법을 찾을 수 있도록 한다.

```yaml
annotations:
  summary: "오류율 1% 초과"
  runbook_url: "https://wiki.example.com/runbooks/high-error-rate"
```

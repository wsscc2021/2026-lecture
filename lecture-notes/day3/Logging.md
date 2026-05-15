# Logging

## 로그 종류와 레벨

### 로그 종류

| 종류 | 설명 | 예시 |
|------|------|------|
| **Application Log** | 앱 코드에서 직접 출력하는 비즈니스 이벤트 | 주문 생성, 결제 실패, 로그인 시도 |
| **Access Log** | HTTP 요청/응답 기록 (웹 서버, ALB) | `GET /api/orders 200 45ms` |
| **System Log** | OS·커널·서비스 이벤트 | syslog, journald, dmesg |
| **Audit Log** | 보안·컴플라이언스용 행위 기록 | API 콜, 파일 접근, 권한 변경 |
| **Event Log** | 인프라 상태 변화 | K8s 이벤트, EC2 상태 변경 |

### 로그 레벨 (심각도)

```
TRACE   가장 상세한 디버깅 정보 (반복 루프, 변수값 등)
DEBUG   개발 중 디버깅에 필요한 상세 정보
INFO    정상 동작 흐름 기록 (요청 수신, 서비스 시작)
WARN    즉각적인 조치는 불필요하지만 주의가 필요한 상황
ERROR   처리 실패, 복구 가능한 오류 (예외, DB 연결 실패)
FATAL   시스템 종료를 유발하는 심각한 오류
```

운영 환경 권장 설정:
- 평상시: **INFO** (DEBUG/TRACE는 로그 양이 너무 많아 비용·성능 문제)
- 장애 조사 시: **DEBUG** 로 일시 전환 후 원복

### 구조화 로그 (Structured Logging)

비구조화(텍스트) 로그는 검색·집계가 어렵다. **JSON 형식**으로 출력하면 로그 수집 시스템에서 필드 단위 검색·필터링이 가능하다.

```python
# 나쁜 예: 비구조화 텍스트
logging.error(f"Payment failed for user {user_id}, amount: {amount}, error: {e}")
# → "Payment failed for user u-123, amount: 50000, error: timeout"

# 좋은 예: JSON 구조화 로그 (python-json-logger)
logger.error("payment_failed", extra={
    "user_id":  user_id,
    "amount":   amount,
    "error":    str(e),
    "trace_id": trace_id,
})
# → {"timestamp":"2026-05-18T10:23:45Z","level":"ERROR","event":"payment_failed",
#    "user_id":"u-123","amount":50000,"error":"timeout","trace_id":"abc-123"}
```

```bash
# 구조화 로그는 jq로 필드 단위 필터링 가능
kubectl logs order-service | jq 'select(.level=="ERROR")'
kubectl logs order-service | jq 'select(.user_id=="u-123")'
```

---

## EFK 스택

**EFK(Elasticsearch + Fluentd/Fluentbit + Kibana)** 는 쿠버네티스 환경에서 가장 널리 쓰이는 로그 수집·저장·시각화 스택이다.

```
┌────────────────────────────────────────────────────────┐
│                    K8s Cluster                         │
│                                                        │
│  Pod A  Pod B  Pod C    ← 로그를 stdout/stderr로 출력   │
│     │      │     │                                     │
│  ┌──┴──────┴─────┴──┐                                  │
│  │   Fluentbit      │  ← DaemonSet (각 노드에 1개)     │
│  │  (수집 · 경량화)  │    /var/log/containers/*.log 읽기│
│  └────────┬─────────┘                                  │
└───────────┼────────────────────────────────────────────┘
            │ 전송
            ▼
┌───────────────────────┐
│   Fluentd (집계·변환) │  ← 선택적 중간 집계 레이어
│   또는 직접 전송       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐      ┌─────────────────────┐
│    Elasticsearch      │ ←──→ │      Kibana          │
│  (저장 · 인덱싱 · 검색)│      │  (검색 · 시각화)    │
└───────────────────────┘      └─────────────────────┘
```

### Elasticsearch

분산 검색·분석 엔진. 로그 데이터를 **인덱스**로 저장하고 전문 검색(Full-Text Search), 필드 필터링, 집계를 지원한다.

```bash
# 인덱스 목록 확인
curl http://elasticsearch:9200/_cat/indices?v

# 특정 조건 검색 (Kibana Query Language 또는 REST API)
curl -X GET "http://elasticsearch:9200/logs-*/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        { "match": { "level": "ERROR" } },
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ]
    }
  }
}'
```

### Kibana

Elasticsearch 데이터를 시각화하는 웹 UI.

```
주요 기능:
  Discover   — 로그 검색 및 시간대별 분포 확인
  Dashboard  — 시각화 패널 모음 (오류율 추이, 서비스별 요청량 등)
  Lens       — 드래그앤드롭 시각화 도구
  Alerting   — 조건 기반 알람 설정
```

```
KQL(Kibana Query Language) 예시:
  level: ERROR                           # ERROR 레벨
  service: "order-service" AND level: ERROR  # 특정 서비스 오류
  response_time > 1000                   # 응답 1초 초과
  NOT status: 200                        # 200 제외
```

---

## Fluentbit vs Fluentd

두 도구 모두 **CNCF 프로젝트**로, 로그를 수집·변환·전송하는 역할을 한다.

| | Fluentbit | Fluentd |
|-|-----------|---------|
| **목적** | 경량 수집기 (Edge) | 중앙 집계기 (Aggregator) |
| **메모리** | ~1 MB | ~40 MB |
| **CPU** | 매우 낮음 | 낮음 |
| **언어** | C | Ruby + C |
| **플러그인 수** | 적음 (~100) | 많음 (~1,000) |
| **변환 기능** | 기본적 | 강력 (Ruby 스크립트 가능) |
| **K8s 배포** | DaemonSet (각 노드) | Deployment 또는 DaemonSet |
| **주 용도** | 노드에서 로그 수집·경량 처리 | 집계, 복잡한 변환, 다중 출력 |

### 권장 배포 패턴

```
노드 → [Fluentbit DaemonSet] → [Fluentd Aggregator] → Elasticsearch
                                       ↓
                               - 로그 중복 제거
                               - 포맷 통일
                               - 여러 스토리지로 분기 (S3, ES, CloudWatch)
```

단순한 환경에서는 Fluentbit만으로 Elasticsearch에 직접 전송해도 된다.

### Fluentbit K8s 설정 예시

```yaml
# ConfigMap: Fluentbit 파이프라인 설정
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentbit-config
  namespace: logging
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush        1
        Log_Level    info

    [INPUT]
        Name              tail
        Path              /var/log/containers/*.log
        Parser            docker
        Tag               kube.*
        Refresh_Interval  5
        Mem_Buf_Limit     50MB

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Merge_Log           On     # JSON 로그를 필드로 파싱
        Keep_Log            Off

    [OUTPUT]
        Name            es
        Match           *
        Host            elasticsearch.logging.svc.cluster.local
        Port            9200
        Index           logs
        Logstash_Format On
        Logstash_Prefix kube
```

---

## Back-Pressure 현상

### 개념

로그 수집 파이프라인에서 **소비자(Elasticsearch 등)가 생산자(앱·Fluentbit)보다 느릴 때** 발생하는 현상. 처리되지 못한 로그가 버퍼에 쌓이고, 버퍼가 가득 차면 로그가 유실되거나 앱 성능에 영향을 준다.

```
앱 (로그 생산)
    │  10,000 lines/sec
    ▼
Fluentbit 버퍼
    │  처리 가능: 8,000 lines/sec
    ▼
Elasticsearch (저장)
    │  처리 가능: 5,000 lines/sec  ← 병목
    ▼
  버퍼 포화 → 로그 유실 또는 생산자 블로킹
```

### 발생 원인

- Elasticsearch 인덱싱 속도보다 로그 생성 속도가 빠를 때 (트래픽 급증 시)
- 네트워크 지연 또는 단절
- Elasticsearch 노드 장애

### 해결 방법

**1. 버퍼 크기 조정 (Fluentbit)**

```
[INPUT]
    Mem_Buf_Limit   100MB    # 메모리 버퍼 한도 증가
    storage.type    filesystem  # 디스크 버퍼로 전환 (메모리 부족 시)

[OUTPUT]
    storage.total_limit_size  1G   # 디스크 버퍼 최대 크기
```

**2. 메시지 큐 도입 (Kafka)**

Fluentbit와 Elasticsearch 사이에 Kafka를 두어 급격한 부하를 흡수한다.

```
Fluentbit → Kafka → Fluentd(Consumer) → Elasticsearch

장점:
  - Kafka가 버퍼 역할 → Elasticsearch 장애 시 로그 유실 없음
  - 여러 Consumer가 병렬로 처리 → 처리량 확장
  - 로그를 여러 목적지(ES, S3, 분석 시스템)로 동시 전달
```

**3. 샘플링 / 로그 레벨 조정**

```
# 트래픽 급증 시 DEBUG 로그 비활성화
# Fluentbit 필터로 낮은 레벨 로그 제거
[FILTER]
    Name    grep
    Match   *
    Exclude level debug
    Exclude level trace
```

**4. Elasticsearch 스케일 아웃**

```bash
# 인덱스 샤드 수 증가 (미리 설계)
PUT /logs-2026.05
{
  "settings": {
    "number_of_shards":   3,   # 데이터 분산 → 쓰기 처리량 향상
    "number_of_replicas": 1    # 복제본 (가용성)
  }
}
```

### Back-Pressure 모니터링 지표

```
Fluentbit:
  □ fluentbit_output_retries_total    — 재전송 횟수 증가 시 병목 신호
  □ fluentbit_output_dropped_records  — 로그 유실 발생 여부

Elasticsearch:
  □ indexing.index_time               — 인덱싱 소요 시간
  □ thread_pool.write.queue           — 쓰기 큐 대기 길이 (증가 시 포화)
  □ jvm.mem.heap_used_percent         — JVM 힙 사용률 (85% 초과 시 GC 압박)
```

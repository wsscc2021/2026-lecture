# Monitoring

## RED 패턴 / USE 패턴

두 패턴은 모니터링 지표를 선정할 때 "무엇을 봐야 하는가"에 대한 체계적인 프레임워크다.

### RED 패턴 — 서비스 수준 모니터링

**마이크로서비스·API** 에 적합. 사용자가 체감하는 서비스 품질을 측정한다.

| 지표 | 의미 | 예시 |
|------|------|------|
| **R**ate | 초당 요청 수 (처리량) | `http_requests_total` rate |
| **E**rror | 오류 비율 (실패율) | 5xx 응답 / 전체 응답 |
| **D**uration | 응답 시간 (지연) | P50 / P95 / P99 응답 시간 |

```
# Prometheus PromQL 예시

# Rate: 초당 요청 수
sum(rate(http_requests_total[5m])) by (service)

# Error: 오류율
sum(rate(http_requests_total{status=~"5.."}[5m]))
/ sum(rate(http_requests_total[5m]))

# Duration: P99 응답시간
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)
```

### USE 패턴 — 리소스 수준 모니터링

**인프라·시스템 리소스** 에 적합. CPU, 메모리, 디스크, 네트워크 등 자원 상태를 측정한다.

| 지표 | 의미 | 예시 |
|------|------|------|
| **U**tilization | 자원 사용률 | CPU 사용률 70%, 메모리 사용률 85% |
| **S**aturation | 자원 포화도 (대기 중인 작업) | CPU Load Average, 디스크 I/O 큐 길이 |
| **E**rrors | 자원 오류 수 | 네트워크 패킷 드롭, 디스크 오류 |

```
# CPU
Utilization:  rate(node_cpu_seconds_total{mode!="idle"}[5m])
Saturation:   node_load1 / count(node_cpu_seconds_total{mode="idle"})

# 메모리
Utilization:  1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
Saturation:   node_vmstat_pgmajfault (메이저 페이지 폴트)

# 디스크
Utilization:  rate(node_disk_io_time_seconds_total[5m])
Saturation:   node_disk_io_time_weighted_seconds_total  (I/O 큐 대기 시간)
```

### RED vs USE 선택 기준

```
사용자 요청을 처리하는 서비스  →  RED 패턴
  (API 서버, 마이크로서비스, 데이터베이스)

자원을 소비하는 인프라 컴포넌트  →  USE 패턴
  (노드, 디스크, 네트워크 인터페이스, 큐)

두 가지 모두 적용:
  서비스 레벨(RED) + 인프라 레벨(USE) 조합이 완전한 모니터링 전략
```

---

## 서비스 수준 모니터링

서비스 수준 모니터링의 목표는 **사용자 영향** 을 가장 먼저 감지하는 것이다.

### Golden Signals (구글 SRE 4가지 핵심 지표)

| 신호 | 의미 | 알람 기준 예시 |
|------|------|----------------|
| **Latency** | 요청 처리 시간 (성공/실패 구분) | P99 > 1s |
| **Traffic** | 시스템 부하 (초당 요청 수) | 평소 대비 3× 급증 |
| **Errors** | 실패 요청 비율 | 5xx > 1% |
| **Saturation** | 자원 포화도 (얼마나 한계에 가까운가) | CPU > 80%, 큐 길이 증가 |

> RED 패턴은 Golden Signals에서 Saturation을 제외한 부분 집합이다.

### HTTP API 모니터링 체크리스트

```
응답 코드 분포:
  □ 2xx 비율 (성공)
  □ 4xx 비율 (클라이언트 오류)
  □ 5xx 비율 (서버 오류)

응답 시간:
  □ P50 (중간값 — 대다수 사용자 경험)
  □ P95 (상위 5% — 느린 요청 탐지)
  □ P99 (상위 1% — 꼬리 지연 탐지)

처리량:
  □ RPS (Requests Per Second)
  □ 동시 연결 수

가용성:
  □ Uptime (헬스체크 기반)
  □ Error Budget 소진률
```

---

## 리소스 수준 모니터링

### CPU

```
모니터링 지표:
  사용률(us + sy)  — 실제 작업에 쓰이는 비율
  I/O Wait (wa)    — 디스크 I/O 대기 비율 (높으면 스토리지 병목)
  Steal (st)       — 하이퍼바이저에게 빼앗긴 비율 (가상화 환경)
  Load Average     — 실행 대기 프로세스 수 (코어 수 대비 평가)

주의 임계값:
  CPU 사용률 > 80% (지속적)  → 스케일 아웃 검토
  I/O Wait > 20%             → 디스크/스토리지 병목 조사
  Load Average > CPU 코어 수 → CPU 포화 상태
```

### Memory

```
모니터링 지표:
  used          — 실제 사용 중인 메모리
  available     — 즉시 사용 가능한 메모리 (free + buff/cache)
  buff/cache    — 커널이 사용 중인 캐시 (재사용 가능)
  swap used     — 스왑 사용량 (0이 이상적)

주의 임계값:
  available < 10%          → OOM Killer 동작 가능성
  swap used > 0 (지속적)  → 메모리 부족, 성능 저하 발생 중
```

### Disk

```
모니터링 지표:
  사용률(%)          — 파일시스템 용량
  inode 사용률(%)   — 파일 개수 한계 (용량은 남아도 inode 고갈 가능)
  I/O Utilization   — 디스크 바쁨 비율
  I/O Latency       — 읽기/쓰기 응답 시간
  Queue Length      — I/O 대기 중인 요청 수

주의 임계값:
  디스크 사용률 > 85%  → 증설 또는 정리 필요
  I/O Utilization > 80% (지속)  → I/O 병목
```

---

## 쿠버네티스 주요 모니터링 요소

### 클러스터 레벨

```
노드:
  □ 노드 상태 (Ready / NotReady)
  □ 노드 CPU/메모리 사용률
  □ 노드 디스크 사용률
  □ 할당 가능한 자원 vs 실제 요청된 자원 (Over-provisioning 감지)

컨트롤 플레인:
  □ API Server 응답 시간
  □ etcd 레이턴시 및 크기
  □ 스케줄러 큐 대기 Pod 수
```

### Pod/워크로드 레벨

```
Pod 상태:
  □ Running / Pending / CrashLoopBackOff / OOMKilled Pod 수
  □ Restart 횟수 (지속적 증가 → 앱 문제)
  □ Pod 스케줄링 대기 시간

리소스:
  □ requests vs 실제 사용량 차이 (VPA 추천값과 비교)
  □ limits 대비 사용률 (limits에 근접 → OOM 위험)
  □ CPU Throttling 비율 (limits로 인해 CPU가 제한되는 비율)
```

### 핵심 PromQL 예시

```promql
# CrashLoopBackOff Pod 수
count(kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"})

# CPU Throttling 비율 (높으면 limits 상향 필요)
sum(rate(container_cpu_cfs_throttled_seconds_total[5m]))
/ sum(rate(container_cpu_cfs_periods_total[5m]))

# 메모리 limits 대비 사용률
container_memory_working_set_bytes
/ container_spec_memory_limit_bytes

# 노드 할당 가능 메모리 대비 요청량
sum(kube_pod_container_resource_requests{resource="memory"}) by (node)
/ kube_node_status_allocatable{resource="memory"}
```

### Kubernetes Monitoring 스택 (kube-prometheus-stack)

```bash
# Helm으로 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# 포함된 컴포넌트
# - Prometheus Operator
# - Prometheus (메트릭 수집·저장)
# - Alertmanager (알람 라우팅)
# - Grafana (시각화 대시보드)
# - node-exporter (노드 메트릭 DaemonSet)
# - kube-state-metrics (K8s 오브젝트 상태 메트릭)

# Grafana 접속 (포트 포워딩)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# admin / prom-operator
```

---

## 데이터베이스 주요 모니터링 요소

### 공통 (MySQL / PostgreSQL / Aurora)

```
성능:
  □ QPS (Queries Per Second)          — 초당 쿼리 수
  □ 쿼리 응답 시간 (P50 / P99)
  □ 슬로우 쿼리 수 (임계값 초과 쿼리)
  □ 커넥션 수 / 최대 커넥션 대비 사용률

가용성:
  □ Replication Lag                   — Replica가 Primary에서 얼마나 뒤처졌나
  □ Failover 발생 횟수

리소스:
  □ CPU 사용률
  □ 메모리 사용률 (Buffer Pool 히트율 포함)
  □ 디스크 I/O (읽기/쓰기 처리량, 지연)
  □ 스토리지 잔여 용량
```

### MySQL / Aurora 특화

```
InnoDB Buffer Pool:
  □ 히트율 = (읽기 요청 - 디스크 읽기) / 읽기 요청
    → 99% 이상 유지 권장 (낮으면 메모리 부족)

  SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool%';

커넥션:
  □ Threads_connected / max_connections
  □ Threads_running (실제 실행 중 쿼리 수)

  SHOW GLOBAL STATUS LIKE 'Threads%';

Replication:
  □ Seconds_Behind_Master  (0에 가까울수록 좋음)

  SHOW REPLICA STATUS\G
```

### RDS / Aurora — CloudWatch 핵심 메트릭

| 메트릭 | 의미 | 주의 임계값 |
|--------|------|-------------|
| `CPUUtilization` | CPU 사용률 | > 80% 지속 |
| `DatabaseConnections` | 현재 연결 수 | max_connections의 80% |
| `FreeableMemory` | 사용 가능한 메모리 | < 인스턴스 메모리의 10% |
| `ReadLatency` / `WriteLatency` | 읽기/쓰기 지연 | > 20ms |
| `ReplicaLag` | 복제 지연 | > 1초 |
| `DiskQueueDepth` | I/O 큐 대기 수 | > 1 지속 |
| `FreeStorageSpace` | 남은 스토리지 | < 총 용량의 20% |

```bash
# AWS CLI로 RDS 메트릭 조회
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=my-db \
  --start-time 2026-05-18T00:00:00Z \
  --end-time 2026-05-18T01:00:00Z \
  --period 60 \
  --statistics Average
```

# 실습 1: 메트릭 수집 및 CloudWatch 대시보드

## 목표

Amazon CloudWatch Container Insights를 EKS 클러스터에 설치하고, Day 2 애플리케이션의
컨테이너·Pod·노드 메트릭을 CloudWatch Metrics에 수집한 뒤 대시보드를 구성합니다.

### 아키텍처

```
EKS Node
  └─ CloudWatch Agent (DaemonSet — Container Insights add-on)
       │  IRSA (IAM Role via ServiceAccount)
       ▼
  AWS CloudWatch Metrics
       └─ 네임스페이스: ContainerInsights
            ├─ 차원: ClusterName / Namespace / Service / PodName / NodeName
            └─ 메트릭: pod_cpu_utilization, pod_memory_utilization, ...
                  ▼
            CloudWatch Dashboard  ←  자동 생성 (Container Insights)
                                  ←  커스텀 생성 가능
```

### Container Insights 주요 메트릭

| 메트릭 이름 | 단위 | 설명 |
|------------|------|------|
| `pod_cpu_utilization` | % | Pod CPU 사용률 (limit 대비) |
| `pod_memory_utilization` | % | Pod 메모리 사용률 (limit 대비) |
| `pod_number_of_container_restarts` | count | 컨테이너 재시작 누적 횟수 |
| `pod_network_rx_bytes` | bytes/s | Pod 네트워크 수신량 |
| `pod_network_tx_bytes` | bytes/s | Pod 네트워크 송신량 |
| `node_cpu_utilization` | % | 노드 CPU 사용률 |
| `node_memory_utilization` | % | 노드 메모리 사용률 |
| `node_filesystem_utilization` | % | 노드 디스크 사용률 |
| `cluster_node_count` | count | 클러스터 노드 수 |
| `cluster_failed_node_count` | count | 장애 노드 수 |

---

## Step 1: Container Insights 설치

`container-insights-irsa.yaml` 주석의 절차를 따르거나, 아래 명령을 순서대로 실행합니다.

```bash
# 1) OIDC Provider 연결
eksctl utils associate-iam-oidc-provider \
  --cluster eks-demo-cluster \
  --region ap-northeast-2 \
  --approve

# 2) CloudWatch Agent IRSA 생성 (AWS 관리형 정책 사용)
eksctl create iamserviceaccount \
  --cluster     eks-demo-cluster \
  --region      ap-northeast-2 \
  --namespace   amazon-cloudwatch \
  --name        cloudwatch-agent \
  --attach-policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy \
  --approve

# 3) IRSA ARN 확인
ROLE_ARN=$(aws iam get-role \
  --role-name eks-demo-cluster-cloudwatch-agent \
  --query Role.Arn --output text 2>/dev/null || \
  kubectl get serviceaccount cloudwatch-agent -n amazon-cloudwatch \
  -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}')
echo "ROLE_ARN: ${ROLE_ARN}"

# 4) EKS Add-on 설치
aws eks create-addon \
  --cluster-name eks-demo-cluster \
  --addon-name amazon-cloudwatch-observability \
  --service-account-role-arn "${ROLE_ARN}" \
  --region ap-northeast-2

# 5) 설치 완료 확인 (ACTIVE 될 때까지 대기)
aws eks wait addon-active \
  --cluster-name eks-demo-cluster \
  --addon-name amazon-cloudwatch-observability \
  --region ap-northeast-2

# 6) DaemonSet Pod 확인
kubectl get pods -n amazon-cloudwatch
# cloudwatch-agent-xxxxx 가 노드마다 1개씩 Running 상태여야 합니다
```

---

## Step 2: 메트릭 수집 확인 (AWS CLI)

설치 후 약 2~3분이 지나면 CloudWatch에 메트릭이 수집됩니다.

```bash
# demo 네임스페이스 관련 메트릭 목록 확인
aws cloudwatch list-metrics \
  --namespace ContainerInsights \
  --region ap-northeast-2 \
  --dimensions Name=Namespace,Value=demo \
  --query 'Metrics[*].MetricName' \
  --output text | tr '\t' '\n' | sort -u

# cpu-load Pod CPU 사용률 최근 10분 조회
aws cloudwatch get-metric-statistics \
  --namespace ContainerInsights \
  --metric-name pod_cpu_utilization \
  --dimensions \
    Name=ClusterName,Value=eks-demo-cluster \
    Name=Namespace,Value=demo \
    Name=Service,Value=cpu-load \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time   $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Average Maximum \
  --region ap-northeast-2 \
  --query 'Datapoints | sort_by(@, &Timestamp)' \
  --output table

# memory-load Pod 메모리 사용률 최근 10분 조회
aws cloudwatch get-metric-statistics \
  --namespace ContainerInsights \
  --metric-name pod_memory_utilization \
  --dimensions \
    Name=ClusterName,Value=eks-demo-cluster \
    Name=Namespace,Value=demo \
    Name=Service,Value=memory-load \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time   $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Average Maximum \
  --region ap-northeast-2 \
  --query 'Datapoints | sort_by(@, &Timestamp)' \
  --output table
```

---

## Step 3: Container Insights 자동 대시보드 탐색

AWS 콘솔에서 자동 생성된 Container Insights 대시보드를 탐색합니다.

**경로**: CloudWatch → Container Insights → Performance monitoring

탐색 단계:

1. **클러스터 보기**: `eks-demo-cluster` 선택 → CPU·메모리·노드 수 확인
2. **네임스페이스 보기**: `demo` 선택 → Pod별 CPU·메모리·재시작 현황
3. **서비스 보기**: `cpu-load`, `memory-load` 등 각 앱 선택
4. **Pod 보기**: 개별 Pod 드릴다운 → 컨테이너별 리소스 확인

**관찰 포인트**:
- 각 앱의 CPU/메모리 사용량이 requests·limits 값과 어떤 관계인지 확인
- 재시작 횟수(`pod_number_of_container_restarts`)가 0인지 확인

---

## Step 4: CloudWatch Metrics 탐색 및 Metric Math

**경로**: CloudWatch → Metrics → All metrics → ContainerInsights

### 4-1. 기본 메트릭 그래프

1. `ContainerInsights` 선택
2. `ClusterName, Namespace, Service` 차원 선택
3. `demo` 네임스페이스 필터
4. `pod_cpu_utilization` 선택 후 그래프 확인

### 4-2. Metric Math — USE 패턴

Graphed metrics 탭 → Add math → Start with empty expression:

```
# CPU limits 대비 사용률 (pod_cpu_utilization은 이미 limit % 기준)
# → pod_cpu_utilization 을 직접 사용

# 메모리 limits 대비 사용률
# → pod_memory_utilization 을 직접 사용

# 클러스터 전체 Pod 재시작 합계 (5분 기준)
# Expression: SUM(METRICS("m1"))
# m1: pod_number_of_container_restarts, 차원: ClusterName + Namespace=demo
```

### 4-3. Metric Math — 이상 감지 (Anomaly Detection)

```
# CloudWatch 콘솔 → Metrics → 그래프에서 특정 메트릭 선택
# → "Add anomaly detection" 클릭
# → 학습 기간(Training period): 14일 권장
# → 이상 대역폭 설정 (표준 편차 2배 = 95% 신뢰구간)
```

---

## Step 5: CloudWatch 대시보드 직접 생성

**경로**: CloudWatch → Dashboards → Create dashboard → `eks-demo-dashboard`

### 위젯 1: demo 앱 CPU 사용률 비교 (Line chart)

- 메트릭: `ContainerInsights > ClusterName, Namespace, Service`
- 선택: `pod_cpu_utilization` (basic, mysql-app, cpu-load, memory-load, slow-response 각 1개)
- Period: 1분
- 제목: `Demo Apps CPU Utilization (%)`

### 위젯 2: demo 앱 메모리 사용률 비교 (Line chart)

- 메트릭: `ContainerInsights > ClusterName, Namespace, Service`
- 선택: `pod_memory_utilization` (5개 앱 모두)
- Period: 1분
- 제목: `Demo Apps Memory Utilization (%)`

### 위젯 3: 컨테이너 재시작 횟수 (Number)

- 메트릭: `ContainerInsights`, `pod_number_of_container_restarts`
- 차원: ClusterName=eks-demo-cluster, Namespace=demo
- Statistics: Sum, Period: 5분
- 제목: `Container Restarts (5m)`

### 위젯 4: 노드 CPU/메모리 사용률 (Gauge)

- 메트릭: `node_cpu_utilization`, `node_memory_utilization`
- 차원: ClusterName=eks-demo-cluster
- 제목: `Node Resource Utilization`
- Min/Max: 0 / 100

---

## Step 6: 부하 시나리오별 메트릭 관찰

각 시나리오를 실행하며 CloudWatch 대시보드에서 메트릭 변화를 실시간으로 관찰합니다.

### 시나리오 A: CPU 부하 → HPA Scale-Out

```bash
# CPU 부하 시작 (60초, 2 workers)
curl -X POST http://<INGRESS_HOST>/cpu/load \
  -H "Content-Type: application/json" \
  -d '{"duration": 60, "workers": 2}'

# kubectl로 HPA 상태 실시간 확인
kubectl get hpa cpu-load -n demo -w
```

CloudWatch에서 관찰:
```bash
# pod_cpu_utilization 증가 확인 (CLI)
watch -n 30 'aws cloudwatch get-metric-statistics \
  --namespace ContainerInsights \
  --metric-name pod_cpu_utilization \
  --dimensions \
    Name=ClusterName,Value=eks-demo-cluster \
    Name=Namespace,Value=demo \
    Name=Service,Value=cpu-load \
  --start-time $(date -u -d "5 minutes ago" +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 --statistics Average \
  --region ap-northeast-2 \
  --query "sort_by(Datapoints, &Timestamp)[-1]"'
```

**관찰 포인트**:
1. `pod_cpu_utilization` 급증 시점 기록
2. HPA Scale-Out 발생 후 Pod당 CPU 사용률 감소 확인
3. CloudWatch 메트릭 갱신 지연(약 1분)을 kubectl top과 비교

### 시나리오 B: 메모리 누수 → OOMKilled

```bash
# 메모리 limits를 낮게 설정 후 누수 시뮬레이션
kubectl patch deployment memory-load -n demo \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"200Mi"}]'

curl -X POST http://<INGRESS_HOST>/memory/leak \
  -H "Content-Type: application/json" \
  -d '{"mb": 50, "interval": 1}'
```

CloudWatch에서 관찰:
```bash
# pod_memory_utilization 및 재시작 횟수 확인
aws cloudwatch get-metric-statistics \
  --namespace ContainerInsights \
  --metric-name pod_number_of_container_restarts \
  --dimensions \
    Name=ClusterName,Value=eks-demo-cluster \
    Name=Namespace,Value=demo \
    Name=Service,Value=memory-load \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 --statistics Maximum \
  --region ap-northeast-2 \
  --query 'sort_by(Datapoints, &Timestamp)' \
  --output table

# limits 복원
curl -X POST http://<INGRESS_HOST>/memory/leak/stop
kubectl patch deployment memory-load -n demo \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}]'
```

---

## 과제 질문

1. **CPU Throttling vs OOMKilled**: CPU limits를 초과하면 Throttling, 메모리 limits를 초과하면 OOMKilled가 발생합니다. CloudWatch Container Insights에서 두 현상을 각각 어떤 메트릭으로 감지할 수 있는지 서술하고, `pod_cpu_utilization_over_pod_limit` 메트릭이 존재하는지 확인해보세요.

2. **HPA 반응 지연**: CPU 부하를 시작한 직후 HPA가 즉시 Scale-Out하지 않는 이유를 설명하고, CloudWatch 메트릭의 1분 주기 갱신이 HPA 반응에 영향을 주는지 판단하세요. (힌트: HPA는 Metrics API를 통해 cAdvisor 데이터를 직접 사용합니다)

3. **Metric Math 작성**: CloudWatch Metrics 콘솔에서 Metric Math를 사용하여 `cpu-load` 서비스의 CPU 사용률이 전체 demo 네임스페이스 평균의 몇 배인지 계산하는 수식을 작성하세요.

4. **RED vs USE 적용**: Day 2의 5개 앱 중 RED 패턴이 적합한 앱과 USE 패턴이 적합한 앱을 각각 구분하고, CloudWatch Container Insights에서 각 패턴을 구현하는 데 어떤 메트릭을 사용해야 하는지 서술하세요.

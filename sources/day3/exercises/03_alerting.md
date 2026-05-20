# 실습 3: 알람 설정 및 장애 대응 시나리오

## 목표

AWS CloudWatch Alarms를 생성하여 Day 2 애플리케이션의 이상 상태를 자동으로 감지하고,
SNS를 통해 이메일로 알림을 받습니다. 각 장애 시나리오를 직접 유발하여 알람이 정상 동작하는지 검증합니다.

### 아키텍처

```
CloudWatch Metrics (ContainerInsights)
       │
       ├─ Metric Alarm (임계값 기반)
       │       │ ALARM 상태 전환 시
       │       ▼
       │  SNS Topic (eks-demo-alerts)
       │       ├─ 이메일 구독자
       │       └─ (확장) Slack / PagerDuty / Lambda
       │
       └─ Composite Alarm (여러 알람 조합)
```

---

## Step 1: SNS Topic 생성 및 이메일 구독

```bash
# SNS Topic 생성
SNS_ARN=$(aws sns create-topic \
  --name eks-demo-alerts \
  --region ap-northeast-2 \
  --query TopicArn \
  --output text)
echo "SNS Topic ARN: ${SNS_ARN}"

# 이메일 구독 추가 (본인 이메일로 교체)
aws sns subscribe \
  --topic-arn "${SNS_ARN}" \
  --protocol email \
  --notification-endpoint "your-email@example.com" \
  --region ap-northeast-2

# 구독 확인 이메일이 도착하면 "Confirm subscription" 링크 클릭
# 구독 상태 확인
aws sns list-subscriptions-by-topic \
  --topic-arn "${SNS_ARN}" \
  --region ap-northeast-2 \
  --query 'Subscriptions[*].{Protocol:Protocol,Endpoint:Endpoint,Status:SubscriptionArn}' \
  --output table
```

---

## Step 2: CloudWatch Alarms 생성

```bash
# SNS ARN을 환경변수로 설정 후 스크립트 실행
export SNS_ARN=$(aws sns get-topic-attributes \
  --topic-arn $(aws sns list-topics --region ap-northeast-2 \
    --query "Topics[?contains(TopicArn,'eks-demo-alerts')].TopicArn" \
    --output text) \
  --query Attributes.TopicArn \
  --output text 2>/dev/null || \
  aws sns list-topics --region ap-northeast-2 \
    --query "Topics[?contains(TopicArn,'eks-demo-alerts')].TopicArn" \
    --output text)

SNS_ARN="${SNS_ARN}" ../k8s/monitoring/cloudwatch-alarms.sh
```

생성 확인:

```bash
# 생성된 알람 목록 및 상태 확인
aws cloudwatch describe-alarms \
  --alarm-name-prefix "EKS-eks-demo-cluster" \
  --region ap-northeast-2 \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue,Threshold:Threshold}' \
  --output table
```

생성되는 알람 목록:

| 알람 이름 | 조건 | 심각도 |
|---------|------|------|
| `...-cpu-load-HighCPU` | cpu-load CPU 사용률 > 80% (5분) | Warning |
| `...-memory-load-HighMemory-Warning` | memory-load 메모리 > 80% (1분) | Warning |
| `...-memory-load-HighMemory-Critical` | memory-load 메모리 > 95% (1분) | Critical |
| `...-ContainerRestarts` | demo 네임스페이스 재시작 > 3회 (5분) | Warning |
| `...-Node-HighCPU` | 노드 CPU > 80% (5분) | Warning |
| `...-Node-HighMemory` | 노드 메모리 > 85% (5분) | Warning |
| `...-Node-HighDisk` | 노드 디스크 > 80% | Warning |
| `...-demo-Overall-Health` | Composite (Critical + Restarts + NodeMem) | Composite |

---

## Step 3: 장애 시나리오별 알람 검증

### 시나리오 1: OOMKilled — `memory-load-HighMemory-Critical`

**목표**: 메모리 limits를 낮추고 누수를 유발하여 Critical 알람 발생

```bash
# Step 1: memory-load의 메모리 limit을 200Mi로 낮춤
kubectl patch deployment memory-load -n demo \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"200Mi"}]'

# Step 2: 메모리 누수 시작 (50MB씩 1초 간격)
curl -X POST http://<INGRESS_HOST>/memory/leak \
  -H "Content-Type: application/json" \
  -d '{"mb": 50, "interval": 1}'

# Step 3: 알람 상태 실시간 모니터링
watch -n 30 'aws cloudwatch describe-alarms \
  --alarm-names \
    "EKS-eks-demo-cluster-demo-memory-load-HighMemory-Warning" \
    "EKS-eks-demo-cluster-demo-memory-load-HighMemory-Critical" \
    "EKS-eks-demo-cluster-demo-ContainerRestarts" \
  --region ap-northeast-2 \
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue}" \
  --output table'
```

**관찰 순서**:
1. `HighMemory-Warning` (> 80%) 알람이 먼저 ALARM 전환
2. `HighMemory-Critical` (> 95%) 알람이 ALARM 전환 후 SNS 이메일 수신
3. OOMKilled 발생 → Pod 재시작 → `ContainerRestarts` 알람 발생
4. Pod 재시작 후 메모리 리셋 → 알람 OK 전환

```bash
# 알람 히스토리 확인
aws cloudwatch describe-alarm-history \
  --alarm-name "EKS-eks-demo-cluster-demo-memory-load-HighMemory-Critical" \
  --history-item-type StateUpdate \
  --region ap-northeast-2 \
  --query 'AlarmHistoryItems[*].{Time:Timestamp,Summary:HistorySummary}' \
  --output table

# 원상 복구
curl -X POST http://<INGRESS_HOST>/memory/leak/stop
kubectl patch deployment memory-load -n demo \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}]'
```

**체크리스트**:
- [ ] `HighMemory-Warning` 알람이 먼저 ALARM 상태로 전환되는가?
- [ ] `HighMemory-Critical` 알람 발생 시 SNS 이메일이 도착하는가?
- [ ] Pod 재시작 후 `ContainerRestarts` 알람도 발생하는가?
- [ ] `Overall-Health` Composite 알람도 연동되어 발생하는가?
- [ ] 메모리 복구 후 알람이 OK로 돌아오는가?

---

### 시나리오 2: CPU 부하 → `cpu-load-HighCPU` 알람

**목표**: CPU 집중 부하로 알람 발생 후 HPA Scale-Out 동작 확인

```bash
# Step 1: CPU 부하 발생 (120초)
curl -X POST http://<INGRESS_HOST>/cpu/load \
  -H "Content-Type: application/json" \
  -d '{"duration": 120, "workers": 4}'

# Step 2: HPA 상태 확인
kubectl get hpa cpu-load -n demo -w

# Step 3: 알람 상태 확인
aws cloudwatch describe-alarms \
  --alarm-names "EKS-eks-demo-cluster-demo-cpu-load-HighCPU" \
  --region ap-northeast-2 \
  --query 'MetricAlarms[*].{State:StateValue,Reason:StateReason}' \
  --output table
```

**관찰 포인트**:
- CPU 부하 발생 → CloudWatch 메트릭 반영까지 약 1~2분 지연 존재
- 알람 조건: 5분 평균 > 80% (EvaluationPeriods: 2 × Period: 300s = 10분 후 알람 발생)
- HPA는 실시간 cAdvisor 데이터를 사용하므로 Scale-Out이 먼저 발생할 수 있음

```bash
# 부하 중지
curl -X POST http://<INGRESS_HOST>/cpu/stop
```

---

### 시나리오 3: 컨테이너 재시작 — `ContainerRestarts` 알람

**목표**: 잘못된 이미지로 Pod 반복 실패 유발

```bash
# 존재하지 않는 이미지 태그로 Deployment 수정
kubectl set image deployment/basic -n demo \
  basic=public.ecr.aws/invalid-repo/day2-01-basic:v999

# Pod 이벤트 확인
kubectl get pods -n demo -l app=basic -w
kubectl describe pod -n demo -l app=basic | grep -A 5 Events

# 알람 상태 확인 (재시작 임계값 3회 초과 후)
aws cloudwatch describe-alarms \
  --alarm-names "EKS-eks-demo-cluster-demo-ContainerRestarts" \
  --region ap-northeast-2 \
  --query 'MetricAlarms[*].{State:StateValue,Reason:StateReason}' \
  --output table

# 원래 이미지로 롤백
kubectl rollout undo deployment/basic -n demo
kubectl rollout status deployment/basic -n demo
```

---

### 시나리오 4: Alarm State 수동 테스트

실제 장애를 유발하지 않고 알람 알림 수신을 테스트하는 방법입니다.

```bash
# 알람을 강제로 ALARM 상태로 전환
aws cloudwatch set-alarm-state \
  --alarm-name "EKS-eks-demo-cluster-demo-cpu-load-HighCPU" \
  --state-value ALARM \
  --state-reason "실습 테스트: 수동 알람 상태 변경" \
  --region ap-northeast-2

# SNS 이메일 수신 확인 후 OK로 복구
aws cloudwatch set-alarm-state \
  --alarm-name "EKS-eks-demo-cluster-demo-cpu-load-HighCPU" \
  --state-value OK \
  --state-reason "실습 테스트: 수동 복구" \
  --region ap-northeast-2
```

---

## Step 4: Composite Alarm 동작 이해

Composite Alarm은 여러 알람의 논리 조합으로 복합적인 장애를 표현합니다.

```bash
# Composite Alarm 현재 상태 확인
aws cloudwatch describe-alarms \
  --alarm-names "EKS-eks-demo-cluster-demo-Overall-Health" \
  --alarm-types CompositeAlarm \
  --region ap-northeast-2 \
  --query 'CompositeAlarms[*].{Name:AlarmName,State:StateValue,Rule:AlarmRule}' \
  --output table

# Composite Alarm 히스토리 확인
aws cloudwatch describe-alarm-history \
  --alarm-name "EKS-eks-demo-cluster-demo-Overall-Health" \
  --region ap-northeast-2 \
  --query 'AlarmHistoryItems[*].{Time:Timestamp,Summary:HistorySummary}' \
  --output table
```

**Composite Alarm의 장점**:
- 여러 알람이 동시에 발생할 때 **중복 알림을 방지** (Overall-Health 하나만 발송)
- AND/OR 논리로 복합 조건 표현 가능
- 알람 계층 구조로 NOC(Network Operations Center) 대시보드 구성에 적합

---

## Step 5: 알람 Runbook 작성 실습

아래 템플릿을 사용해 `memory-load-HighMemory-Critical` 알람의 Runbook을 작성하세요.

```markdown
# Runbook: EKS-eks-demo-cluster-demo-memory-load-HighMemory-Critical

## 알람 조건
memory-load Pod 메모리 사용률이 limits의 95%를 1분 이상 초과.

## 영향
OOMKilled 임박. Pod 재시작 시 처리 중인 요청 유실 가능.

## 즉각 진단 (5분 이내)

1. Pod 상태 확인
   ```bash
   kubectl get pods -n demo -l app=memory-load
   kubectl describe pod -n demo -l app=memory-load | grep -A 5 "Last State"
   ```

2. 메모리 현황 확인 (CloudWatch CLI)
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace ContainerInsights \
     --metric-name pod_memory_utilization \
     --dimensions \
       Name=ClusterName,Value=eks-demo-cluster \
       Name=Namespace,Value=demo \
       Name=Service,Value=memory-load \
     --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
     --period 60 --statistics Maximum \
     --region ap-northeast-2
   ```

3. 로그에서 메모리 할당 패턴 확인
   ```bash
   # CloudWatch Logs Insights
   # 로그 그룹: /eks/eks-demo-cluster/demo/memory-load
   # 쿼리: fields @timestamp, @message | filter @message like /allocat/ | sort @timestamp desc | limit 50
   ```

## 대응 방법
- **메모리 누수 진행 중**: `POST /memory/leak/stop` 즉시 호출
- **일시적 대용량 할당**: `POST /memory/release` 호출 후 원인 파악
- **limits 부족**: limits 상향 후 재배포 (임시 조치)

## 조치 후 확인
- `pod_number_of_container_restarts` 가 더 이상 증가하지 않는지 10분 관찰
- `memory-load-HighMemory-Warning` 알람이 OK 상태로 돌아왔는지 확인
```

---

## Step 6: SLI / SLO 정의 및 CloudWatch 연동

Day 2 `basic` 앱을 기준으로 SLI와 SLO를 정의하고 CloudWatch Alarm으로 연동합니다.

### SLI 측정 메트릭 선정

Container Insights 기준으로 아래 표를 완성하세요:

| SLI | CloudWatch 메트릭 | 네임스페이스 | 차원 |
|-----|----------------|------------|------|
| 가용성 (Pod Ready 비율) | `pod_number_of_container_restarts` | ContainerInsights | ClusterName, Namespace, Service |
| 지연 (응답 시간) | — (Container Insights 미제공, ALB Access Log 필요) | — | — |
| 오류율 | — (Application Log 기반 Metric Filter 필요) | — | — |

### SLO 알람 생성 예시 (Pod 재시작 기준 가용성)

```bash
# 1시간 동안 재시작 횟수가 5회를 초과하면 SLO 위반으로 간주
aws cloudwatch put-metric-alarm \
  --region ap-northeast-2 \
  --alarm-name "EKS-eks-demo-cluster-demo-basic-SLO-Availability" \
  --alarm-description "basic 앱 SLO 위반: 1시간 재시작 5회 초과" \
  --namespace ContainerInsights \
  --metric-name pod_number_of_container_restarts \
  --dimensions \
    Name=ClusterName,Value=eks-demo-cluster \
    Name=Namespace,Value=demo \
    Name=Service,Value=basic \
  --statistic Sum \
  --period 3600 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}"
```

SLO 정의 (작성 과제):

| SLI | 측정 방법 | SLO 목표값 | CloudWatch Alarm 임계값 |
|-----|---------|-----------|----------------------|
| 가용성 (재시작 없음) | `pod_number_of_container_restarts` Sum/1h | 0회/시간 | > 5회/시간 |
| OOMKilled 없음 | `pod_number_of_container_restarts` (OOM 원인) | 0회/일 | > 1회/일 |
| 노드 CPU 정상 | `node_cpu_utilization` Average | < 70% | > 80% |
| 노드 메모리 정상 | `node_memory_utilization` Average | < 75% | > 85% |

---

## 과제 질문

1. **알람 피로도(Alert Fatigue)**: `cloudwatch-alarms.sh`에서 `cpu-load-HighCPU` 알람의 EvaluationPeriods를 2로 설정했습니다(총 10분 초과 시 발동). HPA가 Scale-Out하면 Pod당 CPU가 낮아져 알람이 OK로 돌아옵니다. 이 경우 알람이 반복적으로 ALARM/OK를 오가는 "Flapping" 현상이 발생할 수 있습니다. 이를 방지하려면 알람 설정을 어떻게 바꾸어야 하는지 서술하세요. (힌트: `treat-missing-data`, `evaluation-periods` 조정)

2. **증상 기반 vs 원인 기반 알람**: 현재 생성한 알람들은 CPU/메모리 사용률 등 자원(원인) 기반입니다. 사용자가 실제로 서비스 장애를 체감할 때만 알람이 발생하도록 "증상 기반" 알람을 설계하려면 어떤 데이터 소스와 메트릭이 필요한지 서술하세요. (힌트: ALB Access Log → CloudWatch Logs → Metric Filter)

3. **Error Budget 계산**: `basic` 앱의 SLO가 "월간 재시작 횟수 0회"로 설정되어 있을 때 엄격히 적용하면 배포(Deployment 업데이트)도 Error Budget을 소진합니다. 이 문제를 어떻게 해결해야 하는지 서술하세요.

4. **CloudWatch vs Prometheus 비교**: 이번 실습에서 사용한 CloudWatch Alarms와 강의에서 소개한 Prometheus + Alertmanager 방식을 비교하세요. 각 방식의 장단점을 운영 비용, 유연성, EKS 통합 편의성 측면에서 서술하세요.

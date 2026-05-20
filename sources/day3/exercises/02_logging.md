# 실습 2: 로그 수집 및 CloudWatch Logs 검색

## 목표

Fluent Bit DaemonSet을 배포하여 Day 2 애플리케이션의 컨테이너 로그를 AWS CloudWatch Logs로 수집하고,
CloudWatch Logs Insights에서 로그를 검색·분석합니다.

### 아키텍처

```
EKS Node
  └─ /var/log/containers/*.log
       │
       └─ Fluent Bit (DaemonSet, 노드마다 1개)
            │  IRSA (IAM Role via ServiceAccount)
            ▼
       AWS CloudWatch Logs
            ├─ Log Group: /eks/eks-demo-cluster/demo/basic
            ├─ Log Group: /eks/eks-demo-cluster/demo/mysql-app
            ├─ Log Group: /eks/eks-demo-cluster/demo/cpu-load
            ├─ Log Group: /eks/eks-demo-cluster/demo/memory-load
            └─ Log Group: /eks/eks-demo-cluster/demo/slow-response
                 └─ Log Stream: <pod-name>/<container-name>
```

---

## Step 1: IRSA(IAM Roles for Service Accounts) 설정

Fluent Bit Pod가 CloudWatch Logs에 쓰기 권한을 갖도록 IRSA를 설정합니다.

`cloudwatch-irsa.yaml` 주석의 절차를 따르거나, 아래 명령을 순서대로 실행합니다.

```bash
# 1) OIDC Provider 연결 확인 및 생성
eksctl utils associate-iam-oidc-provider \
  --cluster eks-demo-cluster \
  --region ap-northeast-2 \
  --approve

# 2) IAM 정책 JSON 파일 생성
cat > FluentBitCloudWatchPolicy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:PutRetentionPolicy"
      ],
      "Resource": "arn:aws:logs:ap-northeast-2:*:log-group:/eks/eks-demo-cluster/*"
    }
  ]
}
EOF

# 3) IAM 정책 생성
aws iam create-policy \
  --policy-name FluentBitCloudWatchPolicy \
  --policy-document file://FluentBitCloudWatchPolicy.json \
  --region ap-northeast-2

# 4) IRSA 생성 (ServiceAccount에 IAM Role 바인딩)
eksctl create iamserviceaccount \
  --cluster     eks-demo-cluster \
  --region      ap-northeast-2 \
  --namespace   logging \
  --name        fluentbit \
  --attach-policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/FluentBitCloudWatchPolicy \
  --approve \
  --override-existing-serviceaccounts

# 5) ServiceAccount에 IRSA 어노테이션이 설정되었는지 확인
kubectl get serviceaccount fluentbit -n logging -o yaml | grep role-arn
```

---

## Step 2: Fluent Bit 배포

```bash
# logging 네임스페이스 생성
kubectl apply -f ../k8s/logging/namespace.yaml

# ConfigMap 배포 (Fluent Bit 파이프라인 설정)
kubectl apply -f ../k8s/logging/fluentbit-configmap.yaml

# DaemonSet 배포
# 주의: fluentbit-daemonset.yaml의 ServiceAccount가 IRSA로 이미 생성된 경우
#       ServiceAccount 섹션을 건너뛰고 DaemonSet만 배포합니다.
kubectl apply -f ../k8s/logging/fluentbit-daemonset.yaml

# DaemonSet 상태 확인 (노드 수만큼 Pod가 생성되어야 함)
kubectl get daemonset fluentbit -n logging
kubectl get pods -n logging -l app=fluentbit -o wide
```

---

## Step 3: Fluent Bit 동작 확인

```bash
# Fluent Bit Pod 로그 확인
# "CloudWatch" 출력 플러그인 초기화 로그와 레코드 전송 로그 확인
kubectl logs -n logging -l app=fluentbit --tail=50

# 정상 동작 시 아래와 같은 로그가 출력됩니다:
# [2026/05/20 ...] [info]  [output:cloudwatch_logs] plugin has been enabled.
# [2026/05/20 ...] [info]  Created log group: /eks/eks-demo-cluster/demo/basic

# Fluent Bit 내부 메트릭 확인
kubectl port-forward -n logging daemonset/fluentbit 2020:2020
curl http://localhost:2020/api/v1/metrics | python3 -m json.tool
```

**확인 항목**:
- `fluentbit_output_proc_records_total`: 처리된 레코드 수 (증가 중이어야 함)
- `fluentbit_output_retries_total`: 재전송 횟수 (증가 시 CloudWatch API 연결 문제)
- `fluentbit_output_dropped_records_total`: 유실된 레코드 수 (0이어야 정상)

---

## Step 4: CloudWatch Logs 그룹 확인

```bash
# 생성된 로그 그룹 목록 확인
aws logs describe-log-groups \
  --log-group-name-prefix /eks/eks-demo-cluster/demo \
  --region ap-northeast-2 \
  --query 'logGroups[*].{name:logGroupName,retention:retentionInDays}' \
  --output table

# 예상 출력:
# ------------------------------------------------------------------------------------------------
# |                                      DescribeLogGroups                                      |
# +--------------------------------------------------------------+---------------------------------+
# |                           name                              |           retention             |
# +--------------------------------------------------------------+---------------------------------+
# |  /eks/eks-demo-cluster/demo/basic                           |  30                             |
# |  /eks/eks-demo-cluster/demo/cpu-load                        |  30                             |
# |  /eks/eks-demo-cluster/demo/memory-load                     |  30                             |
# |  /eks/eks-demo-cluster/demo/mysql-app                       |  30                             |
# |  /eks/eks-demo-cluster/demo/slow-response                   |  30                             |
# +--------------------------------------------------------------+---------------------------------+

# 특정 앱의 로그 스트림 목록 확인
aws logs describe-log-streams \
  --log-group-name /eks/eks-demo-cluster/demo/basic \
  --region ap-northeast-2 \
  --query 'logStreams[*].logStreamName' \
  --output table

# 최근 로그 이벤트 직접 조회 (CLI)
aws logs get-log-events \
  --log-group-name /eks/eks-demo-cluster/demo/basic \
  --log-stream-name <pod-name>/basic \
  --region ap-northeast-2 \
  --limit 20 \
  --query 'events[*].message' \
  --output text
```

---

## Step 5: CloudWatch Logs Insights 쿼리 실습

AWS 콘솔 → CloudWatch → Logs Insights에서 아래 쿼리를 실습합니다.

### 5-1. 기본 로그 조회

```
# basic 앱의 최근 로그 100건
# 로그 그룹: /eks/eks-demo-cluster/demo/basic
fields @timestamp, @message
| sort @timestamp desc
| limit 100
```

```
# 모든 demo 앱의 로그 (로그 그룹 여러 개 선택 후 실행)
# 로그 그룹: /eks/eks-demo-cluster/demo/* (여러 개 선택)
fields @timestamp, @logStream, @message
| sort @timestamp desc
| limit 50
```

### 5-2. 시나리오별 로그 검색

**MySQL 앱 — DB 연결 상태 로그**

```bash
# mysql-app의 헬스체크를 반복 호출하여 로그 생성
for i in $(seq 1 10); do
  curl -s http://<INGRESS_HOST>/health | python3 -m json.tool
  sleep 1
done
```

```
# 로그 그룹: /eks/eks-demo-cluster/demo/mysql-app
fields @timestamp, @message
| filter @message like /health/
| sort @timestamp desc
| limit 50
```

**CPU Load 앱 — 부하 발생 로그**

```bash
curl -X POST http://<INGRESS_HOST>/cpu/load \
  -H "Content-Type: application/json" \
  -d '{"duration": 30, "workers": 2}'
```

```
# 로그 그룹: /eks/eks-demo-cluster/demo/cpu-load
fields @timestamp, @message
| filter @message like /started/ or @message like /stopped/
| sort @timestamp desc
```

**Slow Response 앱 — 응답 지연 로그**

```bash
for i in $(seq 1 3); do
  curl -s "http://<INGRESS_HOST>/slow/custom?seconds=5" &
done
wait
```

```
# 로그 그룹: /eks/eks-demo-cluster/demo/slow-response
fields @timestamp, @message
| sort @timestamp desc
| limit 30
```

### 5-3. 에러 로그 집계

```bash
# mysql-app에 잘못된 데이터로 요청하여 에러 유발
curl -X POST http://<INGRESS_HOST>/mysql/users \
  -H "Content-Type: application/json" \
  -d '{"name": "", "email": ""}'

curl http://<INGRESS_HOST>/mysql/users/99999
```

```
# 로그 그룹: /eks/eks-demo-cluster/demo/mysql-app
# HTTP 4xx / 5xx 에러 패턴 집계
fields @timestamp, @message
| filter @message like / 400 / or @message like / 404 / or @message like / 500 /
| stats count() as error_count by bin(5m)
| sort @timestamp desc
```

### 5-4. 시간대별 로그 볼륨 분석

```
# 로그 그룹 여러 개 선택 후 실행
# 1분 단위 앱별 로그 발생량 집계
fields @timestamp, @logStream
| stats count() as log_count by bin(1m)
| sort @timestamp desc
```

### 5-5. 로그 스트림(Pod)별 로그량 비교

```
# 로그 그룹: /eks/eks-demo-cluster/demo/basic
fields @timestamp, @logStream, @message
| stats count() as log_count by @logStream
| sort log_count desc
```

---

## Step 6: Back-Pressure 시뮬레이션 관찰

고빈도 요청으로 대량의 로그를 생성하여 Fluent Bit 버퍼 동작을 관찰합니다.

```bash
# 고빈도 요청으로 대량 로그 생성 (별도 터미널에서 실행)
while true; do
  curl -s http://<INGRESS_HOST>/basic > /dev/null
  curl -s http://<INGRESS_HOST>/cpu > /dev/null
done
```

```bash
# Fluent Bit 메트릭 모니터링 (5초 간격)
watch -n 5 'kubectl exec -n logging \
  $(kubectl get pods -n logging -l app=fluentbit -o jsonpath="{.items[0].metadata.name}") \
  -- curl -s localhost:2020/api/v1/metrics | python3 -m json.tool'
```

**관찰 포인트**:
- `output.proc_records` 증가율이 `input.records` 증가율보다 낮아지면 Back-Pressure 발생
- `output.retries` 값이 증가하면 CloudWatch API 처리 속도가 부족한 상태
- CloudWatch Logs Insights에서 로그 도착 지연 여부 확인

---

## Step 7: CloudWatch Logs 비용 구조 이해

```bash
# 현재 로그 그룹 총 용량 확인
aws logs describe-log-groups \
  --log-group-name-prefix /eks/eks-demo-cluster/demo \
  --region ap-northeast-2 \
  --query 'logGroups[*].{name:logGroupName,storedBytes:storedBytes}' \
  --output table
```

CloudWatch Logs 비용 구성:

| 항목 | 단가 (ap-northeast-2) | 비고 |
|------|----------------------|------|
| 수집(Ingest) | $0.76 / GB | PutLogEvents API 호출량 |
| 저장(Storage) | $0.033 / GB·월 | 보존 기간만큼 과금 |
| Insights 쿼리 | $0.0076 / GB 스캔 | 쿼리한 데이터양 기준 |

**비용 최적화 포인트**:
- `log_retention_days` 설정으로 불필요한 로그 자동 삭제
- DEBUG/TRACE 로그는 Fluent Bit FILTER에서 제외하여 수집량 감소
- 자주 쿼리하는 패턴은 CloudWatch Metric Filter로 메트릭화 (Insights 쿼리 비용 절감)

---

## 과제 질문

1. **구조화 로그의 이점**: Day 2 앱들은 gunicorn 기본 텍스트 포맷으로 로그를 출력합니다. `basic` 앱의 `app.py`를 수정하여 JSON 구조화 로그(`timestamp`, `level`, `service`, `path`, `status`, `response_time` 포함)를 출력하도록 개선하세요. 개선 전후 CloudWatch Logs Insights에서 필드 기반 쿼리가 어떻게 달라지는지 비교하세요.

2. **로그 레벨 필터링**: `fluentbit-configmap.yaml`에 FILTER를 추가하여 `memory-load` 앱의 DEBUG 레벨 로그는 CloudWatch로 전송하지 않도록 설정하세요. (힌트: `grep` 플러그인의 `Exclude` 옵션 사용)

3. **IRSA와 인스턴스 프로파일 비교**: EKS 노드에 CloudWatch 권한을 부여하는 방법으로 (a) EC2 인스턴스 프로파일과 (b) IRSA 두 가지가 있습니다. IRSA 방식이 보안 측면에서 왜 더 권장되는지 최소 권한 원칙(Least Privilege)의 관점에서 서술하세요.

4. **로그 보존 정책**: 현재 `log_retention_days: 30`으로 설정되어 있습니다. 규정 준수(compliance) 요건으로 특정 서비스의 감사 로그(audit log)는 1년 이상 보존해야 한다면 Fluent Bit 설정을 어떻게 변경해야 하는지 서술하세요. (힌트: 앱별 로그 그룹 분리 + 그룹별 다른 retention 설정)

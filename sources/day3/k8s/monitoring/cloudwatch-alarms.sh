#!/usr/bin/env bash
# CloudWatch Alarms 생성 스크립트
# Day 2 EKS 애플리케이션 (demo 네임스페이스) 대상
#
# 사용법:
#   chmod +x cloudwatch-alarms.sh
#   SNS_ARN="arn:aws:sns:ap-northeast-2:<ACCOUNT_ID>:eks-demo-alerts" \
#     ./cloudwatch-alarms.sh
#
# 사전 조건:
#   - Container Insights add-on이 설치되어 메트릭이 수집 중이어야 합니다.
#   - SNS Topic이 생성되어 있어야 합니다 (03_alerting.md Step 1 참고).

set -euo pipefail

REGION="ap-northeast-2"
CLUSTER="eks-demo-cluster"
NAMESPACE="demo"
SNS_ARN="${SNS_ARN:-}"  # 환경변수로 주입

if [[ -z "${SNS_ARN}" ]]; then
  echo "ERROR: SNS_ARN 환경변수를 설정하세요."
  echo "  export SNS_ARN=arn:aws:sns:${REGION}:<ACCOUNT_ID>:eks-demo-alerts"
  exit 1
fi

echo "=== CloudWatch Alarms 생성 시작 ==="
echo "  Cluster:   ${CLUSTER}"
echo "  Namespace: ${NAMESPACE}"
echo "  SNS ARN:   ${SNS_ARN}"
echo ""

# ── 1. Pod CPU 사용률 ─────────────────────────────────────────────────────────
# cpu-load 앱: limits의 80% 초과 시 경고

echo "[1/8] cpu-load Pod CPU 사용률 경고 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-demo-cpu-load-HighCPU" \
  --alarm-description "cpu-load Pod CPU 사용률이 limits의 80%를 초과했습니다. HPA Scale-Out 또는 limits 상향을 검토하세요." \
  --namespace ContainerInsights \
  --metric-name pod_cpu_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
    "Name=Namespace,Value=${NAMESPACE}" \
    "Name=Service,Value=cpu-load" \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 2. Pod 메모리 사용률 경고 ─────────────────────────────────────────────────
# memory-load 앱: limits의 80% 초과 시 경고 (OOMKilled 사전 감지)

echo "[2/8] memory-load Pod 메모리 경고 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-demo-memory-load-HighMemory-Warning" \
  --alarm-description "memory-load Pod 메모리 사용률이 limits의 80%를 초과했습니다. OOMKilled 위험이 있습니다." \
  --namespace ContainerInsights \
  --metric-name pod_memory_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
    "Name=Namespace,Value=${NAMESPACE}" \
    "Name=Service,Value=memory-load" \
  --statistic Average \
  --period 60 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 3. Pod 메모리 사용률 위험 ─────────────────────────────────────────────────
# memory-load 앱: limits의 95% 초과 시 위험 (OOMKilled 임박)

echo "[3/8] memory-load Pod 메모리 위험 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-demo-memory-load-HighMemory-Critical" \
  --alarm-description "memory-load Pod 메모리 사용률이 limits의 95%를 초과했습니다. 즉시 조치가 필요합니다." \
  --namespace ContainerInsights \
  --metric-name pod_memory_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
    "Name=Namespace,Value=${NAMESPACE}" \
    "Name=Service,Value=memory-load" \
  --statistic Average \
  --period 60 \
  --threshold 95 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 4. 컨테이너 재시작 횟수 ──────────────────────────────────────────────────
# demo 네임스페이스 전체: 5분 동안 재시작 3회 초과

echo "[4/8] demo 네임스페이스 컨테이너 재시작 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-demo-ContainerRestarts" \
  --alarm-description "demo 네임스페이스에서 컨테이너 재시작이 빈번합니다. CrashLoopBackOff 또는 OOMKilled 여부를 확인하세요." \
  --namespace ContainerInsights \
  --metric-name pod_number_of_container_restarts \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
    "Name=Namespace,Value=${NAMESPACE}" \
  --statistic Sum \
  --period 300 \
  --threshold 3 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}"

# ── 5. 노드 CPU 사용률 ────────────────────────────────────────────────────────

echo "[5/8] 노드 CPU 사용률 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-Node-HighCPU" \
  --alarm-description "클러스터 노드 CPU 사용률이 80%를 초과했습니다. 노드 추가(Cluster Autoscaler)를 검토하세요." \
  --namespace ContainerInsights \
  --metric-name node_cpu_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 6. 노드 메모리 사용률 ─────────────────────────────────────────────────────

echo "[6/8] 노드 메모리 사용률 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-Node-HighMemory" \
  --alarm-description "클러스터 노드 메모리 사용률이 85%를 초과했습니다." \
  --namespace ContainerInsights \
  --metric-name node_memory_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 7. 노드 파일시스템 사용률 ─────────────────────────────────────────────────

echo "[7/8] 노드 파일시스템 사용률 알람..."
aws cloudwatch put-metric-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-Node-HighDisk" \
  --alarm-description "클러스터 노드 디스크 사용률이 80%를 초과했습니다. 로그 정리 또는 디스크 확장이 필요합니다." \
  --namespace ContainerInsights \
  --metric-name node_filesystem_utilization \
  --dimensions \
    "Name=ClusterName,Value=${CLUSTER}" \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

# ── 8. Composite Alarm: 데모 클러스터 전체 상태 ───────────────────────────────
# 위의 알람 중 하나라도 ALARM 상태이면 발동하는 복합 알람

echo "[8/8] Composite Alarm (데모 클러스터 종합 상태)..."
aws cloudwatch put-composite-alarm \
  --region "${REGION}" \
  --alarm-name "EKS-${CLUSTER}-demo-Overall-Health" \
  --alarm-description "demo 클러스터 전체 상태 알람 — 하위 알람 중 하나라도 ALARM이면 발동합니다." \
  --alarm-rule "ALARM(\"EKS-${CLUSTER}-demo-memory-load-HighMemory-Critical\") OR ALARM(\"EKS-${CLUSTER}-demo-ContainerRestarts\") OR ALARM(\"EKS-${CLUSTER}-Node-HighMemory\")" \
  --alarm-actions "${SNS_ARN}" \
  --ok-actions "${SNS_ARN}"

echo ""
echo "=== 알람 생성 완료 ==="
echo ""
echo "생성된 알람 목록:"
aws cloudwatch describe-alarms \
  --region "${REGION}" \
  --alarm-name-prefix "EKS-${CLUSTER}" \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}' \
  --output table

echo ""
echo "복합 알람:"
aws cloudwatch describe-alarms \
  --region "${REGION}" \
  --alarm-name-prefix "EKS-${CLUSTER}" \
  --alarm-types CompositeAlarm \
  --query 'CompositeAlarms[*].{Name:AlarmName,State:StateValue}' \
  --output table

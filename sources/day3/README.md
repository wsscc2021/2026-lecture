# Day 3 실습 과제: Observability — EKS 클러스터 관찰가능성 구축

## 개요

Day 2에서 배포한 5개 애플리케이션(`basic`, `mysql`, `cpu-load`, `memory-load`, `slow-response`)을 대상으로
Metrics · Logs 수집 파이프라인을 구축하고, 대시보드와 알람을 설정합니다.

## 디렉터리 구조

```
sources/day3/
├── README.md                           # 이 파일 (과제 설명)
├── k8s/
│   ├── monitoring/                     # AWS CloudWatch Container Insights + Alarms
│   │   ├── container-insights-irsa.yaml  # IRSA 및 add-on 설치 가이드
│   │   └── cloudwatch-alarms.sh          # CloudWatch Alarms 생성 스크립트
│   └── logging/                        # Fluent Bit → AWS CloudWatch Logs
│       ├── namespace.yaml
│       ├── cloudwatch-irsa.yaml        # IRSA(IAM Role) 설정 가이드
│       ├── fluentbit-configmap.yaml
│       └── fluentbit-daemonset.yaml
└── exercises/
    ├── 01_metrics.md                   # 실습 1: Container Insights + CloudWatch 대시보드
    ├── 02_logging.md                   # 실습 2: Fluent Bit → CloudWatch Logs 검색
    └── 03_alerting.md                  # 실습 3: CloudWatch Alarms + SNS 장애 대응
```

## AWS 서비스 구성 요약

| 역할 | AWS 서비스 | 설치 방식 |
|------|-----------|---------|
| 메트릭 수집 | CloudWatch Container Insights (Agent DaemonSet) | EKS Add-on |
| 메트릭 저장·조회 | CloudWatch Metrics (`ContainerInsights` 네임스페이스) | 자동 |
| 대시보드 | CloudWatch Dashboard | 콘솔/CLI |
| 알람 | CloudWatch Alarms + Composite Alarm | AWS CLI (`cloudwatch-alarms.sh`) |
| 알림 | SNS (이메일) | AWS CLI |
| 로그 수집 | Fluent Bit (DaemonSet) | `kubectl apply` |
| 로그 저장·검색 | CloudWatch Logs + Logs Insights | 자동 |

## 사전 조건

- Day 2 애플리케이션이 `demo` 네임스페이스에 정상 배포되어 있어야 합니다.
- EKS 클러스터에 대한 `kubectl` 접근 권한이 있어야 합니다.
- AWS CLI가 설치되고 EKS 클러스터 계정에 대한 인증이 되어 있어야 합니다.
- `eksctl`이 설치되어 있어야 합니다 (IRSA 생성에 사용).

## 실습 순서

1. [실습 1: 메트릭 수집 및 대시보드](exercises/01_metrics.md)
2. [실습 2: 로그 수집 및 검색](exercises/02_logging.md)
3. [실습 3: 알람 설정 및 장애 대응](exercises/03_alerting.md)

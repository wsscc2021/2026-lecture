# Elastic Kubernetes Service (EKS)

EKS는 AWS가 Kubernetes **Control Plane을 완전 관리**해주는 서비스다. etcd, API Server, Controller Manager, Scheduler의 설치·패치·고가용성(Multi-AZ)을 AWS가 담당하며, 사용자는 워커 노드와 워크로드 배포에만 집중할 수 있다.

```
┌─────────────────────────────────────────────────────┐
│               AWS 관리 영역                          │
│  ┌──────────────────────────────────────────────┐   │
│  │            Control Plane (Multi-AZ)          │   │
│  │  API Server │ etcd │ Scheduler │ Controller  │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
             │  kubectl / AWS API
┌─────────────────────────────────────────────────────┐
│               사용자 관리 영역                       │
│  Worker Node 1    Worker Node 2    Worker Node 3    │
│  (EC2 / Fargate)  (EC2 / Fargate)  (EC2 / Fargate) │
└─────────────────────────────────────────────────────┘
```

---

## Control Plane

Kubernetes 클러스터를 제어하는 핵심 컴포넌트 집합. EKS에서는 AWS가 완전 관리한다.

| 컴포넌트 | 역할 |
|----------|------|
| **API Server** | 모든 K8s 요청의 진입점. `kubectl`, 컨트롤러, 노드가 이 API로 통신 |
| **etcd** | 클러스터 상태(Pod, Service, ConfigMap 등)를 저장하는 분산 KV 저장소 |
| **Scheduler** | 새 Pod를 어느 노드에 배치할지 결정 (리소스, 어피니티, 테인트 등 고려) |
| **Controller Manager** | Deployment, ReplicaSet, Node 등의 상태를 desired state로 유지 |

```bash
# EKS 클러스터 생성 (eksctl 사용)
eksctl create cluster \
  --name my-cluster \
  --region ap-northeast-2 \
  --version 1.31 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 2

# kubeconfig 업데이트
aws eks update-kubeconfig --name my-cluster --region ap-northeast-2

# Control Plane 버전 확인
kubectl version
```

---

## Managed Node Group

AWS가 EC2 인스턴스의 **프로비저닝·업그레이드·스케일링·종료**를 자동 관리하는 워커 노드 그룹. 내부적으로 Auto Scaling Group(ASG)으로 구현된다.

```
EKS Cluster
  └── Managed Node Group "workers"
        └── Auto Scaling Group
              ├── EC2 i-001 (t3.medium)  ← kubelet, kube-proxy 자동 설치
              ├── EC2 i-002 (t3.medium)
              └── EC2 i-003 (t3.medium)  ← 노드 수 조정 시 자동 추가/제거
```

| 구분 | Managed Node Group | Self-managed Node | Fargate |
|------|-------------------|-------------------|---------|
| 노드 관리 | AWS 자동 | 직접 관리 | AWS (서버리스) |
| AMI 업데이트 | 자동 (롤링) | 직접 | 자동 |
| 인스턴스 접근 | SSH 가능 | SSH 가능 | 불가 |
| 비용 모델 | EC2 On-Demand/Spot | EC2 | Pod 단위 |
| GPU/커스텀 AMI | 지원 | 지원 | 미지원 |

```bash
# 노드 그룹 목록
eksctl get nodegroup --cluster my-cluster

# 노드 그룹 스케일 조정
eksctl scale nodegroup --cluster my-cluster --name workers --nodes 4

# 노드 목록 확인
kubectl get nodes -o wide
```

---

## Kubernetes Default Resources

### Namespace

클러스터를 논리적으로 분리하는 격리 단위. 팀·환경(dev/staging/prod)별로 리소스를 구분한다.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
```

```bash
kubectl get namespaces
kubectl create namespace staging
kubectl config set-context --current --namespace=staging
```

### Deployment

Pod를 선언적으로 관리하는 리소스. **ReplicaSet**을 통해 지정한 수의 Pod를 항상 유지하고, 롤링 업데이트·롤백을 처리한다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1   # 업데이트 중 최대 중단 Pod 수
      maxSurge: 1         # 추가로 생성 가능한 Pod 수
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
      - name: app
        image: my-app:1.2.0
        ports:
        - containerPort: 5000
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
```

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/web-app
kubectl rollout history deployment/web-app
kubectl rollout undo deployment/web-app        # 이전 버전으로 롤백
kubectl set image deployment/web-app app=my-app:1.3.0
```

### DaemonSet

**모든 노드(또는 특정 노드)에 Pod를 하나씩** 배포하는 리소스. 노드가 추가되면 자동으로 해당 노드에 Pod가 생성된다. 로그 수집 에이전트, 모니터링 에이전트, 네트워크 플러그인 등에 사용.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
spec:
  selector:
    matchLabels:
      app: log-collector
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      containers:
      - name: fluentd
        image: fluentd:latest
        volumeMounts:
        - name: varlog
          mountPath: /var/log
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
```

```bash
kubectl get daemonset -A     # 모든 네임스페이스
# kube-system에 aws-node, kube-proxy DaemonSet 기본 존재
```

### Service

Pod에 안정적인 **네트워크 엔드포인트**를 제공한다. Pod는 재시작 시 IP가 바뀌지만 Service IP(ClusterIP)는 고정.

| 타입 | 용도 |
|------|------|
| **ClusterIP** | 클러스터 내부 통신 전용 (기본값) |
| **NodePort** | 각 노드의 포트를 통해 외부 노출 (30000-32767) |
| **LoadBalancer** | 클라우드 LB 생성 (EKS → AWS NLB/CLB) |

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-app-svc
spec:
  type: ClusterIP
  selector:
    app: web-app          # 이 라벨을 가진 Pod로 트래픽 전달
  ports:
  - port: 80              # Service 포트
    targetPort: 5000      # Pod 포트
```

```bash
kubectl get service
kubectl describe service web-app-svc
# DNS: <service>.<namespace>.svc.cluster.local
```

---

## Pod QoS Class

K8s는 Pod의 `resources.requests`와 `limits` 설정에 따라 **QoS(Quality of Service) 등급**을 자동 부여한다. 노드 메모리가 부족할 때 OOM Killer가 낮은 등급의 Pod부터 종료한다.

| QoS Class | 조건 | 우선순위 |
|-----------|------|----------|
| **Guaranteed** | 모든 컨테이너에 `requests == limits` (CPU·메모리 모두) | 가장 높음 (마지막에 종료) |
| **Burstable** | 하나 이상의 컨테이너에 `requests < limits` | 중간 |
| **BestEffort** | `requests`와 `limits` 모두 미설정 | 가장 낮음 (먼저 종료) |

```yaml
# Guaranteed
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "500m"       # requests == limits
    memory: "256Mi"

# Burstable
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"       # limits > requests
    memory: "256Mi"

# BestEffort
# resources 블록 없음
```

```bash
# Pod의 QoS Class 확인
kubectl get pod <pod-name> -o jsonpath='{.status.qosClass}'
```

> 운영 환경에서는 모든 Pod에 **Guaranteed** 또는 **Burstable**을 설정한다. BestEffort Pod는 시스템 부하 시 예고 없이 종료된다.

---

## AWS ALB Ingress

**Ingress**는 클러스터 외부 HTTP/HTTPS 트래픽을 내부 Service로 라우팅하는 K8s 리소스다. EKS에서는 **AWS Load Balancer Controller**가 Ingress 오브젝트를 감지해 자동으로 ALB(Application Load Balancer)를 생성·관리한다.

```
인터넷
  │
  ▼
AWS ALB  (AWS Load Balancer Controller가 자동 생성)
  │
  ├─ /api/*    → api-service:80
  ├─ /auth/*   → auth-service:80
  └─ /*        → frontend-service:80
```

### AWS Load Balancer Controller 설치

```bash
# IAM OIDC Provider 생성
eksctl utils associate-iam-oidc-provider \
  --cluster my-cluster --approve

# IAM Policy 생성 (ALB 생성 권한)
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json

# Service Account 생성
eksctl create iamserviceaccount \
  --cluster my-cluster \
  --namespace kube-system \
  --name aws-load-balancer-controller \
  --attach-policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/AWSLoadBalancerControllerIAMPolicy \
  --approve

# Helm으로 컨트롤러 설치
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=my-cluster \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

### Ingress 리소스 예시

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing    # 외부 공개
    alb.ingress.kubernetes.io/target-type: ip            # Pod IP 직접 연결
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
      - path: /orders
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80
```

```bash
kubectl apply -f ingress.yaml
kubectl get ingress          # ADDRESS 열에 ALB DNS 이름 표시
kubectl describe ingress app-ingress
```

---

## Managed Tools — k9s

**k9s**는 Kubernetes 클러스터를 터미널에서 실시간으로 조회하고 조작할 수 있는 TUI(Text User Interface) 도구다.

```bash
# 설치 (Linux)
curl -sS https://webinstall.dev/k9s | bash
# 또는
brew install k9s

# 실행
k9s
k9s --namespace production
k9s --context my-cluster
```

### 주요 단축키

| 키 | 동작 |
|----|------|
| `:pod` | Pod 목록으로 이동 |
| `:deploy` | Deployment 목록 |
| `:svc` | Service 목록 |
| `:ns` | Namespace 목록 |
| `l` | 선택한 Pod 로그 보기 |
| `s` | 선택한 Pod에 셸 접속 (`exec -it`) |
| `d` | 리소스 상세 (`describe`) |
| `ctrl+d` | 리소스 삭제 |
| `/` | 필터 검색 |
| `esc` | 이전 화면으로 |

---

## Pod Scaling

### HPA (Horizontal Pod Autoscaler)

CPU·메모리 사용률 또는 커스텀 메트릭을 기반으로 **Pod 수를 자동 조절**한다.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60   # CPU 60% 초과 시 스케일 아웃
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
```

```bash
kubectl apply -f hpa.yaml
kubectl get hpa               # REPLICAS, TARGETS 확인
kubectl describe hpa web-app-hpa

# Metrics Server 필요 (HPA가 메트릭을 읽기 위해)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl top pod               # Pod별 CPU/메모리 사용량
```

### VPA (Vertical Pod Autoscaler)

Pod의 `requests`와 `limits`를 **자동으로 추천하거나 적용**한다. HPA와 달리 Pod 수 대신 Pod 크기를 조정.

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: web-app-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  updatePolicy:
    updateMode: "Off"   # Off: 추천만 표시 / Auto: 자동 적용 (Pod 재시작 발생)
```

```bash
kubectl get vpa
kubectl describe vpa web-app-vpa
# RECOMMENDATION 섹션에서 Lower Bound / Target / Upper Bound 확인
```

| | HPA | VPA |
|-|-----|-----|
| 조정 대상 | Pod 수 | Pod 리소스(CPU/메모리) |
| 스케일 방향 | 수평 (Out/In) | 수직 (Up/Down) |
| 적용 시 재시작 | 없음 | 있음 (Auto 모드) |
| 함께 사용 | CPU 기준 시 상호 충돌 주의 | 메모리 기준 HPA와 병행 가능 |

---

## Node Scaling

### Cluster Autoscaler

Pod가 `Pending` 상태로 대기하거나 노드 활용률이 낮을 때 **노드 수를 자동 증감**한다. EKS의 Managed Node Group(ASG)과 연동한다.

```bash
# Cluster Autoscaler 설치 (Helm)
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm install cluster-autoscaler autoscaler/cluster-autoscaler \
  --set autoDiscovery.clusterName=my-cluster \
  --set awsRegion=ap-northeast-2

# 스케일 아웃 트리거 확인
kubectl get events | grep ScaleUp
kubectl logs -n kube-system deployment/cluster-autoscaler
```

스케일 아웃 흐름:
```
Pod 생성 요청
    → Scheduler: 배치할 노드 없음 → Pod Pending
    → Cluster Autoscaler 감지
    → ASG DesiredCapacity +1
    → EC2 인스턴스 기동 (~2분)
    → kubelet 등록 → Pod 배치
```

### Karpenter

AWS가 개발한 차세대 노드 자동 프로비저너. Cluster Autoscaler보다 **더 빠르고 유연하게** 노드를 프로비저닝한다.

| | Cluster Autoscaler | Karpenter |
|-|--------------------|-----------|
| 프로비저닝 단위 | Node Group (ASG) | 개별 EC2 직접 생성 |
| 인스턴스 타입 유연성 | Node Group별 고정 | Pod 요건에 맞게 동적 선택 |
| 속도 | ~2분 | ~30초 |
| Spot 통합 | 수동 설정 | 자동 Spot/On-Demand 혼용 |

```yaml
# NodePool: Karpenter가 프로비저닝할 노드 조건 정의
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
      - key: karpenter.k8s.aws/instance-category
        operator: In
        values: ["c", "m", "r"]
      - key: karpenter.sh/capacity-type
        operator: In
        values: ["spot", "on-demand"]
  limits:
    cpu: "100"
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
```

---

## Probe — 헬스체크

K8s는 세 가지 Probe로 컨테이너 상태를 주기적으로 확인하고, 비정상 컨테이너를 자동으로 재시작하거나 트래픽에서 제외한다.

| Probe | 목적 | 실패 시 동작 |
|-------|------|-------------|
| **Liveness** | 컨테이너가 살아 있는가? (데드락·무한루프 감지) | 컨테이너 재시작 |
| **Readiness** | 트래픽을 받을 준비가 됐는가? (DB 연결 완료 등) | Service 엔드포인트에서 제외 (재시작 없음) |
| **Startup** | 느리게 시작하는 앱의 초기 기동 보호 | 실패하면 컨테이너 재시작 (완료 전까지 Liveness·Readiness 비활성) |

### 점검 방식

```yaml
# HTTP GET — 2xx/3xx 응답이면 성공
livenessProbe:
  httpGet:
    path: /health
    port: 5000

# TCP Socket — 포트가 열려 있으면 성공
readinessProbe:
  tcpSocket:
    port: 5432

# Exec — exit 0이면 성공
livenessProbe:
  exec:
    command: ["pg_isready", "-U", "postgres"]
```

### 전체 예시

```yaml
containers:
- name: app
  image: my-app:1.0.0
  ports:
  - containerPort: 5000

  # Startup: 최대 5 * 30 = 150초 기동 허용
  startupProbe:
    httpGet:
      path: /health
      port: 5000
    failureThreshold: 30
    periodSeconds: 5

  # Liveness: 10초마다 확인, 3회 연속 실패 시 재시작
  livenessProbe:
    httpGet:
      path: /health
      port: 5000
    initialDelaySeconds: 0
    periodSeconds: 10
    failureThreshold: 3
    timeoutSeconds: 2

  # Readiness: 5초마다 확인, 실패 시 트래픽 차단
  readinessProbe:
    httpGet:
      path: /health
      port: 5000
    initialDelaySeconds: 0
    periodSeconds: 5
    failureThreshold: 3
    successThreshold: 1
```

### Probe 동작 흐름

```
Pod 시작
    │
    ├─ startupProbe 실행 (성공할 때까지 반복)
    │       ↓ 성공
    ├─ livenessProbe + readinessProbe 병행 시작
    │
    │  readinessProbe 성공 → Service 엔드포인트 등록 (트래픽 수신 시작)
    │  readinessProbe 실패 → 엔드포인트에서 제외 (트래픽 차단, 재시작 없음)
    │
    │  livenessProbe 3회 연속 실패
    │       ↓
    └─ 컨테이너 재시작 (Pod는 유지, 컨테이너만 재시작)
```

```bash
# Probe 실패 이벤트 확인
kubectl describe pod <pod-name> | grep -A5 "Liveness\|Readiness\|Startup"
kubectl get events --field-selector reason=Unhealthy
```

> **05_slow_response 앱 실습 연계**: 기본 응답이 40초인 앱에 Readiness Probe(`/health`)를 설정하면 `/`는 느리지만 Service 엔드포인트 등록은 `/health`의 즉시 응답으로 정상 처리되는 것을 확인할 수 있다.

---

## Graceful Shutdown — 무중단 종료

### Pod 종료 흐름

`kubectl delete pod` 또는 롤링 업데이트·스케일 인 시 K8s는 Pod를 즉시 강제 종료하지 않고 아래 순서로 진행한다.

```
kubectl delete pod web-app-xxx
         │
         ▼
1. Pod 상태 → Terminating
   동시에 두 가지 병렬 진행:
     A. kubelet: preStop hook 실행 → SIGTERM 전송
     B. kube-proxy / Endpoints 컨트롤러: Service 엔드포인트에서 Pod IP 제거
         (ALB/NLB 등록 해제도 여기서 시작 — 수 초 소요)
         │
         ▼
2. 앱이 SIGTERM 수신 → 처리 중인 요청 완료 후 종료
         │
         ▼
3. terminationGracePeriodSeconds 초과 시
   → kubelet이 SIGKILL 전송 → 강제 종료
```

### Race Condition 문제

엔드포인트 제거(B)와 SIGTERM(A)이 **동시**에 진행되기 때문에, 엔드포인트가 완전히 제거되기 전에 이미 앱이 종료되면 일부 요청이 `Connection Refused`를 받을 수 있다.

```
타임라인:
  t=0  SIGTERM 수신 → 앱 즉시 종료
  t=1  kube-proxy가 iptables 규칙 제거 완료
       (t=0 ~ t=1 사이에 들어온 요청은 이미 닫힌 소켓에 도달 → 502/503)
```

**해결 방법: `preStop` sleep**

```yaml
lifecycle:
  preStop:
    exec:
      command: ["sleep", "5"]   # 엔드포인트 제거가 전파될 시간을 확보
```

`preStop`이 완료된 뒤 SIGTERM이 전송되므로, 5초 동안 새 요청 유입이 차단된 후 앱이 종료 신호를 받는다.

### terminationGracePeriodSeconds

SIGTERM 전송 후 SIGKILL까지 기다리는 최대 시간 (기본: **30초**).

```yaml
spec:
  terminationGracePeriodSeconds: 60   # 처리 시간이 긴 앱은 늘려야 함
  containers:
  - name: app
    lifecycle:
      preStop:
        exec:
          command: ["sleep", "5"]
```

> `preStop` 실행 시간도 `terminationGracePeriodSeconds`에 포함된다.  
> 예: `terminationGracePeriodSeconds: 60`, `preStop sleep 5` → 앱이 SIGTERM을 받고 처리할 수 있는 시간은 최대 55초.

### 애플리케이션 SIGTERM 처리 (Python/Flask)

Flask 개발 서버는 SIGTERM을 처리하지 못하므로 운영 환경에서는 **gunicorn** 을 사용한다. gunicorn은 SIGTERM 수신 시 현재 요청을 완료한 뒤 종료한다(`--graceful-timeout` 옵션으로 대기 시간 설정).

### 전체 권장 설정 예시

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - name: app
    image: my-app:1.0.0
    lifecycle:
      preStop:
        exec:
          command: ["sleep", "5"]      # 엔드포인트 제거 전파 대기
    readinessProbe:
      httpGet:
        path: /health
        port: 5000
      periodSeconds: 5
      failureThreshold: 1              # SIGTERM 후 /health 503 반환 시 즉시 트래픽 차단
    livenessProbe:
      httpGet:
        path: /health
        port: 5000
      periodSeconds: 10
      failureThreshold: 3
```

### Graceful Shutdown 전체 흐름 (권장 설정 기준)

```
t= 0  Pod Terminating
       → preStop sleep 5 시작
       → 엔드포인트 제거 전파 시작 (kube-proxy, ALB 대상 그룹)

t= 5  preStop 완료 → SIGTERM 앱에 전달
       → 앱: /health → 503 반환 시작 (Readiness 실패 → 남은 트래픽 차단)
       → 앱: 처리 중인 요청 완료 대기

t=35  모든 요청 처리 완료 → 앱 정상 종료 (exit 0)

t=60  (만약 앱이 살아 있다면) SIGKILL → 강제 종료
```

```bash
# 종료 과정 실시간 확인
kubectl get pod -w                              # STATUS: Terminating 관찰
kubectl logs <pod> --previous                  # 재시작된 컨테이너의 이전 로그
kubectl describe pod <pod> | grep -A3 "State"  # Last State: exit code 확인
# exit 0: 정상 종료 / exit 137: SIGKILL(강제 종료)
```

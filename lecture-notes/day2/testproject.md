# Day 2 실습 과제: Kubernetes 애플리케이션 배포 및 운영

## 개요

Day 2에서 학습한 Docker 이미지 빌드, Kubernetes 리소스 배포, HPA(Horizontal Pod Autoscaler), 헬스 프로브, Secret/ConfigMap 관리 내용을 바탕으로 아래 과제를 수행합니다.

---

## 과제 1: 기본 애플리케이션 배포 및 헬스 프로브 검증

### 배경

`basic-app`은 hostname, timestamp, 환경변수, 요청 헤더를 반환하는 단순한 Flask 애플리케이션입니다.
Kubernetes에 배포하고 Liveness/Readiness Probe가 정상 동작하는지 확인합니다.

### 요구 사항

1. **Dockerfile 작성**: `sources/day2/apps/01_basic/` 디렉터리의 소스를 기반으로, 아래 조건을 만족하는 Dockerfile을 작성하세요.
   - 베이스 이미지: `python:3.12-slim`
   - 비루트(non-root) 사용자(`appuser`)로 실행
   - `gunicorn` 4 workers로 기동

2. **Deployment 작성**: 아래 조건을 만족하는 `Deployment` 매니페스트를 작성하세요.
   - 네임스페이스: `demo`
   - `replicas: 2`
   - 리소스 요청/제한: CPU `100m/200m`, 메모리 `64Mi/128Mi`
   - `readinessProbe`: `/health` 경로, 포트 5000, `initialDelaySeconds: 5`, `periodSeconds: 5`
   - `livenessProbe`: `/health` 경로, 포트 5000, `initialDelaySeconds: 10`, `periodSeconds: 10`

3. **동작 확인**:
   ```bash
   # Pod 상태 확인
   kubectl get pods -n demo

   # 헬스체크 엔드포인트 호출
   curl http://<INGRESS_HOST>/basic
   curl http://<INGRESS_HOST>/basic/env
   curl http://<INGRESS_HOST>/basic/headers
   ```

4. **관찰 포인트**: `kubectl describe pod <pod-name> -n demo` 출력에서 `Readiness` / `Liveness` 항목을 확인하고, Probe 실패 시 어떤 이벤트가 발생하는지 기록하세요.

### 제출 항목

- 완성된 `Dockerfile`
- 완성된 `Deployment` YAML
- `kubectl get pods -n demo` 실행 결과 스크린샷 또는 출력 텍스트
- 헬스 프로브 동작 확인 내용(정상/비정상 케이스 각 1개)

---

## 과제 2: MySQL 연동 애플리케이션 — Secret·ConfigMap 활용

### 배경

`mysql-app`은 MySQL 데이터베이스와 연동하여 CRUD 기능을 제공하는 Flask REST API입니다.
민감 정보(비밀번호)는 `Secret`으로, 초기화 SQL은 `ConfigMap`으로 관리합니다.

### 요구 사항

1. **Secret 작성**: 아래 값을 담은 `Secret`을 작성하세요.
   - 이름: `mysql-secret`, 네임스페이스: `demo`
   - `MYSQL_ROOT_PASSWORD`: `demo`
   - `MYSQL_DATABASE`: `demo`

2. **ConfigMap 작성**: `init.sql` 내용을 담은 `ConfigMap`을 작성하세요.
   - 이름: `mysql-initdb`, 네임스페이스: `demo`
   - `/docker-entrypoint-initdb.d`에 마운트되어 컨테이너 초기화 시 실행

3. **MySQL Deployment 작성**: 아래 조건을 만족하는 Deployment를 작성하세요.
   - 이미지: `mysql:8.0`
   - `envFrom`으로 `mysql-secret` 참조
   - `readinessProbe`: `mysqladmin ping` exec 명령, `initialDelaySeconds: 20`, `periodSeconds: 10`, `failureThreshold: 6`
   - 데이터 볼륨: `emptyDir` (데모용)

4. **API 동작 확인**:
   ```bash
   # 사용자 목록 조회
   curl http://<INGRESS_HOST>/mysql/users

   # 사용자 생성
   curl -X POST http://<INGRESS_HOST>/mysql/users \
     -H "Content-Type: application/json" \
     -d '{"name": "홍길동", "email": "hong@example.com"}'

   # 사용자 수정
   curl -X PUT http://<INGRESS_HOST>/mysql/users/1 \
     -H "Content-Type: application/json" \
     -d '{"name": "홍길동 수정", "email": "hong2@example.com"}'

   # 사용자 삭제
   curl -X DELETE http://<INGRESS_HOST>/mysql/users/1

   # DB 연결 상태 확인
   curl http://<INGRESS_HOST>/health
   ```

5. **심화 문제**: MySQL Pod를 삭제(`kubectl delete pod <mysql-pod> -n demo`)한 뒤 재기동 시 데이터가 어떻게 되는지 확인하고, 이를 영속적으로 유지하려면 어떤 K8s 리소스를 사용해야 하는지 서술하세요.

### 제출 항목

- 완성된 `Secret`, `ConfigMap`, `Deployment` YAML
- CRUD 동작 확인 결과(curl 명령어 및 응답 JSON)
- 심화 문제 답변(150자 이상)

---

## 과제 3: CPU 부하 애플리케이션 및 HPA 동작 관찰

### 배경

`cpu-load` 애플리케이션은 요청을 통해 CPU 집중 연산을 시작/중지할 수 있습니다.
HPA가 CPU 사용률에 따라 Pod를 자동으로 Scale-Out/In 하는 과정을 관찰합니다.

### 요구 사항

1. **HPA 작성**: 아래 조건을 만족하는 `HorizontalPodAutoscaler`를 작성하세요.
   - 대상: `cpu-load` Deployment
   - `minReplicas: 1`, `maxReplicas: 5`
   - CPU 평균 사용률 50% 초과 시 Scale-Out

2. **부하 발생 및 관찰**:
   ```bash
   # CPU 부하 시작 (30초, 2 workers)
   curl -X POST http://<INGRESS_HOST>/cpu/load \
     -H "Content-Type: application/json" \
     -d '{"duration": 30, "workers": 2}'

   # HPA 상태 실시간 관찰
   kubectl get hpa -n demo -w

   # Pod 수 변화 관찰
   kubectl get pods -n demo -w

   # 부하 중지
   curl -X POST http://<INGRESS_HOST>/cpu/stop
   ```

3. **관찰 포인트**:
   - 부하 발생 후 HPA가 Scale-Out을 시작하기까지 걸린 시간을 기록하세요.
   - 부하 중지 후 Scale-In이 완료되기까지 걸린 시간을 기록하세요.
   - `kubectl describe hpa cpu-load -n demo`의 Events 섹션을 캡처하세요.

4. **심화 문제**: HPA가 Scale-Out을 결정하는 알고리즘을 설명하고, `averageUtilization` 값을 50에서 30으로 낮추면 어떤 효과가 발생하는지 예상하여 서술하세요.

### 제출 항목

- 완성된 `HPA` YAML
- `kubectl get hpa -n demo` 출력 결과 (부하 전/중/후 각 1회)
- Scale-Out 및 Scale-In 소요 시간 측정 결과
- 심화 문제 답변(200자 이상)

---

## 과제 4: 메모리 부하 및 OOMKilled 시나리오 분석

### 배경

`memory-load` 애플리케이션은 메모리를 동적으로 할당하고, 누수(leak)를 시뮬레이션합니다.
컨테이너의 메모리 제한을 초과했을 때 발생하는 OOMKilled 이벤트를 실습합니다.

### 요구 사항

1. **메모리 할당 실습**:
   ```bash
   # 현재 메모리 상태 조회
   curl http://<INGRESS_HOST>/memory

   # 256MB 할당
   curl -X POST http://<INGRESS_HOST>/memory/allocate \
     -H "Content-Type: application/json" \
     -d '{"mb": 256}'

   # 메모리 해제
   curl -X POST http://<INGRESS_HOST>/memory/release
   ```

2. **메모리 누수 시뮬레이션**:
   ```bash
   # 50MB씩 1초 간격으로 계속 할당 (누수 시뮬레이션)
   curl -X POST http://<INGRESS_HOST>/memory/leak \
     -H "Content-Type: application/json" \
     -d '{"mb": 50, "interval": 1}'

   # 메모리 사용량 모니터링 (별도 터미널)
   watch -n 2 'curl -s http://<INGRESS_HOST>/memory | python3 -m json.tool'

   # 누수 중지
   curl -X POST http://<INGRESS_HOST>/memory/leak/stop
   ```

3. **OOMKilled 유도 및 분석**: Deployment의 메모리 limit을 `128Mi`로 낮게 설정한 뒤 메모리 누수를 시뮬레이션하여 OOMKilled가 발생하는 것을 확인하세요.
   ```bash
   kubectl describe pod <pod-name> -n demo
   # "OOMKilled" 이벤트 및 "Last State" 섹션 확인
   ```

4. **심화 문제**: 메모리 limit이 `512Mi`로 설정되어 있을 때 `POST /memory/allocate {"mb": 600}`을 실행하면 어떤 결과가 예상되는지, Kubernetes가 어떻게 대응하는지 서술하세요.

### 제출 항목

- 메모리 할당/해제 동작 확인 결과(JSON 응답)
- OOMKilled 발생 시 `kubectl describe pod` 출력 관련 섹션 캡처
- 심화 문제 답변(200자 이상)

---

## 과제 5: 응답 지연 애플리케이션 — Readiness Probe 및 타임아웃 설정

### 배경

`slow-response` 애플리케이션은 기본 40초의 응답 지연을 가집니다.
Readiness Probe가 응답 지연이 있는 엔드포인트가 아닌 즉시 응답하는 `/health`로 설정된 이유를 이해하고, 클라이언트 타임아웃 설정을 실습합니다.

### 요구 사항

1. **타임아웃 동작 확인**:
   ```bash
   # 40초 응답 확인 (실제로 기다림)
   curl -w "\nTotal time: %{time_total}s\n" http://<INGRESS_HOST>/slow

   # 5초 타임아웃 설정 — 타임아웃 발생 확인
   curl --max-time 5 http://<INGRESS_HOST>/slow

   # 즉시 응답 엔드포인트 — 성공 확인
   curl --max-time 5 http://<INGRESS_HOST>/slow/fast

   # 지연 시간 직접 지정
   curl "http://<INGRESS_HOST>/slow/custom?seconds=10"
   ```

2. **Readiness Probe 설정 의도 파악**: 아래 두 가지 Probe 설정을 비교하고 각각의 결과를 서술하세요.

   | 설정 | Probe 경로 | 예상 결과 |
   |------|-----------|----------|
   | A (잘못된 설정) | `/slow` (40초 응답) | ? |
   | B (올바른 설정) | `/health` (즉시 응답) | ? |

3. **`terminationGracePeriodSeconds` 역할**: Deployment YAML에 `terminationGracePeriodSeconds: 60`이 설정된 이유를 설명하세요. 이 값이 없거나 너무 작으면 어떤 문제가 발생하는지 서술하세요.

4. **심화 문제**: 아래 Deployment 설정에서 문제점을 찾고 수정하세요.
   ```yaml
   readinessProbe:
     httpGet:
       path: /slow   # 40초 응답
       port: 5000
     initialDelaySeconds: 5
     periodSeconds: 5
     timeoutSeconds: 3
   ```
   - 어떤 문제가 발생하는가?
   - 올바른 설정은 무엇인가?

### 제출 항목

- 타임아웃 동작 확인 결과 (curl 명령어 및 결과)
- Probe 설정 비교 표 완성
- `terminationGracePeriodSeconds` 역할 설명 (150자 이상)
- 심화 문제 답변

---

## 과제 6: Ingress 라우팅 및 전체 서비스 통합 검증

### 배경

`ingress.yaml`은 AWS ALB Ingress Controller를 사용하여 경로 기반 라우팅으로 5개 서비스를 단일 엔드포인트로 노출합니다.

### 요구 사항

1. **Ingress 구성 분석**: 아래 라우팅 규칙을 표로 정리하세요.

   | 경로 (Path) | 백엔드 서비스 | 서비스 포트 |
   |------------|--------------|-----------|
   | `/basic` | | |
   | `/mysql` | | |
   | `/cpu` | | |
   | `/memory` | | |
   | `/slow` | | |

2. **전체 서비스 동작 확인**: 배포된 모든 서비스에 각각 1회씩 요청을 보내고 응답을 기록하세요.

3. **ALB 어노테이션 분석**: `ingress.yaml`의 어노테이션 2개를 설명하세요.
   - `alb.ingress.kubernetes.io/scheme: internet-facing`
   - `alb.ingress.kubernetes.io/target-type: ip`

4. **심화 문제**: 현재 Ingress 설정에서 `/health` 경로로 요청하면 어떤 서비스로 라우팅되는지, 또는 라우팅되지 않는지 예측하고 이유를 서술하세요. 각 서비스가 독립적인 `/health` 엔드포인트를 가지고 있을 때 이를 Ingress에서 노출하려면 어떻게 설정해야 하는지도 제안하세요.

### 제출 항목

- 라우팅 규칙 표 완성
- 전체 서비스 동작 확인 결과
- ALB 어노테이션 설명
- 심화 문제 답변(200자 이상)

---

## 제출 기준

| 항목 | 배점 |
|------|------|
| 과제 1: 기본 배포 및 헬스 프로브 | 15점 |
| 과제 2: MySQL 연동 및 Secret/ConfigMap | 20점 |
| 과제 3: CPU HPA 동작 관찰 | 20점 |
| 과제 4: 메모리 부하 및 OOMKilled 분석 | 15점 |
| 과제 5: 응답 지연 및 Probe 설정 | 15점 |
| 과제 6: Ingress 통합 검증 | 15점 |
| **합계** | **100점** |

## 제출 형식

- 각 과제별 YAML 파일 및 결과 캡처를 하나의 압축 파일(`학번_day2_과제.zip`)로 묶어 제출
- 심화 문제 답변은 별도 `report.md` 파일에 과제 번호별로 정리
- 제출 기한: 강의 후 1주일 이내

## 참고 명령어

```bash
# 네임스페이스 생성
kubectl create namespace demo

# 모든 리소스 확인
kubectl get all -n demo

# Pod 로그 확인
kubectl logs <pod-name> -n demo

# HPA 상태 확인
kubectl get hpa -n demo

# 이벤트 확인
kubectl get events -n demo --sort-by='.lastTimestamp'

# Pod 상세 정보
kubectl describe pod <pod-name> -n demo

# Pod 재시작 횟수 확인
kubectl get pods -n demo -o wide
```

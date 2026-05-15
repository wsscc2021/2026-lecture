# 2026년 5월 클라우드컴퓨팅 기초 교육

- 일자: 2026년 5월 18일(월) ~ 21일(목)
- 장소: 인천 글로벌숙련기술진흥원
- 대상: 전국기능경기대회 클라우드컴퓨팅 직종 참가 학생
- 강사: 삼성전자 기능올림픽 이동근

## 1일차

### 운영체제 기초

- 운영체제 CPU, Memory 등 컴퓨터 자원 관리
- 포그라운드, 백그라운드, 시스템 데몬
- SIGTERM, SIGKILL, SIGINT 시그널, Graceful Shutdown
- 프로세스와 쓰레드
- 좀비 프로세스, 고아 프로세스

### 네트워크 기초

- 라우팅 개념, 동적 라우팅, 정적 라우팅
- DNS의 기본 개념, Recursion Query와 Interactive Query, DNS Delegate, Record 타입
- TCP와 UDP, TCP의 3-way handshake, 4-way handshake, TCP의 window size
- 네트워크 툴 활용 (nc, traceroute, nslookup, dig, tcpdump, netstat)

### 데이터베이스 기초

- Primary Key, Unique Key, Foreign Key
- INDEX 설정에 따른 성능 차이
- Transaction, ACID, Isolation Level
- MVCC 개념
- RDS for MySQL과 Aurora MySQL의 차이점

## 2일차

### 모놀리식 구조와 마이크로서비스 구조

- 모놀리식 구조의 개념과 한계
- 마이크로 서비스 구조의 개념과 장점
- 모놀리식 구조와 마이크로 서비스 구조의 장단점 비교
- 마이크로 서비스에서 컨테이너 기술이 주목받는 이유

### 컨테이너 기초

- VM과 컨테이너 비교
- 컨테이너 기반 리눅스 기술 3가지 (Namespace, cgroups, UFS)
- Dockerfile best practices
- Docker image layer
- Multi-stage image build

### Elastic Kubernetes Service

- Manged Node Group
- Control Plane
- Kubernetes default resources (Deployments, DaemonSet, Namespace, Service)
- Pod QoS Class
- AWS ALB Ingress
- Managed tools (k9s)
- Pod Scaling (VPA, HPA)
- Node Scaling
- Probe (Liveness, Readiness, Startup)

## 3일차

### Observability

- Observability 기본 개념
- Logs, Metrics, Trace의 각 개념과 차이점
- SLI, SLO, SLA 개념
- Alerting

### Monitoring

- RED 패턴, USE 패턴
- 서비스 수준 모니터링
- 리소스 수준 모니터링
- 쿠버네티스 주요 모니터링 요소
- 데이터베이스 주요 모니터링 요소

### Logging

- 로그 종류와 레벨
- EFK 스택
- Fluentbit, Fluentd 차이점
- back-pressure 현상

## 4일차

### Load Test

- 로드 테스트, 성능 테스트, 스트레스 테스트, 스파이크 테스트 차이
- TPS/RPS, Latency, Error Rate, Timeout 해석
- 모니터링 지표 분석
- 로드 테스트 결과 기반 병목 원인 추정
- k6 기반 로드테스트 실습
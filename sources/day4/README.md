# Day 4 실습 과제: k6 로드 테스트

## 개요

Day 2에서 배포한 5개 애플리케이션을 대상으로 k6 로드 테스트를 수행합니다.
각 스크립트는 테스트 유형(Load, Stress, Spike, Soak)과 앱 특성을 매칭하여 설계되었습니다.

## 디렉터리 구조

```
sources/day4/
├── README.md
└── scripts/
    ├── 01_load_basic.js      # Load Test    — basic 앱 기본 성능 측정
    ├── 02_load_mysql.js      # Load Test    — mysql CRUD 읽기/쓰기 시나리오
    ├── 03_stress_cpu.js      # Stress Test  — cpu-load + HPA 스케일 아웃 관찰
    ├── 04_soak_memory.js     # Soak Test    — memory-load 메모리 누수 탐지
    └── 05_spike_slow.js      # Spike Test   — slow-response 타임아웃·큐 포화 관찰
```

## 사전 조건

```bash
# k6 설치 on Amazon Linux 2023
sudo dnf install https://dl.k6.io/rpm/repo.rpm
sudo dnf install k6

# 설치 확인
k6 version
```

## 실행 방법

```bash
# ALB Ingress 주소로 변경하여 실행
# 각 스크립트 실행 (BASE_URL 환경변수 전달)
k6 run -e BASE_URL="${BASE_URL}" scripts/01_load_basic.js
k6 run -e BASE_URL="${BASE_URL}" scripts/02_load_mysql.js
k6 run -e BASE_URL="${BASE_URL}" scripts/03_stress_cpu.js
k6 run -e BASE_URL="${BASE_URL}" scripts/04_soak_memory.js
k6 run -e BASE_URL="${BASE_URL}" scripts/05_spike_slow.js
```

## 테스트별 요약

| 스크립트 | 테스트 유형 | 대상 앱 | 핵심 관찰 포인트 |
|---------|-----------|---------|---------------|
| `01_load_basic.js` | Load Test | basic | P95 응답시간, 최대 RPS |
| `02_load_mysql.js` | Load Test (Scenario) | mysql | 읽기/쓰기 비율별 성능, DB 병목 |
| `03_stress_cpu.js` | Stress Test | cpu-load | 한계 부하, HPA Scale-Out 타이밍 |
| `04_soak_memory.js` | Soak Test | memory-load | 시간에 따른 응답 시간 저하, OOMKilled |
| `05_spike_slow.js` | Spike Test | slow-response | 타임아웃, 큐 포화, 연결 거부 |

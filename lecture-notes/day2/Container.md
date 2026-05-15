# Container Fundamentals

## VM vs Container

### VM (Virtual Machine)

하이퍼바이저(VMware, KVM, Hyper-V)가 물리 하드웨어를 가상화해 각 VM에 독립된 **게스트 OS**를 제공한다.

```
┌─────────────────────────────────────────┐
│              Physical Hardware           │
├─────────────────────────────────────────┤
│              Host OS                    │
├─────────────────────────────────────────┤
│              Hypervisor                 │
├──────────────┬──────────────────────────┤
│   VM 1       │   VM 2        │   VM 3  │
│  Guest OS    │  Guest OS     │ Guest OS│
│  App A       │  App B        │  App C  │
└──────────────┴───────────────┴─────────┘
```

### Container

호스트 OS 커널을 **공유**하고, 프로세스 수준의 격리(Namespace)와 자원 제한(cgroups)으로 독립 실행 환경을 제공한다.

```
┌─────────────────────────────────────────┐
│              Physical Hardware           │
├─────────────────────────────────────────┤
│              Host OS (Linux Kernel)     │
├─────────────────────────────────────────┤
│          Container Runtime (containerd) │
├──────────────┬──────────────────────────┤
│ Container 1  │ Container 2  │Container 3│
│  App A       │  App B       │  App C   │
└──────────────┴──────────────┴──────────┘
```

### 비교

| 항목 | VM | Container |
|------|----|-----------|
| **격리 수준** | 완전 격리 (Guest OS 분리) | 프로세스 격리 (커널 공유) |
| **기동 시간** | 분 단위 | 초 단위 |
| **이미지 크기** | GB 단위 | MB 단위 |
| **자원 오버헤드** | 높음 (Guest OS 상주) | 낮음 |
| **이식성** | 하이퍼바이저 의존 | 컨테이너 런타임만 있으면 동일 동작 |
| **보안 격리** | 강함 | 상대적으로 약함 (커널 공유) |
| **적합한 용도** | 강한 격리가 필요한 환경, Windows 워크로드 | 마이크로서비스, 빠른 배포 |

---

## 컨테이너 기반 Linux 기술

컨테이너는 새로운 기술이 아니라 리눅스 커널에 이미 존재하는 세 가지 기술을 조합한 것이다.

### 1. Namespace — 프로세스 격리

각 컨테이너에 독립된 **리눅스 자원 뷰(View)** 를 제공한다. 컨테이너 내부에서 보이는 PID, 네트워크, 파일시스템은 호스트와 완전히 분리된 공간이다.

| Namespace | 격리 대상 | 효과 |
|-----------|-----------|------|
| `pid` | 프로세스 ID | 컨테이너 내부 PID 1이 호스트에서는 다른 PID로 존재 |
| `net` | 네트워크 인터페이스, 라우팅 테이블 | 컨테이너마다 독립된 가상 NIC·IP |
| `mnt` | 마운트 포인트 | 컨테이너만의 파일시스템 트리 |
| `uts` | hostname, domain name | `docker run --name` 으로 지정한 이름이 컨테이너 내 hostname |
| `ipc` | 공유 메모리, 세마포어 | 컨테이너 간 IPC 격리 |
| `user` | UID/GID 매핑 | 컨테이너 내 root가 호스트에서 일반 유저로 매핑 가능 |

```bash
# 현재 프로세스의 namespace 확인
ls -la /proc/self/ns/

# 컨테이너 내부와 호스트의 PID 공간 비교
docker run --rm alpine ps aux        # 컨테이너 내부: PID 1이 ps
ps aux | grep alpine                 # 호스트: 다른 PID로 보임

# 컨테이너의 네트워크 namespace 확인
docker inspect <container> | grep Pid
nsenter -t <pid> -n ip addr          # 컨테이너 net namespace 진입
```

### 2. cgroups (Control Groups) — 자원 제한

프로세스 그룹의 **CPU·메모리·디스크 I/O·네트워크** 사용량을 제한하고 모니터링한다. `docker run --memory`, `--cpus` 옵션이 내부적으로 cgroups를 설정한다.

```bash
# 메모리 256MB, CPU 0.5 코어로 제한
docker run --memory=256m --cpus=0.5 nginx

# 컨테이너의 cgroup 경로 확인
cat /proc/self/cgroup

# cgroup v2 자원 사용량 직접 확인
cat /sys/fs/cgroup/system.slice/docker-<ID>.scope/memory.current
cat /sys/fs/cgroup/system.slice/docker-<ID>.scope/cpu.stat
```

cgroups가 없다면 하나의 컨테이너가 호스트 전체 메모리를 소진해 다른 컨테이너까지 OOM으로 종료시킬 수 있다.

### 3. Union File System (UFS) — 이미지 레이어

여러 파일시스템 레이어를 **하나로 겹쳐 보이게** 하는 기술. Docker 이미지의 레이어 구조를 가능하게 한다. Linux에서는 주로 **OverlayFS**를 사용한다.

```
컨테이너 레이어 (Read-Write)    ← docker run 시 생성, 컨테이너 종료 시 삭제
───────────────────────────────
이미지 레이어 4: COPY app /app  ← Read-Only
이미지 레이어 3: RUN pip install
이미지 레이어 2: COPY requirements.txt
이미지 레이어 1: FROM python:3.12-slim  ← 베이스 이미지
```

- 같은 베이스 이미지 레이어는 여러 컨테이너가 **공유** → 디스크/메모리 절약
- 컨테이너 내에서 파일을 수정하면 Read-Only 레이어를 건드리지 않고 Read-Write 레이어에 복사 후 수정 (**Copy-on-Write**)

```bash
docker history nginx              # 이미지 레이어 목록 및 크기
docker inspect nginx | jq '.[0].RootFS'  # 레이어 SHA 확인
```

---

## Docker Image Layer

이미지는 Dockerfile 명령어 하나하나가 레이어가 된다. 레이어는 **내용의 SHA256 해시**로 식별되며, 동일한 레이어는 로컬에 한 번만 저장된다.

```dockerfile
FROM python:3.12-slim          # 레이어 1: 베이스 이미지 pull
WORKDIR /app                   # 레이어 2: 메타데이터 (실제 크기 없음)
COPY requirements.txt .        # 레이어 3: requirements.txt 추가
RUN pip install -r requirements.txt  # 레이어 4: 패키지 설치 (가장 큼)
COPY . .                       # 레이어 5: 앱 소스 코드 추가
CMD ["python", "app.py"]       # 레이어 6: 메타데이터
```

### 레이어 캐시

빌드 시 이전과 동일한 레이어는 **캐시에서 재사용**한다. 레이어가 변경되면 그 이후의 모든 레이어 캐시가 무효화된다.

```
# 나쁜 예: 소스 코드 변경 시 pip install도 매번 재실행
COPY . .                            ← 소스 변경 시 캐시 무효
RUN pip install -r requirements.txt ← 항상 재실행 (느림)

# 좋은 예: 의존성과 소스를 분리
COPY requirements.txt .             ← requirements.txt가 바뀔 때만 캐시 무효
RUN pip install -r requirements.txt ← requirements.txt 변경 시만 재실행
COPY . .                            ← 소스 변경은 이 레이어만 영향
```

### 레이어 최소화

`RUN` 명령어를 `&&`로 합치면 중간 레이어 없이 최종 결과만 저장해 이미지 크기를 줄인다.

```dockerfile
# 나쁜 예: 3개 레이어, apt 캐시가 레이어 2에 남아 있음
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# 좋은 예: 1개 레이어, 캐시 삭제가 같은 레이어에서 처리됨
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*
```

---

## Dockerfile Best Practices

### 베이스 이미지 선택

```dockerfile
# 피할 것: 전체 OS 이미지 — 불필요한 도구 포함, 보안 취약점 많음
FROM ubuntu:22.04

# 권장: slim/alpine 변형 — 최소한의 패키지만 포함
FROM python:3.12-slim       # Debian 기반 최소 이미지 (~50MB)
FROM python:3.12-alpine     # Alpine 기반 (~10MB, musl libc)

# 최선: distroless — OS 쉘조차 없는 최소 런타임
FROM gcr.io/distroless/python3
```

### 비루트(non-root) 사용자 실행

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# 전용 유저 생성 후 전환 (보안)
RUN adduser --disabled-password --no-create-home appuser
COPY --chown=appuser:appuser . .
USER appuser

CMD ["python", "app.py"]
```

### `.dockerignore`

빌드 컨텍스트에서 불필요한 파일을 제외해 이미지 크기를 줄이고 비밀 파일 유출을 방지한다.

```
# .dockerignore
.git/
__pycache__/
*.pyc
.env
.env.*
venv/
node_modules/
*.log
tests/
```

### 시크릿을 이미지에 포함하지 않기

```dockerfile
# 절대 금지: 이미지 레이어에 키가 영구 저장됨
ENV AWS_SECRET_ACCESS_KEY=abc123
RUN aws s3 cp s3://bucket/file .  # 키가 레이어에 남음

# 올바른 방법: 런타임 환경변수 또는 K8s Secret으로 주입
# docker run -e AWS_SECRET_ACCESS_KEY=$KEY ...
# kubectl create secret generic aws-key --from-literal=key=$KEY
```

### COPY vs ADD

```dockerfile
COPY src/ /app/          # 단순 파일 복사 — 권장
ADD archive.tar.gz /app/ # 압축 자동 해제, URL 다운로드 지원 — 필요할 때만 사용
```

### CMD vs ENTRYPOINT

```dockerfile
# ENTRYPOINT: 컨테이너의 기본 실행 명령 (변경 어려움)
# CMD: 기본 인자 (docker run 시 덮어쓰기 가능)

ENTRYPOINT ["python"]
CMD ["app.py"]
# → docker run my-image          : python app.py
# → docker run my-image other.py : python other.py

# 단독 CMD (가장 일반적)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
```

---

## Multi-Stage Build

하나의 Dockerfile에서 **빌드 환경**과 **실행 환경**을 분리해 최종 이미지에서 빌드 도구를 제거한다.

### 문제: 단일 스테이지 빌드

```dockerfile
FROM golang:1.22
WORKDIR /app
COPY . .
RUN go build -o server .
# 최종 이미지에 Go 컴파일러, 소스 코드, 빌드 캐시가 모두 포함 → ~900MB
CMD ["./server"]
```

### 해결: Multi-Stage Build

```dockerfile
# ── 스테이지 1: 빌드 ──────────────────────────────────────
FROM golang:1.22 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download                  # 의존성 캐시 레이어 분리
COPY . .
RUN CGO_ENABLED=0 go build -o server .

# ── 스테이지 2: 실행 ──────────────────────────────────────
FROM gcr.io/distroless/static AS runner
WORKDIR /app
COPY --from=builder /app/server .    # 빌드 결과물만 복사
EXPOSE 8080
CMD ["/app/server"]
# 최종 이미지: ~10MB (Go 컴파일러, 소스 미포함)
```

### Python 예시

```dockerfile
# ── 스테이지 1: 의존성 설치 ───────────────────────────────
FROM python:3.12-slim AS deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 스테이지 2: 실행 이미지 ───────────────────────────────
FROM python:3.12-slim AS runner
WORKDIR /app
COPY --from=deps /install /usr/local  # 설치된 패키지만 복사
COPY . .
RUN adduser --disabled-password --no-create-home appuser
USER appuser
EXPOSE 5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
```

### 특정 스테이지만 빌드 (CI 캐시 활용)

```bash
# 의존성 레이어만 빌드 (캐시 워밍)
docker build --target deps -t my-app:deps .

# 전체 빌드
docker build -t my-app:latest .

# 빌드 캐시를 레지스트리에서 가져와 재사용 (CI/CD 속도 향상)
docker build \
  --cache-from my-app:deps \
  --cache-from my-app:latest \
  -t my-app:latest .
```

### 이미지 크기 비교

```bash
docker images my-app
# REPOSITORY   TAG        SIZE
# my-app       single     912MB   ← 단일 스테이지 (Go 컴파일러 포함)
# my-app       latest      11MB   ← Multi-stage (바이너리만)
```

---

## 자주 쓰는 Docker 명령어

```bash
# 이미지 빌드
docker build -t my-app:1.0.0 .
docker build --no-cache -t my-app:1.0.0 .   # 캐시 무시

# 컨테이너 실행
docker run -d -p 5000:5000 --name app my-app:1.0.0
docker run --rm -it my-app:1.0.0 /bin/sh     # 일회성 셸 접속

# 실행 중인 컨테이너 관리
docker ps
docker logs -f app          # 실시간 로그
docker exec -it app /bin/sh # 실행 중 컨테이너에 셸 접속
docker stats                # CPU/메모리 실시간 모니터링
docker stop app && docker rm app

# 이미지 관리
docker images
docker rmi my-app:1.0.0
docker image prune          # 미사용 이미지 삭제

# 레지스트리
docker tag my-app:1.0.0 <account>.dkr.ecr.ap-northeast-2.amazonaws.com/my-app:1.0.0
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-northeast-2.amazonaws.com
docker push <account>.dkr.ecr.ap-northeast-2.amazonaws.com/my-app:1.0.0
```

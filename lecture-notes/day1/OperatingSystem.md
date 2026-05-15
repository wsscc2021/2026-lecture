# Operating System Fundamentals

## `top` Command — 시스템 자원 모니터링

`top` 명령어는 실시간으로 시스템의 자원 사용률을 확인하는 대화형 모니터링 도구다.

```
top - 10:23:45 up 3 days,  2:11,  2 users,  load average: 0.52, 0.58, 0.59
Tasks: 212 total,   1 running, 211 sleeping,   0 stopped,   0 zombie
%Cpu(s):  3.2 us,  1.0 sy,  0.0 ni, 95.5 id,  0.2 wa,  0.0 hi,  0.1 si,  0.0 st
MiB Mem :  15888.0 total,   3200.4 free,   8412.1 used,   4275.5 buff/cache
MiB Swap:   2048.0 total,   2048.0 free,      0.0 used.   7100.2 avail Mem
```

### 헤더 주요 지표

| 항목 | 의미 |
|------|------|
| `load average: X, Y, Z` | 최근 1분 / 5분 / 15분 평균 실행 대기 프로세스 수. CPU 코어 수보다 크면 과부하 상태 |
| `us` (user) | 사용자 공간에서 CPU를 소비한 비율 |
| `sy` (system) | 커널(시스템 콜)이 CPU를 소비한 비율 |
| `ni` (nice) | nice 우선순위가 조정된 사용자 프로세스가 사용한 CPU |
| `id` (idle) | CPU가 유휴 상태인 비율 |
| `wa` (iowait) | I/O 완료를 기다리며 CPU가 대기한 비율. 높으면 디스크/네트워크 병목 의심 |
| `st` (steal) | 하이퍼바이저가 물리 CPU를 디스패치받기까지 기다린 CPU 시간 (가상 환경에서 중요) |

### 프로세스 열 주요 항목

| 열 | 의미 |
|----|------|
| `PID` | 프로세스 ID |
| `%CPU` | 해당 프로세스의 CPU 사용률 |
| `%MEM` | 물리 메모리(RSS) 사용률 |
| `RES` | 실제 점유 중인 물리 메모리 크기 |
| `VIRT` | 프로세스가 예약한 가상 메모리 전체 크기 (실제 점유와 다름) |
| `S` | 프로세스 상태 (R: running, S: sleeping, D: disk wait, Z: zombie) |

### 유용한 단축키

| 키 | 동작 |
|----|------|
| `1` | CPU 코어별 사용률 펼쳐 보기 |
| `M` | 메모리 사용량 기준 정렬 |
| `P` | CPU 사용량 기준 정렬 |
| `H` | 스레드 표시/숨김 |
| `V` | 프로세스 트리 보기/해제 |
| `y` | 실행 중인 프로세스 강조 |

### 필터링/검색

| 키 | 기능 |
| ---|-----|
| `o` |	필터 추가 |
| `O` |	필터 조건 보기/선택 |
| `=` |	필터 초기화 |
| `L` |	문자열 검색 |
| `&` |	다음 검색 결과로 이동 |
| `u` |	특정 사용자 프로세스만 보기 |
 
---

## Buffer / Cache

리눅스 커널은 가용 메모리를 디스크 I/O 성능 향상에 적극적으로 활용한다.

- **Buffer**: 파일시스템 메타데이터(디렉터리, inode 등)와 블록 디바이스의 원시 데이터를 임시 저장. 쓰기 작업이 즉시 디스크에 반영되지 않고 버퍼에 모인 뒤 한꺼번에 flush된다.
- **Cache (Page Cache)**: 디스크에서 읽어 온 파일 데이터를 메모리에 보관. 같은 파일을 다시 읽을 때 디스크 접근 없이 메모리에서 바로 반환해 속도를 높인다.

> 두 값 모두 **사용 가능한(avail) 메모리**로 간주된다. 애플리케이션이 메모리를 요청하면 커널이 즉시 반환하므로 "낭비"가 아니다.

### 관련 명령어

```bash
# 전체 메모리 현황 (buff/cache 포함)
free -h

# 페이지 캐시 / 버퍼 상세
cat /proc/meminfo | grep -E 'Buffers|Cached|MemAvailable'

# 캐시 강제 비우기 (테스트 목적; 운영 환경에서는 지양)
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

---

## Foreground / Background / nohup / Daemon

### Foreground vs Background

| 구분 | 설명 |
|------|------|
| **Foreground** | 터미널(셸)과 연결되어 실행. 터미널을 점유하며 사용자 입력을 받음. 터미널 종료 시 SIGHUP으로 함께 종료됨 |
| **Background** | 터미널을 점유하지 않고 뒤에서 실행. 다른 명령을 동시에 실행 가능 |

```bash
# 백그라운드로 실행 (& 기호)
./my-server &

# 현재 실행 중인 작업 목록 확인
jobs

# 백그라운드 작업을 포그라운드로 전환
fg %1

# 실행 중인 포그라운드를 백그라운드로 보내기
# (Ctrl+Z로 일시 정지 후)
bg %1
```

### nohup

터미널이 닫혀도 프로세스가 계속 실행되도록 SIGHUP 신호를 무시한다. 로그아웃 이후에도 작업을 유지해야 할 때 사용.

```bash
nohup ./my-server > server.log 2>&1 &
```

- 표준 출력/에러를 파일로 리다이렉트하지 않으면 `nohup.out`에 자동 저장된다.
- `&`를 붙여 백그라운드로 보내지 않으면 포그라운드로 실행되어 터미널을 점유한다.

AWS EC2 인스턴스의 경우 기본적으로 huponexit


### Daemon

시스템 부팅 시 자동으로 시작되어 백그라운드에서 지속적으로 실행되는 서비스 프로세스. 터미널과 완전히 분리되어 있으며, 일반적으로 systemd가 관리한다.

```bash
# systemd 서비스 시작/중지/상태 확인
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl status nginx

# 부팅 시 자동 시작 등록
sudo systemctl enable nginx

# 현재 실행 중인 서비스 전체 목록
systemctl list-units --type=service --state=running
```

---

## Signals — 프로세스 간 통신

시그널은 프로세스에 비동기적으로 이벤트를 알리는 운영체제 메커니즘이다.

| 시그널 | 번호 | 기본 동작 | 설명 |
|--------|------|-----------|------|
| `SIGINT` | 2 | 종료 | 사용자가 `Ctrl+C`를 눌렀을 때 전송. 프로세스가 잡아서 처리 가능 |
| `SIGTERM` | 15 | 종료 | 정상 종료 요청. 프로세스가 잡아서 정리(clean-up) 후 종료 가능. `kill <PID>` 기본값 |
| `SIGKILL` | 9 | 강제 종료 | 커널이 직접 프로세스를 제거. 프로세스가 무시하거나 잡을 수 없음 |

```bash
# SIGTERM 전송 (기본)
kill <PID>

# SIGKILL 전송 (강제)
kill -9 <PID>

# 프로세스 이름으로 SIGTERM
pkill nginx

# 시그널 종류 전체 목록
kill -l
```

### Graceful Shutdown

프로세스가 SIGTERM을 수신했을 때 즉시 종료하지 않고:
1. 새로운 요청 수신 중단
2. 현재 처리 중인 요청 완료
3. 열린 파일/커넥션/DB 연결 정상 해제
4. 종료

...하는 방식. 쿠버네티스 파드 교체 시 `terminationGracePeriodSeconds` 동안 SIGTERM → 타임아웃 후 SIGKILL 순으로 진행된다.

---

## Process vs Thread

### Process (프로세스)

- 독립적인 메모리 공간(코드, 데이터, 힙, 스택)을 가진 실행 단위
- 다른 프로세스와 메모리를 공유하지 않음 → IPC(파이프, 소켓, 공유 메모리 등)로 통신
- 생성/전환(Context Switch) 비용이 스레드보다 큼
- 한 프로세스 크래시가 다른 프로세스에 영향을 미치지 않음

### Thread (스레드)

- 프로세스 내에서 코드·데이터·힙 메모리를 **공유**하는 실행 흐름
- 각 스레드는 독립적인 스택과 레지스터를 가짐
- 메모리 공유로 통신 비용이 낮지만 동기화(lock, mutex) 필요
- 한 스레드의 잘못된 메모리 접근이 전체 프로세스를 종료시킬 수 있음

### 상태 확인 명령어

```bash
# 실행 중인 프로세스 트리 (부모-자식 관계 포함)
ps auxf

# 특정 프로세스의 스레드 확인
ps -T -p <PID>
# 또는
top -H -p <PID>

# 프로세스 상태 상세 (메모리 맵, fd 등)
cat /proc/<PID>/status

# 전체 프로세스 스냅샷 (스레드 포함)
ps -eLf

# 프로세스 트리 시각화
pstree -p
```

### 프로세스 상태 값 (S 열)

| 상태 | 의미 |
|------|------|
| `R` (Running) | CPU에서 실행 중이거나 실행 대기 중 |
| `S` (Sleeping) | 이벤트(I/O, 타이머 등)를 기다리며 대기 중 (인터럽트 가능) |
| `D` (Disk wait) | 인터럽트 불가능한 I/O 대기. 높으면 스토리지 병목 |
| `Z` (Zombie) | 종료됐지만 부모가 `wait()`을 호출하지 않아 PCB가 남아 있는 상태 |
| `T` (Stopped) | `Ctrl+Z` 또는 SIGSTOP으로 일시 정지된 상태 |

---

## Orphan Process (고아 프로세스)

### 개념

부모 프로세스가 자식보다 먼저 종료된 경우, 자식 프로세스는 **고아 프로세스**가 된다. 리눅스 커널은 고아 프로세스를 자동으로 **init(PID 1)** 또는 systemd에게 입양(re-parent)시킨다. 이후 자식이 종료되면 init이 `wait()`을 호출해 정상적으로 회수한다.

```
부모(PID 100) ──→ 자식(PID 200)
     │
  [종료]
     ↓
init(PID 1) ──→ 자식(PID 200)   ← 자동 입양
```

### 발생 시나리오

- 터미널에서 `nohup` 없이 실행한 프로세스의 셸이 닫힌 경우
- 서버 프로세스가 자식을 fork한 뒤 비정상 종료된 경우

### 고아 프로세스가 위험한 경우

- 의도하지 않은 프로세스가 계속 실행됨
- CPU/메모리/포트/파일 핸들을 계속 점유함
- 서비스 중지나 재배포 후에도 이전 프로세스가 남음
- 컨테이너에서 PID 1이 자식 프로세스를 제대로 관리하지 못함
- 장애 분석과 프로세스 추적이 어려워짐

---

## Zombie Process (좀비 프로세스)

### 개념

자식 프로세스가 종료(`exit()`)됐지만 부모가 아직 `wait()`을 호출하지 않은 경우, 자식의 **PCB(Process Control Block)** 가 커널에 남아 있는 상태다. 이 상태의 프로세스를 좀비(Zombie, `Z`)라고 한다.

- 실제 CPU·메모리는 사용하지 않는다
- PID 슬롯만 점유한다 (PID는 유한 자원)
- 부모가 `wait()`을 호출하는 순간 커널이 PCB를 회수하고 좀비가 사라진다

```
자식: exit() 호출
     → 상태 Z (좀비)로 전환, PCB 보존
          ↓
부모: wait() 호출
     → 커널이 PCB 회수, 좀비 소멸
```

### 좀비 프로세스가 위험한 경우

단순 좀비 몇 개는 무해하지만, 부모가 `wait()`을 영구히 호출하지 않으면서 자식을 계속 생성하면 PID 공간(`/proc/sys/kernel/pid_max`, 기본 32768)이 고갈되어 새 프로세스를 생성할 수 없게 된다.

```bash
# 시스템 최대 PID 확인
cat /proc/sys/kernel/pid_max
```

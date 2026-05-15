# Network Fundamentals

## Routing — 라우팅

### 개념

라우터는 패킷의 목적지 IP를 **라우팅 테이블**과 비교해 다음 홉(Next Hop)을 결정한다. 여러 경로가 매칭될 경우 **가장 긴 프리픽스(Longest Prefix Match)** 를 우선한다.

```
목적지: 10.0.1.50

라우팅 테이블:
  10.0.0.0/8    → via 172.16.0.1   ← 8비트 매칭
  10.0.1.0/24   → via 172.16.0.2   ← 24비트 매칭 (우선)
  0.0.0.0/0     → via 172.16.0.254 ← 기본 경로 (default route)
```

```bash
# 라우팅 테이블 확인
ip route show
route -n          # 구형 명령어

# 특정 목적지에 어떤 경로를 사용하는지 확인
ip route get 8.8.8.8
```

### Static Routing (정적 라우팅)

관리자가 직접 경로를 설정. 변경이 적은 소규모 네트워크나 특정 트래픽을 강제로 유도할 때 사용.

```bash
# 경로 추가
sudo ip route add 192.168.10.0/24 via 10.0.0.1

# 경로 삭제
sudo ip route del 192.168.10.0/24
```

| 장점 | 단점 |
|------|------|
| 예측 가능, 오버헤드 없음 | 장애 시 자동 전환 불가 |
| 설정이 단순 | 규모가 커지면 관리 어려움 |

### Dynamic Routing (동적 라우팅)

라우터들이 프로토콜을 통해 경로 정보를 **자동으로 교환**하고 갱신. 장애 발생 시 대체 경로로 자동 전환.

| 프로토콜 | 유형 | 용도 |
|----------|------|------|
| **OSPF** | Link-State (IGP) | 단일 AS 내부, 비용(cost) 기반 |
| **BGP** | Path-Vector (EGP) | AS 간, 인터넷 백본. AWS Direct Connect·Transit Gateway가 BGP 사용 |
| RIP | Distance-Vector (IGP) | 소규모, 현재는 거의 미사용 |

> AWS VPC에서 온프레미스와 연결할 때 VPN Gateway나 Direct Connect에서 BGP로 경로를 교환한다.

---

## DNS — 도메인 이름 시스템

### 계층 구조

```
.(root)
  └── com.  (TLD: Top-Level Domain)
        └── example.com.  (Authoritative)
                └── www.example.com.  (A Record → 93.184.216.34)
```

DNS 조회는 오른쪽에서 왼쪽으로(루트 → TLD → 권한 서버) 진행된다.

### Recursive Query vs Iterative Query

**Recursive Query (재귀 쿼리)**
- 클라이언트가 **Resolver(재귀 해석기)** 에게 최종 답을 요청
- Resolver가 루트 → TLD → 권한 서버를 대신 순회하고 최종 IP를 반환
- 일반 사용자의 PC나 서버가 DNS 쿼리를 보낼 때의 방식

```
클라이언트 ──(재귀 요청)──→ Resolver
                              ├─→ Root NS     → TLD NS 주소
                              ├─→ TLD NS      → 권한 NS 주소
                              └─→ 권한 NS     → 최종 IP
           ←─(최종 IP)──────── Resolver
```

**Iterative Query (반복 쿼리)**
- Resolver가 각 서버에 직접 물어볼 때 사용하는 방식
- 서버는 정답 또는 **다음에 물어볼 서버 주소(Referral)** 를 반환
- Resolver 내부에서 단계별로 반복 수행

### DNS Delegation (위임)

상위 도메인이 하위 도메인의 관리를 **NS 레코드**를 통해 다른 네임서버에게 위임.

```
example.com. 의 권한 NS가 sub.example.com. 영역을 위임:

  sub.example.com.  NS  ns1.subdomain-provider.com.
```

AWS Route 53에서 서브도메인을 별도 Hosted Zone으로 분리할 때 동일한 위임 구조를 사용한다.

### DNS Record 타입

| 레코드 | 용도 | 예시 |
|--------|------|------|
| `A` | 도메인 → IPv4 | `example.com. A 93.184.216.34` |
| `AAAA` | 도메인 → IPv6 | `example.com. AAAA 2606:2800::1` |
| `CNAME` | 도메인 → 다른 도메인 (별칭) | `www CNAME example.com.` |
| `MX` | 메일 서버 지정 (우선순위 포함) | `example.com. MX 10 mail.example.com.` |
| `NS` | 권한 네임서버 지정 / 위임 | `example.com. NS ns1.example.com.` |
| `TXT` | 임의 텍스트 (SPF, DKIM, 도메인 인증) | `"v=spf1 include:_spf.google.com ~all"` |
| `PTR` | IP → 도메인 (역방향 조회) | `34.216.184.93.in-addr.arpa. PTR example.com.` |
| `SOA` | 영역의 기본 정보 (TTL, Serial 등) | 영역 파일의 첫 레코드 |

> CNAME은 루트 도메인(`example.com.`)에 사용할 수 없다. AWS Route 53의 **Alias 레코드**는 이 제한을 우회해 루트 도메인을 ELB나 CloudFront에 연결할 수 있다.

---

## TCP vs UDP

### 비교

| 항목 | TCP | UDP |
|------|-----|-----|
| 연결 방식 | 연결 지향 (3-way handshake) | 비연결 |
| 신뢰성 | 순서 보장, 재전송 | 보장 없음 |
| 흐름 제어 | Window size로 제어 | 없음 |
| 헤더 크기 | 20~60 bytes | 8 bytes |
| 속도 | 상대적으로 느림 | 빠름 |
| 사용 예 | HTTP, SSH, DB | DNS, QUIC, 스트리밍, 게임 |

### 3-Way Handshake (연결 수립)

```
클라이언트                          서버
    │── SYN (seq=x) ──────────────→ │   클라이언트: 연결 요청
    │← SYN-ACK (seq=y, ack=x+1) ──  │   서버: 수락 + 자신의 seq 전송
    │── ACK (ack=y+1) ─────────────→ │   클라이언트: 확인
    │          [연결 수립]            │
```

- **SYN**: 연결 요청, 클라이언트의 Initial Sequence Number(ISN) 전달
- **SYN-ACK**: 요청 수락 + 서버의 ISN 전달
- **ACK**: 서버 ISN 확인 → 이후 데이터 전송 시작

### 4-Way Handshake (연결 종료)

```
클라이언트                          서버
    │── FIN ────────────────────────→ │   클라이언트: 전송 끝
    │← ACK ──────────────────────── │   서버: 확인 (서버 데이터 전송 가능)
    │← FIN ──────────────────────── │   서버: 전송 끝
    │── ACK ────────────────────────→ │   클라이언트: 확인
    │  [TIME_WAIT → CLOSED]          │
```

- **TIME_WAIT**: 마지막 ACK 유실에 대비해 클라이언트가 2MSL(최대 세그먼트 수명 × 2)간 대기
- 서버는 `CLOSE_WAIT` 상태에서 자신의 데이터를 모두 보낸 뒤 FIN을 전송

```bash
# 현재 TCP 연결 상태 확인
ss -tn
netstat -tn    # 구형 명령어

# TIME_WAIT 개수만 카운트
ss -tn | grep TIME-WAIT | wc -l
```

### Window Size — 흐름 제어 / 혼잡 제어

**흐름 제어 (Flow Control)**
수신자가 자신의 **수신 버퍼 크기**를 Window Size 필드로 송신자에게 알려 과부하를 방지.

```
송신자 ──[데이터 (window size만큼)]──→ 수신자
       ←──[ACK + 새 window size]────
```

**혼잡 제어 (Congestion Control)**
네트워크 혼잡을 감지(패킷 손실, RTT 증가)하면 **Congestion Window(cwnd)** 를 줄여 전송 속도를 낮춤.

| 알고리즘 | 동작 |
|----------|------|
| Slow Start | 연결 초기, cwnd를 1 → 2 → 4 … 지수적 증가 |
| Congestion Avoidance | 임계치(ssthresh) 이후 선형 증가 |
| Fast Retransmit | 3 ACK 중복 수신 시 타임아웃 없이 즉시 재전송 |

```bash
# 특정 연결의 TCP 상세 정보 (window size, rtt 등)
ss -tni dst 8.8.8.8
```

---

## Network Tools

### `nc` — Netcat

TCP/UDP 연결을 열거나 간단한 서버를 만들 수 있는 범용 도구. 포트 개방 여부 확인, 데이터 전송 테스트에 활용.

```bash
# 포트 연결 테스트 (80 포트가 열려 있는지)
nc -zv example.com 80

# UDP 포트 테스트
nc -zvu example.com 53

# 간단한 TCP 서버 (8080 포트 수신 대기)
nc -l 8080

# 파일 전송: 수신 측
nc -l 9999 > received.txt
# 파일 전송: 송신 측
nc <server-ip> 9999 < send.txt
```

### `traceroute` — 경로 추적

패킷이 목적지까지 거치는 라우터(홉)와 각 구간의 RTT를 표시. TTL을 1씩 늘려가며 ICMP Time Exceeded 응답을 수집.

```bash
traceroute 8.8.8.8

# ICMP 대신 TCP SYN 사용 (방화벽 우회)
traceroute -T -p 80 8.8.8.8

# UDP 비활성화, ICMP 사용
traceroute -I 8.8.8.8
```

```
traceroute to 8.8.8.8, 30 hops max
 1  192.168.1.1    1.2 ms    ← 로컬 게이트웨이
 2  10.0.0.1       5.4 ms    ← ISP
 3  * * *                    ← ICMP 차단 (응답 없음)
 4  8.8.8.8       12.3 ms    ← 목적지
```

### `nslookup` — DNS 조회

```bash
# 기본 조회 (A 레코드)
nslookup example.com

# 특정 레코드 타입 조회
nslookup -type=MX example.com
nslookup -type=NS example.com

# 특정 DNS 서버에 질의
nslookup example.com 8.8.8.8

# 역방향 조회 (IP → 도메인)
nslookup 93.184.216.34
```

### `dig` — 상세 DNS 조회

nslookup보다 상세한 DNS 응답(쿼리 시간, TTL, Authority 섹션 등)을 보여준다.

```bash
# 기본 A 레코드 조회
dig example.com

# 특정 레코드 타입
dig example.com MX
dig example.com NS
dig example.com TXT

# 짧은 출력 (+short)
dig +short example.com

# 특정 DNS 서버에 질의
dig @8.8.8.8 example.com

# DNS 조회 전 과정 추적 (루트부터 단계별)
dig +trace example.com

# 역방향 조회
dig -x 93.184.216.34
```

dig 응답 구조:
```
;; QUESTION SECTION:    ← 질문
;; ANSWER SECTION:      ← 응답 (A 레코드, TTL 포함)
;; AUTHORITY SECTION:   ← 권한 네임서버 정보
;; ADDITIONAL SECTION:  ← 추가 정보 (NS의 IP 등)
;; Query time: 12 msec  ← 응답 시간
```

### `tcpdump` — 패킷 캡처

네트워크 인터페이스를 지나는 패킷을 실시간으로 캡처하고 분석.

```bash
# 모든 인터페이스에서 캡처
sudo tcpdump -i any

# 특정 인터페이스
sudo tcpdump -i eth0

# 특정 호스트 필터
sudo tcpdump -i any host 8.8.8.8

# 특정 포트 필터
sudo tcpdump -i any port 80

# 복합 필터 (DNS 트래픽)
sudo tcpdump -i any udp port 53

# 패킷 내용 출력 (-A: ASCII, -X: hex+ASCII)
sudo tcpdump -i any -A port 80

# 파일로 저장 후 Wireshark로 분석
sudo tcpdump -i any -w capture.pcap

# 저장된 파일 읽기
tcpdump -r capture.pcap
```

주요 필터 표현식:

| 표현식 | 의미 |
|--------|------|
| `host 1.2.3.4` | 해당 IP 송수신 |
| `port 443` | 해당 포트 |
| `tcp` / `udp` | 프로토콜 |
| `src 1.2.3.4` | 출발지 IP |
| `dst port 53` | 목적지 포트 |
| `not port 22` | 제외 |
| `tcp[tcpflags] & tcp-syn != 0` | SYN 패킷만 |

### `netstat` / `ss` — 소켓 및 연결 상태

`netstat`은 열린 포트, 활성 연결, 라우팅 테이블을 확인하는 전통적인 도구. 현대 리눅스에서는 더 빠른 `ss`(socket statistics)로 대체되고 있다.

```bash
# 모든 TCP 연결 (숫자 주소, 프로세스 포함)
netstat -tnp
ss -tnp          # 동일 기능, 더 빠름

# LISTEN 상태(열린 포트)만 표시
netstat -tlnp
ss -tlnp

# UDP 소켓
netstat -ulnp
ss -ulnp

# 연결 상태별 집계 (TIME_WAIT 과다 여부 확인)
ss -s

# 특정 포트를 점유한 프로세스 확인
ss -tlnp sport = :8080

# 특정 목적지 연결만 표시
ss -tn dst 10.0.0.1
```

출력 열 의미 (`ss -tnp` 기준):

| 열 | 의미 |
|----|------|
| `State` | TCP 상태 (ESTAB, LISTEN, TIME-WAIT 등) |
| `Recv-Q` | 수신 버퍼에 쌓인 미처리 바이트 (높으면 앱이 데이터를 못 읽는 중) |
| `Send-Q` | 송신 버퍼에서 ACK를 못 받은 바이트 (높으면 네트워크 병목) |
| `Local Address:Port` | 로컬 IP:포트 |
| `Peer Address:Port` | 원격 IP:포트 |
| `Process` | PID와 프로세스 이름 |

### `ping` — 연결성 확인

ICMP Echo Request를 보내 목적지까지 도달 여부와 RTT를 측정.

```bash
# 기본 ping
ping 8.8.8.8

# 횟수 제한
ping -c 4 8.8.8.8

# 패킷 크기 지정 (MTU 테스트)
ping -s 1400 8.8.8.8

# 인터페이스 지정
ping -I eth0 8.8.8.8

# 빠른 flood ping (root 필요, 네트워크 부하 테스트)
sudo ping -f -c 1000 192.168.1.1
```

> EC2 Security Group에서 ICMP를 허용해야 ping이 응답한다. 응답이 없다고 호스트가 다운된 것은 아님.

### `mtr` — 경로 추적 + 실시간 통계

`traceroute`와 `ping`을 합친 도구. 각 홉의 패킷 손실률과 RTT 변동을 실시간으로 모니터링.

```bash
# 대화형 모드
mtr 8.8.8.8

# 비대화형 (100 패킷 후 리포트 출력)
mtr -r -c 100 8.8.8.8

# TCP 모드 (ICMP 차단 우회)
mtr --tcp --port 443 8.8.8.8
```

```
                             Loss%   Snt   Last   Avg  Best  Wrst
 1. 192.168.1.1               0.0%   10    0.8   0.9   0.7   1.2
 2. 10.0.0.1                  0.0%   10    4.2   4.5   4.0   5.1
 3. ???                      100.0%  10     --    --    --    --   ← ICMP 차단
 4. 8.8.8.8                   0.0%   10   11.3  11.5  11.0  12.0
```

- **Loss%** 가 특정 홉에서만 높고 그 이후 홉에서 정상이면 해당 홉이 ICMP를 제한하는 것 (실제 손실 아님)
- 마지막 홉(목적지)의 Loss%가 높으면 실제 패킷 손실

### `curl` — HTTP/HTTPS 요청

API 엔드포인트, 서비스 헬스체크, HTTP 응답 헤더 분석에 사용.

```bash
# GET 요청
curl https://example.com

# 응답 헤더만 출력
curl -I https://example.com

# 상태 코드만 출력
curl -o /dev/null -s -w "%{http_code}" https://example.com

# POST 요청 (JSON)
curl -X POST https://api.example.com/data \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# 응답 시간 측정 (DNS / Connect / TTFB 등)
curl -o /dev/null -s -w "\
  dns: %{time_namelookup}s\n\
  connect: %{time_connect}s\n\
  ttfb: %{time_starttransfer}s\n\
  total: %{time_total}s\n" https://example.com

# 특정 DNS 서버로 강제 해석 (Route 53 테스트 시 유용)
curl --resolve example.com:443:93.184.216.34 https://example.com

# 인증서 무시 (테스트용)
curl -k https://self-signed.example.com
```

### `ip` — 인터페이스 및 주소 관리

`ifconfig`의 현대적 대체 명령어. 인터페이스 상태, IP 주소, 라우팅, ARP 테이블을 통합 관리.

```bash
# 인터페이스 목록 및 IP 주소
ip addr show
ip a             # 단축형

# 특정 인터페이스만
ip addr show eth0

# 인터페이스 활성화/비활성화
sudo ip link set eth0 up
sudo ip link set eth0 down

# 임시 IP 주소 추가/삭제
sudo ip addr add 192.168.1.100/24 dev eth0
sudo ip addr del 192.168.1.100/24 dev eth0

# 라우팅 테이블
ip route show

# ARP 테이블 (MAC 주소 ↔ IP 매핑)
ip neigh show
```

### 도구 선택 가이드

| 상황 | 사용 도구 |
|------|-----------|
| 호스트 도달 가능 여부 | `ping` |
| 어느 구간에서 지연/손실 발생 | `mtr` |
| 포트가 열려 있는지 확인 | `nc -zv` |
| 어떤 프로세스가 포트를 점유 | `ss -tlnp` |
| DNS 레코드 조회 | `dig` / `nslookup` |
| HTTP API 응답 확인 | `curl` |
| 실제 패킷 내용 분석 | `tcpdump` |
| 인터페이스 IP / 라우팅 확인 | `ip addr`, `ip route` |

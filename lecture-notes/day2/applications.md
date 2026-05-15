앱	주요 엔드포인트	특징
01_basic	GET /, /health, /env, /headers	hostname·timestamp 반환. K8s Pod 확인, Probe 실습용
02_mysql	GET/POST /users, GET/PUT/DELETE /users/<id>, /health	CRUD + DB 연결 상태 헬스체크. init.sql로 테이블 초기화
03_cpu_load	POST /load {"duration":30,"workers":2}, POST /stop	multiprocessing으로 코어별 독립 프로세스 생성. top의 us 항목으로 확인
04_memory_load	POST /allocate {"mb":256}, POST /release, POST /leak {"mb":50}, POST /leak/stop	메모리 할당 유지 + 누수 시뮬레이션. top의 RES·%MEM 확인
05_slow_response	GET / (40초), GET /slow?seconds=N, GET /fast, GET /health	DEFAULT_DELAY 환경변수로 기본 지연 조정 가능. curl --max-time 5 타임아웃 실습용
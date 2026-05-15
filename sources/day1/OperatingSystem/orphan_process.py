import os, time

pid = os.fork()

if pid == 0:          # 자식
    print(f"자식(PID {os.getpid()})")
    time.sleep(120)    # 부모가 먼저 죽는 동안 살아 있음
    print(f"자식 프로세스 종료")  # 실행 시 1(init)로 바뀌어 있음
else:                 # 부모
    print(f"부모(PID {os.getpid()})")
    os._exit(0)       # 자식보다 먼저 종료 → 자식이 고아가 됨
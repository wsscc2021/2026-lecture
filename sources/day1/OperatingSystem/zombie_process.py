import os, time

pid = os.fork()
if pid == 0:      # 자식
    print(f"자식(PID {os.getpid()}) 종료")
    os._exit(0)   # 종료했지만 부모가 wait()을 안 부름 → 좀비
else:             # 부모
    time.sleep(120)  # 이 30초 동안 자식은 좀비 상태
    # ps aux | grep Z 로 확인 가능
    os.wait()     # 이 시점에 좀비 회수
    print("자식 회수 완료")
import os
import time

data = []

print(f"PID: {os.getpid()}", flush=True)

chunk_size_mb = 10

while True:
    data.append(bytearray(chunk_size_mb * 1024 * 1024))
    print(f"Allocated: {len(data) * chunk_size_mb} MB", flush=True)
    time.sleep(1)

# dnf update -y
# dnf install -y docker
# systemctl start docker
# docker build -t memory-oom .
# docker run --name memory-oom-test -d --memory=128m memory-oom
# docker logs -f memory-oom-test
# docker inspect memory-oom-test --format '{{.State.OOMKilled}}'

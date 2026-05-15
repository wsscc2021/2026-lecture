#!/usr/bin/env python3
"""
I/O Wait generator — demonstrates high iowait in `top`.

Two modes
---------
fsync mode (default)
  Writes a chunk then calls fsync(). The kernel page cache still absorbs the
  write first, so some CPU cycles are "hidden" inside the cache layer.
  Typical result: 30–60 % iowait.

direct mode (--direct)
  Opens the file with O_DIRECT, which bypasses the page cache entirely.
  Every write() call blocks until the EBS volume acknowledges the data.
  The worker thread sits in kernel iowait for nearly the whole duration.
  Typical result on t3.micro: 90–100 % iowait.

Usage
-----
  python3 generate_iowait.py                        # fsync, 2 workers, 60 s
  python3 generate_iowait.py --direct               # O_DIRECT mode
  python3 generate_iowait.py --direct --workers 2 --chunk-mb 4 --duration 120

Monitor in another terminal
---------------------------
  top           # press '1' to expand per-core, watch 'wa'
  iostat -x 1   # watch %iowait and %util columns
"""

import argparse
import ctypes
import ctypes.util
import os
import signal
import tempfile
import threading
import time


STOP = threading.Event()

# O_DIRECT is Linux-specific; value = 0x4000 on x86-64
O_DIRECT: int = getattr(os, "O_DIRECT", 0x4000)


def _handle_signal(sig, frame) -> None:
    print("\n[*] Stopping...", flush=True)
    STOP.set()


# ---------------------------------------------------------------------------
# Aligned memory allocation (required for O_DIRECT)
# ---------------------------------------------------------------------------

def _alloc_aligned(size: int, alignment: int = 4096) -> ctypes.Array:
    """
    Allocate a buffer aligned to `alignment` bytes via posix_memalign.

    O_DIRECT requires:
      - Buffer address aligned to the device logical block size (512 or 4096 B)
      - Transfer size a multiple of that block size
    Regular Python bytes objects are NOT guaranteed to be aligned,
    so we must go through libc.
    """
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    ptr = ctypes.c_void_p()
    ret = libc.posix_memalign(ctypes.byref(ptr), alignment, size)
    if ret != 0:
        raise OSError(ret, "posix_memalign failed")
    buf = (ctypes.c_char * size).from_address(ptr.value)
    # Fill with non-zero data so the drive can't skip compressed-zero pages
    ctypes.memmove(buf, os.urandom(size), size)
    return buf


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def iowait_worker(worker_id: int, chunk_bytes: int, tmp_dir: str, direct: bool) -> None:
    path = os.path.join(tmp_dir, f"iowait_worker_{worker_id}.dat")

    if direct:
        # Pre-allocate an aligned buffer — do this ONCE outside the write loop
        # so the hot path contains zero CPU work between disk writes.
        buf = _alloc_aligned(chunk_bytes)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | O_DIRECT
        try:
            fd = os.open(path, flags, 0o644)
        except OSError as e:
            if e.errno == 22:  # EINVAL
                raise SystemExit(
                    f"[worker-{worker_id}] O_DIRECT not supported on this filesystem.\n"
                    f"  /tmp is usually tmpfs which rejects O_DIRECT.\n"
                    f"  Use --path to point at an ext4/xfs mount, e.g.:\n"
                    f"    python3 generate_iowait.py --direct --path /home"
                ) from None
            raise
    else:
        # Pre-generate random bytes once; reuse in write loop
        buf = os.urandom(chunk_bytes)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

    total_written = 0
    written_this_file = 0
    max_file_bytes = chunk_bytes * 16  # keep temp file from growing unbounded

    try:
        while not STOP.is_set():
            os.write(fd, buf)          # blocks until disk ack (O_DIRECT) or cache (fsync)
            if not direct:
                os.fsync(fd)           # force flush in non-direct mode
            total_written += chunk_bytes
            written_this_file += chunk_bytes

            if written_this_file >= max_file_bytes:
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                written_this_file = 0
    finally:
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)
        print(f"[worker-{worker_id}] wrote {total_written / 1024**2:.1f} MB total", flush=True)


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

def monitor(interval: float = 1.0) -> None:
    def _read_raw() -> list[int]:
        with open("/proc/stat") as f:
            # fields: user nice system idle iowait irq softirq steal ...
            return [int(x) for x in f.readline().split()[1:]]

    prev = _read_raw()
    while not STOP.is_set():
        time.sleep(interval)
        cur = _read_raw()
        delta = [c - p for c, p in zip(cur, prev)]
        total = sum(delta) or 1
        user   = delta[0] / total * 100
        sys_   = delta[2] / total * 100
        idle   = delta[3] / total * 100
        iowait = delta[4] / total * 100
        color  = "\033[1;31m" if iowait > 80 else "\033[1;33m"
        print(
            f"  CPU  user={user:5.1f}%  sys={sys_:5.1f}%  "
            f"idle={idle:5.1f}%  {color}iowait={iowait:5.1f}%\033[0m",
            flush=True,
        )
        prev = cur


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate I/O wait load (use --direct for ~100% iowait)"
    )
    parser.add_argument("--direct",    action="store_true", help="Use O_DIRECT (bypass page cache); requires ext4/xfs, not tmpfs")
    parser.add_argument("--path",      type=str, default=None, help="Directory for temp files (default: /tmp for fsync, current dir for --direct)")
    parser.add_argument("--chunk-mb",  type=int, default=4,  help="Write chunk size in MB, must be multiple of 4 for O_DIRECT (default: 4)")
    parser.add_argument("--duration",  type=int, default=60, help="Run duration in seconds (default: 60)")
    parser.add_argument("--workers",   type=int, default=2,  help="Parallel writer threads (default: 2, matches t3.micro vCPU count)")
    args = parser.parse_args()

    # O_DIRECT requires transfer size to be a multiple of 4096 bytes
    chunk_bytes = args.chunk_mb * 1024 * 1024
    if args.direct and chunk_bytes % 4096 != 0:
        parser.error("--chunk-mb must be a multiple of 4 when using --direct")

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # /tmp is usually tmpfs which does not support O_DIRECT; default to cwd instead
    base_dir = args.path or ("." if args.direct else None)
    tmp_dir = tempfile.mkdtemp(prefix="iowait_", dir=base_dir)
    mode = "O_DIRECT (page cache bypassed)" if args.direct else "fsync"

    print(f"[*] mode={mode}  chunk={args.chunk_mb} MB  workers={args.workers}  duration={args.duration}s")
    print(f"[*] tmp dir: {tmp_dir}")
    print("[*] Monitor: run `top` (press 1 to see per-core wa) or `iostat -x 1`\n")

    threads: list[threading.Thread] = []

    for i in range(args.workers):
        t = threading.Thread(
            target=iowait_worker,
            args=(i, chunk_bytes, tmp_dir, args.direct),
            daemon=True,
        )
        t.start()
        threads.append(t)

    mon = threading.Thread(target=monitor, daemon=True)
    mon.start()

    STOP.wait(timeout=args.duration)
    STOP.set()

    for t in threads:
        t.join(timeout=5)

    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    print("[*] Done.")


if __name__ == "__main__":
    main()

"""EDA 互斥锁: 多个子代理共享一个嘉立创EDA实例时的写操作串行化工具。
用法:
  python eda_lock.py acquire [超时秒=600]   # 抢锁, 成功退出码0; 锁文件被持有则等待
  python eda_lock.py release               # 释放锁
  python eda_lock.py status                # 查看锁状态
锁文件: C:/Users/Lenovo/AppData/Local/Temp/eda_write.lock
内容: 持有者PID+时间戳; 超过15分钟的死锁自动清除(持有进程不存在时)。
"""
import sys, os, time, json

LOCK = r"C:/Users/Lenovo/AppData/Local/Temp/eda_write.lock"
STALE_SEC = 900

def _holder_alive(info):
    try:
        import psutil
        return psutil.pid_exists(info.get("pid", 0))
    except ImportError:
        # 无psutil时用tasklist查
        pid = info.get("pid", 0)
        r = os.popen(f'tasklist /FI "PID eq {pid}" /NH').read()
        return str(pid) in r

def acquire(timeout=600):
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"pid": os.getpid(), "ts": time.time()}).encode())
            os.close(fd)
            print(f"LOCK_ACQUIRED pid={os.getpid()}")
            return 0
        except FileExistsError:
            try:
                with open(LOCK) as f:
                    info = json.load(f)
                age = time.time() - info.get("ts", 0)
                if age > STALE_SEC and not _holder_alive(info):
                    os.remove(LOCK)
                    print(f"STALE_LOCK_REMOVED (age={age:.0f}s)")
                    continue
            except (json.JSONDecodeError, FileNotFoundError):
                try:
                    os.remove(LOCK)
                except OSError:
                    pass
                continue
            if time.time() - t0 > timeout:
                print(f"LOCK_TIMEOUT waited={time.time()-t0:.0f}s holder={info}")
                return 2
            time.sleep(10)

def release():
    try:
        with open(LOCK) as f:
            info = json.load(f)
        if info.get("pid") != os.getpid():
            print(f"WARN: releasing lock held by pid={info.get('pid')} (not me)")
        os.remove(LOCK)
        print("LOCK_RELEASED")
        return 0
    except FileNotFoundError:
        print("LOCK_NOT_HELD")
        return 0

def status():
    try:
        with open(LOCK) as f:
            info = json.load(f)
        age = time.time() - info.get("ts", 0)
        print(f"LOCKED by pid={info.get('pid')} age={age:.0f}s")
        return 1
    except FileNotFoundError:
        print("FREE")
        return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 and cmd == "acquire" else 600
    if cmd == "acquire": sys.exit(acquire(timeout))
    elif cmd == "release": sys.exit(release())
    else: sys.exit(status())

"""Drive the full 2026-11-15 insurance regression.

Job set:
  * numeric, 2 MHz: every vector 0..25 (one vsim process per vector)
  * numeric, vector 16 at 32 kHz / 250 kHz / 1 MHz (frequency invariance)
  * cnn74 protocol test at 2 MHz and 32 kHz

Runs `run_one.py` per job with bounded concurrency and a global status file.
"""
import argparse
import concurrent.futures as cf
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default="all")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--vecs", type=int, default=26)
    a = ap.parse_args()

    jobs = []
    if a.jobs in ("all", "numeric"):
        for v in range(a.vecs):
            jobs.append(("sim_v%02d_2m" % v, "numeric", v, "2m"))
    if a.jobs in ("all", "freq"):
        for f in ("32k", "250k", "1m"):
            jobs.append(("freq_v16_%s" % f, "numeric", 16, f))
    if a.jobs in ("all", "proto"):
        jobs.append(("proto_2m", "cnn74", 0, "2m"))
        jobs.append(("proto_32k", "cnn74", 0, "32k"))

    t0 = time.time()
    status = os.path.join(HERE, "run_status.txt")
    done = []

    def worker(job):
        d, tb, v, f = job
        cmd = [PY, os.path.join(HERE, "run_one.py"), "--dir", os.path.join(HERE, d),
               "--tb", tb, "--vec", str(v), "--freq", f]
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        return d, r.returncode, (r.stdout + r.stderr).strip()[-400:]

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(worker, j): j for j in jobs}
        for fut in cf.as_completed(futs):
            d, rc, tail = fut.result()
            done.append((d, rc))
            line = "%-14s rc=%d %s" % (d, rc, tail if rc else "")
            print(line)
            with open(status, "a", encoding="utf-8") as sf:
                sf.write(line + "\n")

    dt = time.time() - t0
    ok = sum(1 for _, rc in done if rc == 0)
    print("\n=== %d/%d jobs exited 0 in %.1f s ===" % (ok, len(jobs), dt))
    with open(status, "a", encoding="utf-8") as sf:
        sf.write("=== %d/%d exited 0, %.1f s ===\n" % (ok, len(jobs), dt))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())

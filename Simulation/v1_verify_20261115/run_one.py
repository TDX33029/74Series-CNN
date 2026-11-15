"""Run one ModelSim job of the 74CNN-BRD insurance verification.

Creates <rundir>, compiles DUT + TB with the oscillator model of the chosen
frequency, runs, and leaves sim.log + dump_*.hex in <rundir>.
"""
import argparse
import os
import shutil
import subprocess
import sys

MSIM = r"C:\intelFPGA\18.0\modelsim_ase\win32aloem"
RTLSRC = os.path.dirname(os.path.abspath(__file__))
RTL = os.path.join(RTLSRC, "rtl")
WBASE = os.path.join(RTLSRC, "vectorset", "x28s") + os.sep


def run(cmd, cwd, env, log):
    with open(log, "a", encoding="utf-8") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        p = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT,
                           text=True, errors="replace")
        f.write("\n[exit %d]\n" % p.returncode)
        f.flush()
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tb", default="numeric", choices=["numeric", "cnn74"])
    ap.add_argument("--vec", type=int, default=0)
    ap.add_argument("--freq", default="2m", choices=["32k", "250k", "1m", "2m"])
    a = ap.parse_args()

    rundir = os.path.abspath(a.dir)
    if os.path.isdir(rundir):
        for _ in range(5):
            try:
                shutil.rmtree(rundir)
                break
            except PermissionError:
                import time
                time.sleep(2)
        else:
            raise SystemExit("cannot clear %s (still in use)" % rundir)
    os.makedirs(rundir)
    shutil.copytree(os.path.join(RTL, "init"), os.path.join(rundir, "init"))

    env = dict(os.environ)
    env["PATH"] = MSIM + os.sep + ";" + env.get("PATH", "")
    env["MTI_VCO_MODE"] = "32"   # ASE needs the 32-bit kernel flag in some setups

    log = os.path.join(rundir, "build.log")
    for l in ("build.log", "sim.log"):
        p = os.path.join(rundir, l)
        if os.path.exists(p):
            os.remove(p)

    models = os.path.join(RTL, "models_eda_%s.v" % a.freq)
    r = run([os.path.join(MSIM, "vlib.exe"), "work"], rundir, env, log)
    if r != 0:
        return r
    files = [models, os.path.join(RTL, "cnn74_top_eda.v"),
             os.path.join(RTL, "tb_%s.v" % ("numeric" if a.tb == "numeric" else "cnn74"))]
    r = run([os.path.join(MSIM, "vlog.exe"), "-sv", "-work", "work"] + files,
            rundir, env, log)
    if r != 0:
        return r

    args = [os.path.join(MSIM, "vsim.exe"), "-c", "-voptargs=+acc", "work.tb_" + a.tb]
    if a.tb == "numeric":
        args += ["+nvec=1", "+vfirst=%d" % a.vec, "+wbase=%s" % WBASE]
    do = os.path.join(rundir, "run.do")
    with open(do, "w", encoding="ascii", newline="\n") as f:
        f.write("run -all\nquit -f\n")
    args += ["-do", do]
    return run(args, rundir, env, os.path.join(rundir, "sim.log"))


if __name__ == "__main__":
    sys.exit(main())

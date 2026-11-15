"""Check the dumps produced by tb_numeric against the independent golden model.

For every run directory passed, compare
  dump_C1OUT_v.hex  -> exp_c1_v.hex
  dump_P1OUT_v.hex  -> exp_p1_v.hex
  dump_C2OUT_v.hex  -> exp_c2_v.hex
  dump_P2OUT_v.hex  -> exp_p2_v.hex
  dump_FC1OUT_v.hex -> exp_fc1_v.hex
  dump_FC2LOG_v.hex -> logit_v.hex (10 int32, little-endian in SRAM)
and parse the pass/fail lines plus stage DONE times from sim.log.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VEC = os.path.join(HERE, "vectorset", "x28s", "vectors")


def hexbytes(path):
    with open(path, encoding="ascii") as f:
        return [int(x, 16) for x in f if x.strip()]


def vec_id(d):
    m = re.search(r"v(\d+)_", d)
    if m:
        return int(m.group(1))
    for f in glob.glob(os.path.join(d, "dump_FC2LOG_*.hex")):
        m = re.search(r"dump_FC2LOG_(\d+)\.hex", f)
        if m:
            return int(m.group(1))
    return None


def load_logits(path, n=10):
    words = [int(x, 16) for x in open(path) if x.strip()]
    out = []
    for i in range(n):
        v = words[i]
        if v >= 0x80000000:
            v -= 0x100000000
        out.append(v)
    return out


LAYERS = [("C1OUT", "exp_c1", 4608), ("P1OUT", "exp_p1", 1152),
          ("C2OUT", "exp_c2", 1600), ("P2OUT", "exp_p2", 400),
          ("FC1OUT", "exp_fc1", 32)]


def check_dir(d):
    v = vec_id(os.path.basename(d))
    if v is None:
        return None
    res = {"dir": os.path.basename(d), "vec": v, "layers": {}, "errors": 0}
    log = os.path.join(d, "sim.log")
    txt = open(log, encoding="utf-8", errors="replace").read() if os.path.exists(log) else ""
    res["tb_pass"] = "TB RESULT: PASS" in txt
    res["vector_pass"] = "VECTOR %d: PASS" % v in txt
    m = re.search(r"=== NUMERIC RESULT: (\d+)/(\d+) vectors pass, (\d+) total errors", txt)
    if m:
        res["summary"] = "%s/%s pass, %s errors" % m.groups()
    for name, exp_pref, n in LAYERS:
        dump = os.path.join(d, "dump_%s_%d.hex" % (name, v))
        exp = os.path.join(VEC, "%s_%d.hex" % (exp_pref, v))
        if not (os.path.exists(dump) and os.path.exists(exp)):
            res["layers"][name] = "missing"
            res["errors"] += 1
            continue
        got, want = hexbytes(dump), hexbytes(exp)
        if len(got) < n or len(want) < n:
            res["layers"][name] = "short"
            res["errors"] += 1
            continue
        got, want = got[:n], want[:n]
        bad = [(i, g, w) for i, (g, w) in enumerate(zip(got, want)) if g != w]
        res["layers"][name] = "OK" if not bad else "%d/%d differ (first @%d %02x!=%02x)" % (
            len(bad), n, bad[0][0], bad[0][1], bad[0][2])
        if bad:
            res["errors"] += 1
    dump_lg = os.path.join(d, "dump_FC2LOG_%d.hex" % v)
    exp_lg = os.path.join(VEC, "logit_%d.hex" % v)
    if os.path.exists(dump_lg) and os.path.exists(exp_lg):
        b = hexbytes(dump_lg)[:40]
        got = [int.from_bytes(bytes(b[4 * i:4 * i + 4]), "little", signed=True) for i in range(10)]
        want = load_logits(exp_lg)
        ok = got == want
        res["layers"]["FC2LOG"] = "OK" if ok else "got %s want %s" % (got, want)
        if not ok:
            res["errors"] += 1
    else:
        res["layers"]["FC2LOG"] = "missing"
        res["errors"] += 1
    m = re.search(r"FC2LOG write pulses: (\d+)", txt)
    res["fc2log_we"] = int(m.group(1)) if m else None
    times = {}
    for stage in ("C1_DONE", "P1_DONE", "C2_DONE", "P2_DONE", "FC1_DONE",
                  "FC2_DONE", "ARGMAX_DONE"):
        mm = re.findall(r"\[(\d+)\] " + stage, txt)
        if mm:
            times[stage] = int(mm[-1])
    res["done_times_ps"] = times
    # ModelSim prints $time in ps here (timescale 1ns/1ps); 1e12 ps = 1 s.
    m = re.search(r"\[TB\] recognition START at (\d+)", txt)
    if m and times:
        res["recognition_ms"] = (times.get("ARGMAX_DONE", max(times.values()))
                                 - int(m.group(1))) / 1e9
    return res


def main(dirs):
    rows = []
    for d in dirs:
        r = check_dir(d)
        if r:
            rows.append(r)
    if not rows:
        print("no run dirs matched")
        return 2
    total_err = 0
    for r in sorted(rows, key=lambda x: x["vec"]):
        total_err += r["errors"]
        print("vec %2d (%s): tb=%s %s" % (r["vec"], r["dir"],
                                         "PASS" if r["tb_pass"] else "FAIL",
                                         r.get("summary", "")))
        for k, v in r["layers"].items():
            print("    %-7s %s" % (k, v))
        if r.get("recognition_ms"):
            print("    recognition %.3f ms" % r["recognition_ms"])
    print("\nTOTAL layer/logit errors: %d" % total_err)
    with open(os.path.join(HERE, "check_summary.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

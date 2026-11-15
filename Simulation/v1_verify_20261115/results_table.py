"""Build the final markdown/CSV result tables from check_summary.json."""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VEC = os.path.join(HERE, "vectorset", "x28s", "vectors")
FREQS = {"freq_v16_32k": 32000, "freq_v16_250k": 250000,
         "freq_v16_1m": 1000000, "sim_v16_2m": 2000000}


def meta_label(v):
    p = os.path.join(VEC, "meta_%d.txt" % v)
    if not os.path.exists(p):
        return None
    d = {}
    for line in open(p):
        k, _, val = line.partition(" ")
        d[k.strip()] = val.strip()
    return d.get("label")


def hw_logits(d, v):
    p = os.path.join(HERE, d, "dump_FC2LOG_%d.hex" % v)
    b = [int(x, 16) for x in open(p) if x.strip()][:40]
    return [int.from_bytes(bytes(b[4 * i:4 * i + 4]), "little", signed=True) for i in range(10)]


def main():
    rows = json.load(open(os.path.join(HERE, "check_summary.json"), encoding="utf-8"))
    table = []
    for r in sorted(rows, key=lambda x: x["vec"]):
        v, d = r["vec"], r["dir"]
        lg = hw_logits(d, v)
        top = max(range(10), key=lambda i: lg[i])
        second = sorted(lg, reverse=True)[1]
        layers_ok = all(x == "OK" for x in r["layers"].values())
        table.append({"vec": v, "dir": d, "label": meta_label(v), "hw": top,
                      "margin": lg[top] - second, "layers": layers_ok,
                      "errors": r["errors"], "tb": r["tb_pass"],
                      "recog_ms": r.get("recognition_ms")})
    with open(os.path.join(HERE, "results_26_vectors.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("| vec | 真实标签 | 硬件 argmax | top1-top2 | 6 层逐字节 | TB |")
    print("|---:|---:|---:|---:|:---:|:---:|")
    for t in table:
        print("| %d | %s | %d | %d | %s | %s |" % (
            t["vec"], t["label"], t["hw"], t["margin"],
            "OK" if t["layers"] else "FAIL", "PASS" if t["tb"] else "FAIL"))

    print("\n| 频率 | 识别时间 | 折合拍数 |")
    print("|---|---:|---:|")
    for d, f in FREQS.items():
        for r in rows:
            if r["dir"] == d:
                ms = r["recognition_ms"]
                print("| %s | %.3f ms | %.0f |" % (d, ms, ms / 1000 * f))
    uni = {}
    for t in table:
        uni.setdefault(t["vec"], t)
    labeled = [t for t in uni.values() if t["label"] and t["label"] not in ("-1", None)]
    print("\nall layers OK: %d/%d" % (sum(1 for t in table if t["layers"]), len(table)))
    print("all TB PASS: %d/%d" % (sum(1 for t in table if t["tb"]), len(table)))
    print("argmax matches golden: %d/%d (labeled vectors)" % (
        sum(1 for t in labeled if int(t["label"]) == t["hw"]), len(labeled)))


if __name__ == "__main__":
    main()

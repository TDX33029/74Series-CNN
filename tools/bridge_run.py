#!/usr/bin/env python3
"""Run JS in EasyEDA via bridge POST /execute. Usage: python bridge_run.py <codefile> [outfile]"""
import json, sys, subprocess, os

PORT = 49620
URL = f"http://localhost:{PORT}/execute"
OUT_DIR = r"C:\Users\Lenovo\AppData\Local\Temp"

def run(code, timeout=90):
    payload = json.dumps({"code": code}, ensure_ascii=False)
    p = os.path.join(OUT_DIR, "eda_req.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write(payload)
    r = subprocess.run(
        ["curl", "-s", "-m", str(timeout), "-X", "POST", URL,
         "-H", "Content-Type: application/json", "--data-binary", "@" + p],
        capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return None, f"curl failed rc={r.returncode} stderr={r.stderr[:200]}"
    try:
        resp = json.loads(r.stdout)
    except Exception as e:
        return None, f"bad json: {r.stdout[:300]}"
    if not resp.get("success"):
        return None, f"bridge error: {str(resp)[:400]}"
    return resp.get("result"), None

if __name__ == "__main__":
    codefile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else None
    with open(codefile, "r", encoding="utf-8") as f:
        code = f.read()
    result, err = run(code)
    if err:
        print("ERROR:", err)
        sys.exit(1)
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"saved -> {outfile} ({len(text)} chars)")
    print(text[:3000])

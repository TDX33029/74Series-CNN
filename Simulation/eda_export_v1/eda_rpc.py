"""Minimal EasyEDA bridge client for the 2026-11-15 insurance run."""
import json
import sys
import urllib.request

BRIDGE = "http://127.0.0.1:49620"


def rpc(code, timeout=300, window_id=None):
    payload = {"code": code}
    if window_id:
        payload["windowId"] = window_id
    req = urllib.request.Request(
        BRIDGE + "/execute",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        body = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")))
    if not body.get("success"):
        raise RuntimeError(body.get("error") or body)
    return body.get("result")


def windows():
    with urllib.request.urlopen(BRIDGE + "/eda-windows", timeout=10) as r:
        return json.load(r)


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "return 1;"
    print(json.dumps(rpc(code), ensure_ascii=False, indent=2))

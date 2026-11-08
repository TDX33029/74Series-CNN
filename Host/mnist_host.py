"""28x28 digit sketcher for the 74-series CNN board.

Draw a digit with the mouse, the sketch is downscaled and MNIST-normalised
to a 28x28 uint8 image, sent over the serial link to the FPGA bridge
(see FPGA_Bridge/host_bridge.v), and the ten class scores come back.

Run:
    python mnist_host.py             # GUI, serial or simulator
    python mnist_host.py --sim       # start in simulator mode

The simulator (protocol.SimBoard) speaks exactly the FPGA protocol with
zeroed memories, so it exercises the GUI and the link without hardware.
"""
from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import protocol as P  # noqa: E402

try:
    import numpy as _np
except Exception:      # numpy is only needed for the fast downscale
    _np = None

CANVAS_PX = 280          # drawing area, 10x the 28x28 grid
SCALE = CANVAS_PX // 28  # 10
PREVIEW_SCALE = 4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- imaging
def blank_canvas() -> bytearray:
    return bytearray(CANVAS_PX * CANVAS_PX)


def stamp(buf: bytearray, cx: int, cy: int, radius: int) -> None:
    """Paint a filled disc (0..255) with simple clipping."""
    r2 = radius * radius
    x0, x1 = max(0, cx - radius), min(CANVAS_PX - 1, cx + radius)
    y0, y1 = max(0, cy - radius), min(CANVAS_PX - 1, cy + radius)
    for y in range(y0, y1 + 1):
        dy = y - cy
        row = y * CANVAS_PX
        for x in range(x0, x1 + 1):
            dx = x - cx
            if dx * dx + dy * dy <= r2:
                buf[row + x] = 255


def draw_segment(buf: bytearray, x0: int, y0: int, x1: int, y1: int,
                 radius: int) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / steps
        stamp(buf, int(round(x0 + (x1 - x0) * t)),
              int(round(y0 + (y1 - y0) * t)), radius)


def downscale(buf: bytearray) -> list[list[float]]:
    """10x10 box average -> 28x28 float 0..255.

    numpy path (~0.2 ms) keeps up with 30 fps; the pure-python fallback is
    ~10 ms and is only there for machines without numpy.
    """
    if _np is not None:
        a = _np.frombuffer(buf, dtype=_np.uint8)
        return a.reshape(28, SCALE, 28, SCALE).mean(axis=(1, 3)).tolist()
    out = [[0.0] * 28 for _ in range(28)]
    inv = 1.0 / (SCALE * SCALE)
    for gy in range(28):
        for gx in range(28):
            s = 0
            base_y = gy * SCALE
            base_x = gx * SCALE
            for dy in range(SCALE):
                row = (base_y + dy) * CANVAS_PX + base_x
                for dx in range(SCALE):
                    s += buf[row + dx]
            out[gy][gx] = s * inv
    return out


def _bbox(img, thresh=1.0):
    ys = [y for y in range(len(img)) if any(v >= thresh for v in img[y])]
    if not ys:
        return None
    xs = [x for x in range(len(img[0]))
          for y in ys if img[y][x] >= thresh]
    return min(xs), min(ys), max(xs), max(ys)


def _resize_bilinear(img, w, h):
    sh, sw = len(img), len(img[0])
    out = [[0.0] * w for _ in range(h)]
    for y in range(h):
        fy = (y + 0.5) * sh / h - 0.5
        y0 = max(0, min(sh - 1, int(fy)))
        y1 = max(0, min(sh - 1, y0 + 1))
        wy = fy - y0
        for x in range(w):
            fx = (x + 0.5) * sw / w - 0.5
            x0 = max(0, min(sw - 1, int(fx)))
            x1 = max(0, min(sw - 1, x0 + 1))
            wx = fx - x0
            top = img[y0][x0] * (1 - wx) + img[y0][x1] * wx
            bot = img[y1][x0] * (1 - wx) + img[y1][x1] * wx
            out[y][x] = top * (1 - wy) + bot * wy
    return out


def mnist_normalize(img, box_size=20, out_size=28):
    """Crop to ink, scale the long side to `box_size`, centre by mass.

    This mirrors the usual MNIST preprocessing: the digit occupies a 20x20
    box whose centre of mass sits in the middle of the 28x28 frame.
    """
    bb = _bbox(img)
    out = [[0.0] * out_size for _ in range(out_size)]
    if bb is None:
        return out
    x0, y0, x1, y1 = bb
    crop = [row[x0:x1 + 1] for row in img[y0:y1 + 1]]
    h, w = len(crop), len(crop[0])
    scale = box_size / max(h, w)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    small = _resize_bilinear(crop, nw, nh)
    # centre of mass of the scaled digit
    tot = sum(sum(r) for r in small) or 1.0
    cy = sum(y * v for y, r in enumerate(small) for v in r) / tot
    cx = sum(x * v for r, y in zip(small, range(nh)) for x, v in enumerate(r)) / tot
    off_y = int(round(out_size / 2.0 - 0.5 - cy))
    off_x = int(round(out_size / 2.0 - 0.5 - cx))
    for y in range(nh):
        ty = y + off_y
        if not 0 <= ty < out_size:
            continue
        for x in range(nw):
            tx = x + off_x
            if 0 <= tx < out_size:
                out[ty][tx] = small[y][x]
    return out


def to_bytes(img) -> bytes:
    return bytes(max(0, min(255, int(round(v)))) for row in img for v in row)


def preprocess(buf: bytearray, normalise: bool) -> list[list[float]]:
    img = downscale(buf)
    if normalise:
        return mnist_normalize(img)
    return img


# ------------------------------------------------------------------- app
class App:
    def __init__(self, root: tk.Tk, sim: bool = False, model_dir: str = ""):
        self.root = root
        self.model_dir = model_dir
        self.model_loaded = False
        root.title("74 系列 CNN · 手写数字识别")
        root.resizable(False, False)

        self.buf = blank_canvas()
        self.last = None
        self.link: P.Link | None = None
        self.link_kind = ""
        self.busy = False
        self.dirty = False
        self.live_var = tk.BooleanVar(value=False)
        self.temp_var = tk.DoubleVar(value=3.0)
        # fc2 logits are raw int32 accumulators; metadata gives the scale
        # that turns them back into float-like values for softmax
        self.scales = P.load_output_scales(model_dir) if model_dir else None
        # a single worker thread owns the link; the UI only queues images
        self.job_lock = threading.Lock()
        self.pending = None
        self.inflight = False
        self.res_q: queue.Queue = queue.Queue()
        self.ser_lock = threading.Lock()
        self._last_submit = 0.0
        self._last_live_log = 0.0
        self.last_logits = None
        self.last_result = 0
        threading.Thread(target=self._worker, daemon=True).start()

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="921600")
        self.sim_var = tk.BooleanVar(value=sim)
        self.norm_var = tk.BooleanVar(value=True)
        self.brush_var = tk.DoubleVar(value=1.6)
        self.status_var = tk.StringVar(value="未连接")
        self.result_var = tk.StringVar(value="—")

        self._build_ui()
        self.temp_var.trace_add("write", self._redraw_scores)
        self._refresh_preview()
        self.root.after(8, self._poll_results)
        self.root.after(12, self._live_tick)
        if sim:
            self.open_sim()

    # -- layout ---------------------------------------------------------
    def _build_ui(self):
        pad = dict(padx=6, pady=4)
        top = ttk.Frame(self.root)
        top.grid(row=0, column=0, sticky="ew", **pad)

        ttk.Label(top, text="串口").pack(side="left")
        self.port_box = ttk.Combobox(top, textvariable=self.port_var,
                                     width=12, values=self._ports())
        self.port_box.pack(side="left", padx=(4, 10))
        ttk.Label(top, text="波特率").pack(side="left")
        ttk.Combobox(top, textvariable=self.baud_var, width=8,
                     values=("115200", "57600", "230400", "460800", "921600"),
                     state="readonly").pack(side="left", padx=(4, 10))
        self.btn_open = ttk.Button(top, text="连接", command=self.toggle_link)
        self.btn_open.pack(side="left")
        self.btn_model = ttk.Button(top, text="下载模型", command=self.download_model)
        self.btn_model.pack(side="left", padx=(6, 0))
        ttk.Checkbutton(top, text="仿真模式", variable=self.sim_var,
                        command=self.toggle_sim).pack(side="left", padx=10)
        ttk.Label(top, textvariable=self.status_var,
                  foreground="#555").pack(side="right")

        body = ttk.Frame(self.root)
        body.grid(row=1, column=0, **pad)

        # drawing area
        left = ttk.Frame(body)
        left.grid(row=0, column=0, padx=(0, 10))
        self.canvas = tk.Canvas(left, width=CANVAS_PX, height=CANVAS_PX,
                                bg="#000000", highlightthickness=1,
                                highlightbackground="#888", cursor="crosshair")
        self.canvas.grid(row=0, column=0)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", lambda e: self.clear())

        ctl = ttk.Frame(left)
        ctl.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(ctl, text="清空", command=self.clear).pack(side="left")
        ttk.Label(ctl, text="笔刷").pack(side="left", padx=(10, 4))
        ttk.Scale(ctl, from_=0.6, to=3.5, variable=self.brush_var,
                  orient="horizontal", length=110).pack(side="left")
        ttk.Button(ctl, text="识别", command=self.recognise).pack(side="right")
        ttk.Label(ctl, text="显示温度").pack(side="right", padx=(10, 2))
        ttk.Spinbox(ctl, from_=1, to=10, increment=1, width=3,
                    textvariable=self.temp_var,
                    command=self._redraw_scores).pack(side="right")
        ttk.Checkbutton(ctl, text="实时", variable=self.live_var,
                        command=self._live_changed).pack(side="right", padx=10)

        # 28x28 preview
        mid = ttk.Frame(body)
        mid.grid(row=0, column=1, padx=(0, 12))
        ttk.Label(mid, text="28×28 输入").pack(anchor="w")
        size = 28 * PREVIEW_SCALE
        self.prev = tk.Canvas(mid, width=size, height=size, bg="#000000",
                              highlightthickness=1, highlightbackground="#888")
        self.prev.pack()

        # confidence bars
        right = ttk.Frame(body)
        right.grid(row=0, column=2)
        ttk.Label(right, text="置信度").pack(anchor="w")
        self.bars = []
        bar_w, bar_h = 260, 16
        for i in range(10):
            row = ttk.Frame(right)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=str(i), width=2, font=("Consolas", 10, "bold")).pack(side="left")
            c = tk.Canvas(row, width=bar_w, height=bar_h, highlightthickness=0)
            c.pack(side="left", padx=4)
            c.create_rectangle(0, 0, bar_w, bar_h, fill="#e8e8e8", width=0)
            rect = c.create_rectangle(0, 0, 0, bar_h, fill="#3b7ddd", width=0)
            pct = ttk.Label(row, text=" 0.0%", width=7)
            pct.pack(side="left")
            self.bars.append((c, rect, pct))
        self.bar_w = bar_w

        res = ttk.Frame(right)
        res.pack(fill="x", pady=(10, 0))
        ttk.Label(res, text="结果：").pack(side="left")
        ttk.Label(res, textvariable=self.result_var,
                  font=("Segoe UI", 18, "bold"),
                  foreground="#c0392b").pack(side="left")

        self.log = tk.Text(self.root, height=6, width=96, state="disabled",
                           font=("Consolas", 9))
        self.log.grid(row=2, column=0, sticky="ew", **pad)
        self.log.tag_configure("err", foreground="#c0392b")

        self.root.bind("<Control-Return>", lambda e: self.recognise())
        self.root.bind("<Escape>", lambda e: self.clear())

    @staticmethod
    def _ports():
        try:
            from serial.tools import list_ports
        except Exception:
            return ()
        return tuple(p.device for p in list_ports.comports())

    def say(self, msg: str, err: bool = False):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("[%H:%M:%S] ") + msg + "\n",
                        ("err",) if err else ())
        self.log.see("end")
        self.log.configure(state="disabled")

    # -- drawing --------------------------------------------------------
    def on_press(self, e):
        self.last = (e.x, e.y)
        r = max(2, int(round(self.brush_var.get() * SCALE / 2)))
        stamp(self.buf, e.x, e.y, r)
        self.dirty = True
        self._refresh_preview()

    def on_drag(self, e):
        if self.last is None:
            self.last = (e.x, e.y)
        r = max(2, int(round(self.brush_var.get() * SCALE / 2)))
        draw_segment(self.buf, self.last[0], self.last[1], e.x, e.y, r)
        self.last = (e.x, e.y)
        self.dirty = True
        self._refresh_preview()

    def on_release(self, _e):
        self.last = None
        self.dirty = True
        self._refresh_preview()

    def clear(self):
        self.buf = blank_canvas()
        self.canvas.delete("all")
        self.dirty = True
        self._refresh_preview()
        self.result_var.set("—")

    def _refresh_preview(self):
        img = downscale(self.buf)
        self.prev.delete("all")
        s = PREVIEW_SCALE
        for y in range(28):
            for x in range(28):
                v = int(max(0, min(255, img[y][x])))
                if v:
                    self.prev.create_rectangle(x * s, y * s, (x + 1) * s,
                                               (y + 1) * s,
                                               fill=f"#{v:02x}{v:02x}{v:02x}",
                                               width=0)

    # -- link -----------------------------------------------------------
    def toggle_link(self):
        if self.link:
            self.close_link()
        else:
            self.open_link()

    def open_link(self):
        if self.sim_var.get():
            self.open_sim()
            return
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("串口", "先选择串口号")
            return
        try:
            self.link = P.SerialLink(port, int(self.baud_var.get()))
        except Exception as exc:
            messagebox.showerror("串口", f"打不开 {port}：\n{exc}")
            return
        self.link_kind = f"串口 {port} @ {self.baud_var.get()}"
        self.status_var.set("已连接 · " + self.link_kind)
        self.btn_open.configure(text="断开")
        try:
            with self.ser_lock:
                st, data = self.link.request(P.CMD_PING, timeout=1.5)
            if st == P.ST_OK:
                name = data.decode(errors="replace")
                self.say(f"在线：{name}")
                if name.startswith("CNN28"):
                    self.download_model()
            else:
                self.say(f"PING 返回 {P.STATUS_TEXT.get(st, st)}", err=True)
        except Exception as exc:
            self.say(f"PING 失败：{type(exc).__name__}: {exc}", err=True)

    def open_sim(self):
        self.sim_var.set(True)
        self.link = P.SimBoard(self.model_dir or None)
        self.link_kind = "仿真"
        self.btn_open.configure(text="断开")
        if self.link.model is not None:
            self.status_var.set("已连接 · 仿真模式（整数模型）")
            self.say("仿真模式：使用 weights/x28 的整数模型，与 FPGA 位精确一致。")
        else:
            self.status_var.set("已连接 · 仿真模式（无模型）")
            self.say(f"仿真模式：模型未加载（{self.link.model_error or '未找到'}），"
                     "分数全为 0。")

    def download_model(self):
        if self.link is None:
            messagebox.showinfo("未连接", "请先连接，或勾选“仿真模式”。")
            return
        if isinstance(self.link, P.SimBoard):
            self.say("仿真模式不需要下载模型。")
            return
        if not self.model_dir:
            messagebox.showwarning("模型", "未指定模型目录（--model）")
            return
        self.status_var.set("正在下载模型…")
        self.root.update_idletasks()
        try:
            with self.ser_lock:
                n = self.link.load_model(self.model_dir)
        except Exception as exc:
            self.say(f"模型下载失败：{exc}", err=True)
            self.status_var.set("模型下载失败")
            return
        self.model_loaded = True
        self.say(f"模型已下载：{n} 字节（{self.model_dir}）")
        self.status_var.set(f"就绪 · {self.link_kind} · 模型已加载")

    def close_link(self):
        if isinstance(self.link, P.SerialLink):
            self.link.close()
        self.link = None
        self.link_kind = ""
        self.status_var.set("未连接")
        self.btn_open.configure(text="连接")

    def toggle_sim(self):
        if self.sim_var.get():
            self.close_link()
            self.open_sim()
        else:
            if isinstance(self.link, P.SimBoard):
                self.close_link()

    # -- inference ------------------------------------------------------
    def recognise(self):
        """Button / Ctrl+Enter: queue the current drawing."""
        self._submit(verbose=True)

    def _submit(self, verbose: bool) -> None:
        if self.link is None:
            if verbose:
                messagebox.showinfo("未连接", "请先连接串口，或勾选“仿真模式”。")
            return
        img = preprocess(self.buf, self.norm_var.get())
        data = to_bytes(img)
        if not any(data):
            if verbose:
                messagebox.showinfo("空白", "画布是空的，先画一个数字。")
            else:
                self._clear_scores()
            return
        with self.job_lock:
            self.pending = (data, verbose)   # newest frame wins
            self.busy = True
        self.status_var.set("识别中…")

    # -- worker (owns the serial link) ----------------------------------
    def _worker(self) -> None:
        while True:
            with self.job_lock:
                job, self.pending = self.pending, None
                if job is not None:
                    self.inflight = True
            if job is None:
                time.sleep(0.003)
                continue
            data, verbose = job
            t0 = time.monotonic()
            try:
                with self.ser_lock:
                    link = self.link
                    st, _ack = link.request(P.CMD_LOAD_IMAGE, data, timeout=10)
                    if st != P.ST_OK:
                        raise RuntimeError(
                            f"加载图像失败：{P.STATUS_TEXT.get(st, st)}")
                    st, payload = link.request(P.CMD_INFER, timeout=15)
                    if st != P.ST_OK:
                        raise RuntimeError(
                            f"推理失败：{P.STATUS_TEXT.get(st, st)}")
                logits, result, errcode, flags = P.decode_scores(payload)
                dt = (time.monotonic() - t0) * 1000.0
                self.res_q.put((logits, result, errcode, flags, dt,
                                verbose, None))
            except Exception as exc:            # report, keep the UI alive
                self.res_q.put((None, None, None, None, 0.0, verbose, exc))
            finally:
                with self.job_lock:
                    self.inflight = False
                    self.busy = False

    def _poll_results(self) -> None:
        try:
            while True:
                self._on_result(self.res_q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(8, self._poll_results)

    def _on_result(self, item) -> None:
        logits, result, errcode, flags, dt, verbose, exc = item
        if exc is not None:
            self.say(f"推理失败：{type(exc).__name__}: {exc}", err=True)
            self.status_var.set("错误")
            return
        self.last_logits, self.last_result = logits, result
        probs, true_p = self._probabilities(logits, result)
        self._show_scores(probs, logits, result)
        note = ""
        if not flags & 0x04:
            note = "（未收到 DONE）"
        if flags & 0x02:
            note += f" 板卡 ERROR，错误码 {errcode}"
        tail = f"真实置信度 {true_p * 100:.2f}%"
        if verbose:
            self.say(f"推理完成 {dt:.0f} ms，结果 {result}，{tail}{note}")
            self.status_var.set(f"就绪 · {self.link_kind}")
        else:
            now = time.monotonic()
            if now - self._last_live_log > 1.0:
                self._last_live_log = now
                self.say(f"实时 {dt:.0f} ms/帧，结果 {result}，{tail}{note}")
            self.status_var.set(f"实时 · {dt:.0f} ms/帧 · {tail}")

    def _probabilities(self, logits, result):
        """Dequantize the int32 logits, then softmax at the display temperature."""
        if self.scales:
            z = [logits[i] * self.scales[i] for i in range(10)]
        else:
            z = [v / 2000.0 for v in logits]
        try:
            temp = float(self.temp_var.get())
        except Exception:
            temp = 1.0
        probs = P.softmax(z, max(1.0, temp))
        true_p = P.softmax(z)[result] if 0 <= result < 10 else 0.0
        return probs, true_p

    def _redraw_scores(self, *_args) -> None:
        """Temperature changed: re-render from the last logits, no inference."""
        if self.last_logits is not None:
            probs, _ = self._probabilities(self.last_logits, self.last_result)
            self._show_scores(probs, self.last_logits, self.last_result)

    def _clear_scores(self) -> None:
        for c, rect, pct in self.bars:
            c.coords(rect, 0, 0, 0, 16)
            pct.configure(text="  0.00%")
        self.result_var.set("—")

    # -- live drawing mode ----------------------------------------------
    def _live_changed(self) -> None:
        if self.live_var.get():
            self.dirty = True
            self.say("实时模式：绘制过程中持续发送当前画面（链路够快时可到 30 帧/秒）。")
        else:
            self.dirty = False
            self.status_var.set(f"就绪 · {self.link_kind}".rstrip(" ·"))

    def _live_tick(self) -> None:
        if (self.live_var.get() and self.dirty and self.link is not None
                and time.monotonic() - self._last_submit >= 1.0 / 50.0):
            with self.job_lock:
                idle = self.pending is None and not self.inflight
            if idle:
                self._last_submit = time.monotonic()
                self.dirty = False
                self._submit(verbose=False)
        self.root.after(12, self._live_tick)

    def _show_scores(self, probs, logits, result):
        for i, (c, rect, pct) in enumerate(self.bars):
            w = int(round(probs[i] * self.bar_w))
            c.coords(rect, 0, 0, max(0, w), 16)
            c.itemconfigure(rect, fill="#3b7ddd" if i != result else "#c0392b")
            pct.configure(text=f"{probs[i] * 100:6.2f}%")
        self.result_var.set(str(result))
        if not any(logits):
            self.say("提示：10 个 logit 全为 0 —— 板卡 EEPROM 里还没有权重，"
                     "此时置信度必然均匀分布。")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sim", action="store_true", help="直接以仿真模式启动")
    ap.add_argument("--model", default=os.path.join(ROOT, "weights", "x28"),
                    help="weights/x28 目录（默认 ../weights/x28）")
    args = ap.parse_args()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.25)
    except Exception:
        pass
    App(root, sim=args.sim, model_dir=args.model)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

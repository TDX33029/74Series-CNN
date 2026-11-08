"""Wire protocol for the 74-series CNN host link.

The same framing is implemented on the FPGA side (see FPGA_Bridge/host_bridge.v):

    host -> FPGA : A5 5A | CMD | LEN_L LEN_H | PAYLOAD... | CRC_L CRC_H
    FPGA -> host : 5A A5 | STAT | LEN_L LEN_H | PAYLOAD... | CRC_L CRC_H

CRC is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, MSB first) over
CMD/STAT + length + payload (the two SOF bytes are not covered).

Memory regions (MEM_SEL) come straight from S04's 74HC138 decoders:

    0  IMAGE    28x28 uint8 image            (6264, 784 bytes used)
    1  C1OUT    2  P1OUT    3  C2OUT    4  P2OUT
    5  FC1OUT   6  FC2LOG   10 x int32 LE logits  (argmax input)
    8..11    W_CONV1 / W_CONV2 / W_FC1 / W_FC2
    12..15   B_CONV1 / B_CONV2 / B_FC1 / B_FC2

The FPGA bridge only loads the image region and reads the score region;
EEPROM (weight/bias) regions must be programmed offline because a 28C256
byte write takes milliseconds.
"""
from __future__ import annotations

import struct
import time

SOF_HOST = b"\xA5\x5A"
SOF_FPGA = b"\x5A\xA5"

CMD_PING = 0x01
CMD_LOAD_IMAGE = 0x02
CMD_INFER = 0x03
CMD_READ_SCORES = 0x04
CMD_RESET = 0x05
CMD_STATUS = 0x06
CMD_LOAD_MEM = 0x07
CMD_READ_MEM = 0x08

ST_OK = 0
ST_BAD_CRC = 1
ST_BAD_LEN = 2
ST_BAD_CMD = 3
ST_TIMEOUT = 4
ST_BOARD_ERR = 5
ST_BAD_ARG = 6

STATUS_TEXT = {
    ST_OK: "OK",
    ST_BAD_CRC: "CRC 错误",
    ST_BAD_LEN: "长度错误",
    ST_BAD_CMD: "不支持的命令",
    ST_TIMEOUT: "板卡超时",
    ST_BOARD_ERR: "板卡报错",
    ST_BAD_ARG: "参数错误",
}

# Memory region numbers.
# The 74-series bridge uses MEM_SEL 0 IMAGE / 6 FC2LOG / 8..15 weights.
# The FPGA CNN uses the sel map below (see FPGA_CNN/rtl/cnn28_top.v).
SEL_IMAGE = 0
SEL_SCORES = 6
IMAGE_BYTES = 28 * 28
SCORE_BYTES = 10 * 4

FPGA_SEL = {
    "image": 0,
    "conv1_weight": 1,
    "conv2_weight": 2,
    "fc1_weight": 3,
    "fc2_weight": 4,
    "bias": 5,
    "logits": 6,
    "qparams": 7,
}
FPGA_SEL_SIZE = {
    0: 784, 1: 200, 2: 1152, 3: 12800,
    4: 320, 5: 264, 6: 40, 7: 1056,
}


def crc16(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_frame(code: int, payload: bytes = b"",
                sof: bytes = SOF_HOST) -> bytes:
    """Build a frame. `code` is CMD on the host side, STAT on the FPGA side."""
    body = bytes([code]) + struct.pack("<H", len(payload)) + bytes(payload)
    return sof + body + struct.pack("<H", crc16(body))


class FrameError(Exception):
    pass


class FrameParser:
    """Incremental parser for one direction of the link."""

    def __init__(self, sof: bytes = SOF_FPGA, max_payload: int = 2048):
        self.sof = sof
        self.max_payload = max_payload
        self.buf = bytearray()
        self.crc_errors = 0

    def feed(self, data: bytes):
        """Yield (code, payload) tuples; code is the status/cmd byte."""
        self.buf += data
        while True:
            i = self.buf.find(self.sof)
            if i < 0:
                # keep at most one byte in case SOF is split across reads
                if len(self.buf) > 1:
                    del self.buf[:-1]
                return
            if i:
                del self.buf[:i]
            if len(self.buf) < 5:
                return
            code = self.buf[2]
            length = self.buf[3] | (self.buf[4] << 8)
            if length > self.max_payload:
                self.crc_errors += 1
                del self.buf[:2]
                continue
            total = 7 + length          # SOF(2)+CMD(1)+LEN(2)+payload+CRC(2)
            if len(self.buf) < total:
                return
            body = bytes(self.buf[2:5 + length])
            want = self.buf[5 + length] | (self.buf[6 + length] << 8)
            payload = bytes(self.buf[5:5 + length])
            del self.buf[:total]
            if crc16(body) != want:
                self.crc_errors += 1
                yield (ST_BAD_CRC, b"")
                continue
            yield (code, payload)


class Link:
    """Request/response wrapper over a byte transport."""

    def __init__(self, write, read, timeout=5.0):
        self._write = write
        self._read = read
        self.timeout = timeout
        self.parser = FrameParser()

    def request(self, cmd: int, payload: bytes = b"",
                timeout: float | None = None) -> tuple[int, bytes]:
        self._write(build_frame(cmd, payload))
        deadline = time.monotonic() + (self.timeout if timeout is None
                                       else timeout)
        while time.monotonic() < deadline:
            chunk = self._read(0.05)
            if not chunk:
                continue
            for stat, data in self.parser.feed(chunk):
                return stat, data
        raise TimeoutError(f"命令 0x{cmd:02X} 超时")


    def load_model(self, model_dir: str, chunk: int = 500) -> int:
        """Download weights/x28 into the FPGA (LOAD_MEM frames)."""
        total = 0
        for sel, data in model_blocks(model_dir):
            for off in range(0, len(data), chunk):
                part = data[off:off + chunk]
                payload = (bytes([sel, off & 0xFF, (off >> 8) & 0xFF,
                                  len(part) & 0xFF, (len(part) >> 8) & 0xFF])
                           + part)
                st, _ = self.request(CMD_LOAD_MEM, payload, timeout=10)
                if st != ST_OK:
                    raise RuntimeError(
                        f"下载模型失败 sel={sel} off={off}: "
                        f"{STATUS_TEXT.get(st, st)}")
                total += len(part)
        return total


def pyserial_read(ser, _timeout=None):
    """Adapter between Link.request's timeout argument and pyserial.

    ``Link.request`` calls its read function as ``read(0.05)`` meaning
    "wait up to 50 ms".  pyserial's ``read(n)`` takes a *byte count*, so
    forwarding 0.05 verbatim makes ctypes raise ``TypeError: 0.05``.
    Read everything that is already buffered instead; the 50 ms wait comes
    from the port's own ``timeout`` setting.
    """
    n = getattr(ser, "in_waiting", 0) or 1
    return ser.read(n)


class SerialLink(Link):
    """pyserial backend (imported lazily so the app still runs without it)."""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 5.0):
        import serial  # noqa: WPS433  (optional dependency)

        self.ser = serial.Serial(port, baud, timeout=0.05, write_timeout=2.0)
        super().__init__(self.ser.write, lambda _t: pyserial_read(self.ser),
                         timeout)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class SimBoard(Link):
    """In-process stand-in for the FPGA CNN.

    Speaks the same framed protocol and executes the same integer model
    when ``model_dir`` points at a weights/x28 export (numpy only); with
    no model it returns zeros, like an FPGA whose memories were never
    programmed.
    """

    VERSION = b"CNN28-FPGA"

    def __init__(self, model_dir: str | None = None):
        super().__init__(self._write, self._read, timeout=5.0)
        self.rx = bytearray()
        self.tx = bytearray()
        self.mem = {sel: bytearray(size) for sel, size in FPGA_SEL_SIZE.items()}
        self.result = 0
        self.error_code = 0
        self.busy = False
        self.last_infer = 0.0
        self.model = None
        self.model_error = ""
        if model_dir:
            try:
                import model28
                self.model = model28.load_model(model_dir)
            except Exception as exc:            # report, do not crash the GUI
                self.model_error = str(exc)

    # -- Link interface ---------------------------------------------------
    def _write(self, data: bytes):
        self.rx += data

    def _read(self, _timeout):
        self._pump()
        out = bytes(self.tx)
        self.tx.clear()
        return out

    # -- board emulation --------------------------------------------------
    def _pump(self):
        while True:
            i = self.rx.find(SOF_HOST)
            if i < 0:
                if len(self.rx) > 1:
                    del self.rx[:-1]
                return
            if i:
                del self.rx[:i]
            if len(self.rx) < 5:
                return
            length = self.rx[3] | (self.rx[4] << 8)
            total = 7 + length
            if len(self.rx) < total:
                return
            cmd = self.rx[2]
            payload = bytes(self.rx[5:5 + length])
            body = bytes(self.rx[2:5 + length])
            want = self.rx[5 + length] | (self.rx[6 + length] << 8)
            del self.rx[:total]
            if crc16(body) != want:
                self._reply(ST_BAD_CRC, b"")
                continue
            self._exec(cmd, payload)

    def _reply(self, stat, payload):
        self.tx += build_frame(stat, payload, SOF_FPGA)

    def _exec(self, cmd, payload):
        if cmd == CMD_PING:
            self._reply(ST_OK, self.VERSION)
        elif cmd == CMD_LOAD_IMAGE:
            if len(payload) != IMAGE_BYTES:
                self._reply(ST_BAD_LEN, b"")
                return
            self.mem[0][:IMAGE_BYTES] = payload
            self._reply(ST_OK, b"")
        elif cmd == CMD_INFER:
            self.last_infer = time.monotonic()
            logits = bytes(SCORE_BYTES)
            if self.model is not None:
                try:
                    import numpy as np
                    import model28
                    img = np.frombuffer(bytes(self.mem[0][:IMAGE_BYTES]),
                                        np.uint8).reshape(28, 28)
                    out = model28.infer(img, self.model)
                    logits = out.astype("<i4").tobytes()
                    self.result = int(out.argmax())
                    self.error_code = 0
                except Exception as exc:
                    self.error_code = 1
                    self.last_error = str(exc)
            else:
                self.result = 0
                self.error_code = 0
            self.mem[SEL_SCORES][:SCORE_BYTES] = logits
            self._reply(ST_OK, logits + bytes([self.result, self.error_code, 0x05]))
        elif cmd == CMD_READ_SCORES:
            self._reply(ST_OK, bytes(self.mem[SEL_SCORES][:SCORE_BYTES]))
        elif cmd == CMD_RESET:
            self.result = 0
            self.error_code = 0
            self._reply(ST_OK, b"")
        elif cmd == CMD_STATUS:
            flags = (1 if self.busy else 0) | 0x02 | 0x04
            self._reply(ST_OK, bytes([flags, self.result, self.error_code]))
        elif cmd == CMD_LOAD_MEM:
            if len(payload) < 5:
                self._reply(ST_BAD_LEN, b"")
                return
            sel = payload[0]
            addr = payload[1] | (payload[2] << 8)
            n = payload[3] | (payload[4] << 8)
            data = payload[5:]
            if (n != len(data) or sel not in self.mem or sel == SEL_SCORES
                    or addr + n > FPGA_SEL_SIZE[sel]):
                self._reply(ST_BAD_ARG, b"")
                return
            self.mem[sel][addr:addr + n] = data
            self._reply(ST_OK, b"")
        elif cmd == CMD_READ_MEM:
            if len(payload) != 5:
                self._reply(ST_BAD_LEN, b"")
                return
            sel = payload[0]
            addr = payload[1] | (payload[2] << 8)
            n = payload[3] | (payload[4] << 8)
            if (sel not in self.mem or n > 64
                    or addr + n > FPGA_SEL_SIZE[sel]):
                self._reply(ST_BAD_ARG, b"")   # RTL reply buffer is 64 bytes
                return
            self._reply(ST_OK, bytes(self.mem[sel][addr:addr + n]))
        else:
            self._reply(ST_BAD_CMD, b"")


def model_blocks(model_dir: str):
    """Split weights/x28/model.bin into (sel, bytes) blocks for download."""
    import json
    import os

    with open(os.path.join(model_dir, "metadata.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(model_dir, "model.bin"), "rb") as f:
        blob = f.read()
    off = meta["sections"]

    def sec(name):
        start = off[name]
        ends = [v for v in off.values() if v > start]
        end = min(ends) if ends else len(blob)
        return blob[start:end]

    bias = (sec("conv1_bias") + sec("conv2_bias")
            + sec("fc1_bias") + sec("fc2_bias"))
    return [
        (FPGA_SEL["conv1_weight"], sec("conv1_weight")),
        (FPGA_SEL["conv2_weight"], sec("conv2_weight")),
        (FPGA_SEL["fc1_weight"], sec("fc1_weight")),
        (FPGA_SEL["fc2_weight"], sec("fc2_weight")),
        (FPGA_SEL["bias"], bias),
        (FPGA_SEL["qparams"], sec("qparams")),
    ]


def decode_scores(payload: bytes):
    """Return (logits[10], result, error_code, flags) from an INFER reply."""
    if len(payload) < SCORE_BYTES + 3:
        raise ValueError("INFER 响应长度不足")
    raw = payload[:SCORE_BYTES]
    logits = list(struct.unpack("<10i", raw))
    result, error_code, flags = payload[SCORE_BYTES:SCORE_BYTES + 3]
    return logits, result, error_code, flags


def softmax(logits, temperature: float = 1.0):
    """Softmax with an optional temperature (display only).

    The fc2 logits are raw int32 accumulators (tens of thousands apart), so
    exp() underflows to exactly 0 for every non-winner.  Dequantize first
    (see load_output_scales) and/or raise the temperature to see a spread.
    """
    if not logits:
        return []
    t = temperature if temperature > 0 else 1.0
    z = [v / t for v in logits]
    m = max(z)
    ex = [pow(2.718281828459045, v - m) for v in z]
    s = sum(ex) or 1.0
    return [v / s for v in ex]


def load_output_scales(model_dir: str):
    """Per-class scale turning the int32 fc2 logits back into float units.

    float_logit[c] ~= logit[c] * fc2.scale_in * fc2.s_w[c]
    Returns None when metadata.json is unavailable.
    """
    import json
    import os
    try:
        with open(os.path.join(model_dir, "metadata.json"),
                  encoding="utf-8") as f:
            meta = json.load(f)
        lay = meta["layers"]["fc2"]
        s_in = float(lay["scale_in"])
        return [s_in * float(w) for w in lay["s_w"]]
    except Exception:
        return None

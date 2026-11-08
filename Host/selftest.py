"""Smoke test for the host side (no hardware, no GUI window).

    python selftest.py

Exercises the CRC/framing, the simulator transport, and the 28x28
preprocessing pipeline.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import protocol as P
import mnist_host as H


def test_crc() -> None:
    assert P.crc16(b"123456789") == 0x29B1
    print("crc16 CCITT-FALSE vector OK")


def test_frames() -> None:
    frame = P.build_frame(P.CMD_PING, b"MNIST74\x01")
    assert frame[:2] == b"\xA5\x5A"
    parser = P.FrameParser(P.SOF_HOST)
    assert list(parser.feed(frame)) == [(P.CMD_PING, b"MNIST74\x01")]
    # byte-at-a-time feed must produce the same result
    parser = P.FrameParser(P.SOF_HOST)
    got = []
    for b in frame:
        got += list(parser.feed(bytes([b])))
    assert got == [(P.CMD_PING, b"MNIST74\x01")]
    # corrupt one payload byte -> parser flags a CRC error, not a frame
    bad = bytearray(frame)
    bad[6] ^= 0xFF
    parser = P.FrameParser(P.SOF_HOST)
    assert list(parser.feed(bytes(bad))) == [(P.ST_BAD_CRC, b"")]
    assert parser.crc_errors == 1
    # the app's parser accepts the FPGA direction by default
    reply = P.build_frame(P.ST_OK, b"\x01", P.SOF_FPGA)
    assert list(P.FrameParser().feed(reply)) == [(P.ST_OK, b"\x01")]
    print("frame build/parse/CRC-reject OK")


def test_sim_board() -> None:
    board = P.SimBoard()
    st, ver = board.request(P.CMD_PING)
    assert st == P.ST_OK and ver == b"CNN28-FPGA"
    img = bytes([7] * P.IMAGE_BYTES)
    st, ack = board.request(P.CMD_LOAD_IMAGE, img)
    assert st == P.ST_OK and ack == b"\x01"
    assert bytes(board.mem[P.SEL_IMAGE][:P.IMAGE_BYTES]) == img
    st, payload = board.request(P.CMD_INFER)
    logits, result, errcode, flags = P.decode_scores(payload)
    assert st == P.ST_OK and len(logits) == 10 and result == 0
    assert flags & 0x01 and flags & 0x04
    assert len(board.request(P.CMD_READ_SCORES)[1]) == P.SCORE_BYTES
    # wrong image length must be rejected, and must not disturb the link
    st, _ = board.request(P.CMD_LOAD_IMAGE, b"\x00" * 100)
    assert st == P.ST_BAD_LEN
    assert board.request(P.CMD_PING)[0] == P.ST_OK
    print("SimBoard LOAD_IMAGE/INFER/READ_SCORES OK")


def test_imaging() -> None:
    buf = H.blank_canvas()
    # crude upright "1"
    H.draw_segment(buf, 180, 40, 140, 70, 8)
    H.draw_segment(buf, 140, 70, 140, 240, 8)
    H.draw_segment(buf, 110, 240, 175, 240, 8)
    img = H.downscale(buf)
    assert max(max(r) for r in img) > 0
    assert len(img) == 28 and len(img[0]) == 28

    norm = H.mnist_normalize(img)
    bb = H._bbox(norm)
    assert bb is not None
    x0, y0, x1, y1 = bb
    assert max(x1 - x0, y1 - y0) + 1 == 20, (bb, "digit must fill 20 px")

    tot = sum(sum(r) for r in norm) or 1.0
    cy = sum(y * v for y, r in enumerate(norm) for v in r) / tot
    cx = sum(x * v for r in norm for x, v in enumerate(r)) / tot
    assert abs(cx - 13.5) <= 1.5 and abs(cy - 13.5) <= 1.5, (cx, cy)

    data = H.to_bytes(norm)
    assert len(data) == P.IMAGE_BYTES
    # two bilinear resamplings cost a little contrast; ink must stay strong
    assert max(data) > 200, max(data)
    print(f"preprocess OK (bbox 20 px, centre of mass {cx:.1f},{cy:.1f})")


def test_model28() -> None:
    """Host golden model must reproduce the exported vectors exactly."""
    import numpy as np
    import model28

    mdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "weights", "x28")
    if not os.path.isdir(mdir):
        print("model28: export not found, skipped")
        return
    model = model28.load_model(mdir)
    for k in range(8):
        img = np.array([int(s, 16) for s in
                        open(os.path.join(mdir, "vectors", f"img_{k}.hex"))],
                       np.uint8).reshape(28, 28)
        exp = np.array([int(s, 16) for s in
                        open(os.path.join(mdir, "vectors", f"logit_{k}.hex"))],
                       np.int64)
        exp = np.where(exp >= 2 ** 31, exp - 2 ** 32, exp)
        got = model28.infer(img, model)
        assert np.array_equal(got, exp), (k, got, exp)
    print("model28 matches the exported RTL vectors (8/8)")

    # the simulator must now classify, not return zeros
    board = P.SimBoard(mdir)
    img0 = bytes([int(s, 16) for s in
                  open(os.path.join(mdir, "vectors", "img_0.hex"))])
    assert board.request(P.CMD_LOAD_IMAGE, img0)[0] == P.ST_OK
    st, payload = board.request(P.CMD_INFER)
    logits, result, errcode, flags = P.decode_scores(payload)
    assert st == P.ST_OK and result == 0 and logits[0] == 23614, (result, logits)


def test_softmax() -> None:
    p = P.softmax([0] * 10)
    assert abs(sum(p) - 1.0) < 1e-9 and max(p) - min(p) < 1e-9
    p = P.softmax([0, 10, 0, 0, 0, 0, 0, 0, 0, 0])
    assert abs(p[1] - 0.9999) < 1e-3
    print("softmax OK")


def test_confidence_display() -> None:
    """Raw int32 logits must not collapse to 0/100 in the UI."""
    model = os.path.join(H.ROOT, "weights", "x28")
    if not os.path.isdir(model):
        print("confidence display SKIP (no weights/x28)")
        return
    scales = P.load_output_scales(model)
    assert scales and len(scales) == 10 and min(scales) > 0
    logits = [23614, -28969, 1800, -10847, -11950, -2404, 8509, -10876,
              -2299, -258]
    z = [logits[i] * scales[i] for i in range(10)]
    # true distribution is essentially one-hot
    true_p = P.softmax(z)[0]
    assert true_p > 0.99, true_p
    # at display temperature 3 the runner-ups are visible
    disp = P.softmax(z, 3.0)
    assert 0.5 < disp[0] < 1.0 and disp[6] > 0.01, disp
    print("confidence display OK (true %.2f%%, T=3 top %.1f%%)"
          % (true_p * 100, disp[0] * 100))


def test_serial_read_adapter() -> None:
    """Link.request passes a timeout; pyserial.read takes a byte count."""
    class FakeSer:
        def __init__(self, data: bytes):
            self.buf = bytearray(data)
            self.read_sizes = []

        @property
        def in_waiting(self):
            return len(self.buf)

        def read(self, n):
            self.read_sizes.append(n)
            out = bytes(self.buf[:n])
            del self.buf[:n]
            return out

    ser = FakeSer(b"ABCDE")
    # the exact call Link.request makes: read(0.05) must not reach pyserial
    data = P.pyserial_read(ser, 0.05)
    assert data == b"ABCDE", data
    assert ser.read_sizes == [5], ser.read_sizes

    empty = FakeSer(b"")
    assert P.pyserial_read(empty, 0.05) == b""   # times out like a real port
    assert empty.read_sizes == [1], empty.read_sizes
    print("pyserial read adapter OK")


if __name__ == "__main__":
    test_crc()
    test_frames()
    test_sim_board()
    test_imaging()
    test_model28()
    test_softmax()
    test_confidence_display()
    test_serial_read_adapter()
    print("SELFTEST PASS")

"""Set the board pins for the CNN bitstream and rebuild.

    python set_pins.py --clk E1 --rx R1 --tx T1 [--rst M2] [--led P9]
    python set_pins.py --show

The assignments are written into cnn28.qsf between the two marker lines so
they survive repeated edits, then `quartus_sh --flow compile cnn28` runs.
Without a --rst the reset pin is left unused and the internal weak pull-up
keeps the design out of reset.

Pin names are the FPGA package pins printed in the board schematic
(EP4CE10F17C8N: A1..T16).  Run with --show to see what is currently set.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QSF = HERE / "cnn28.qsf"
BEGIN = "# --- board pins (set_pins.py) ---"
END = "# --- end board pins ---"

SIGNALS = [
    ("clk", "50 MHz clock"),
    ("rst_n", "reset, active low (optional)"),
    ("uart_rx", "USB-UART TX -> FPGA"),
    ("uart_tx", "FPGA -> USB-UART RX"),
    ("led", "heartbeat (optional)"),
]


def current_block() -> str:
    text = QSF.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.S)
    return m.group(1).strip() if m else ""


def show() -> int:
    block = current_block()
    print("current board pins:")
    print(block if block else "  (none - the fitter picks arbitrary pins)")
    return 0


def write_block(pins: dict[str, str], baud: int | None = None) -> None:
    lines = [BEGIN]
    for sig, _ in SIGNALS:
        if sig in pins:
            lines.append(f"set_location_assignment PIN_{pins[sig]} -to {sig}")
    if "rst_n" not in pins:
        # no reset pin: the design generates its own power-on reset
        lines.append('set_global_assignment -name VERILOG_MACRO "NO_EXT_RESET=1"')
    if baud:
        lines.append(f"set_parameter -name BAUD {baud}")
    if "led" in pins:
        # the port only exists when the macro is defined
        lines.append('set_global_assignment -name VERILOG_MACRO "LED_HEARTBEAT=1"')
    lines.append(END)
    block = "\n".join(lines)

    text = QSF.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, text,
                      flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    QSF.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clk", help="50 MHz clock pin, e.g. E1")
    ap.add_argument("--rx", help="FPGA uart_rx pin (from the USB-UART TX)")
    ap.add_argument("--tx", help="FPGA uart_tx pin (to the USB-UART RX)")
    ap.add_argument("--rst", help="reset pin, active low (optional)")
    ap.add_argument("--led", help="heartbeat LED pin (optional)")
    ap.add_argument("--baud", type=int,
                    help="UART baud the bitstream is built for (default 115200)")
    ap.add_argument("--show", action="store_true", help="print the current pins")
    ap.add_argument("--no-build", action="store_true", help="only edit the qsf")
    args = ap.parse_args()

    if args.show:
        return show()

    pins = {}
    for name, val in (("clk", args.clk), ("rst_n", args.rst),
                      ("uart_rx", args.rx), ("uart_tx", args.tx),
                      ("led", args.led)):
        if val:
            pin = val.upper().lstrip("PIN_")
            if not re.fullmatch(r"[A-T]\d{1,2}", pin):
                print(f"error: '{val}' does not look like an F17 package pin",
                      file=sys.stderr)
                return 2
            pins[name] = pin

    if not pins:
        ap.print_help()
        return 2

    for required in ("clk", "uart_rx", "uart_tx"):
        if required not in pins:
            print(f"warning: no --{required} given; the fitter will place it "
                  f"arbitrarily", file=sys.stderr)

    write_block(pins, args.baud)
    msg = ", ".join(f"{k}=PIN_{v}" for k, v in pins.items())
    if args.baud:
        msg += f", BAUD={args.baud}"
    print("wrote:", msg)
    if args.no_build:
        return 0

    print("compiling...")
    quartus = "quartus_sh"
    try:
        subprocess.run([quartus, "--flow", "compile", "cnn28"], cwd=HERE,
                       check=True)
    except FileNotFoundError:
        print("quartus_sh not on PATH; add "
              "C:/intelFPGA/18.0/quartus/bin64 and rerun, or run it manually.",
              file=sys.stderr)
        return 3
    except subprocess.CalledProcessError as exc:
        print(f"compile failed (exit {exc.returncode})", file=sys.stderr)
        return exc.returncode
    print("done: quartus/cnn28.sof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

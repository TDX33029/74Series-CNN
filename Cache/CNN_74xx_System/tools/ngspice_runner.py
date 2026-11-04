"""Drive KiCad's bundled ngspice.dll from Python (shared-library API).

This gives us a scriptable SPICE engine without needing a separate
ngspice.exe.  It is the same ngspice build that KiCad's simulator uses.
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_int, c_void_p

DLL_PATH = r"C:/Program Files/KiCad/10.0/bin/ngspice.dll"
LIB_DIR = r"C:/Program Files/KiCad/10.0/lib/ngspice"
CM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "ngspice")


class NgSpice:
    def __init__(self, dll_path: str = DLL_PATH, lib_dir: str = LIB_DIR):
        # ngspice's code models are loaded relative to this directory.
        os.environ.setdefault("SPICE_LIB_DIR", lib_dir)
        os.environ.setdefault("NGSPICE_LIB_DIR", lib_dir)
        os.environ.setdefault("PATH", lib_dir + os.pathsep + os.environ.get("PATH", ""))
        self.lib = ctypes.CDLL(dll_path)
        self._out = []
        self._err = []
        self._data = []
        self._init_callbacks()
        self.lib.ngSpice_Init(
            self._send_char,
            self._send_stat,
            self._controlled_exit,
            self._send_data,
            self._send_init_data,
            self._bg_thread_running,
            None,
        )
        # Load the XSPICE code-model libraries shipped with KiCad.
        import glob
        search = [os.path.abspath(CM_DIR), lib_dir]
        loaded = False
        for d in search:
            cms = sorted(glob.glob(os.path.join(d, "*.cm")))
            if not cms:
                continue
            for cm in cms:
                self.command("codemodel " + os.path.abspath(cm).replace("\\", "/"))
            loaded = True
            break
        if not loaded:
            print("warning: no XSPICE .cm files found", file=sys.stderr)

    def _init_callbacks(self) -> None:
        self._CB_CHAR = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
        self._CB_STAT = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
        self._CB_EXIT = CFUNCTYPE(c_int, c_int, c_bool, c_bool, c_void_p)
        self._CB_DATA = CFUNCTYPE(c_int, c_void_p, c_int, c_void_p)
        self._CB_INITDATA = CFUNCTYPE(c_int, c_void_p, c_void_p)
        self._CB_BG = CFUNCTYPE(c_int, c_bool, c_int, c_void_p)

        def send_char(s, ident, user):
            try:
                text = s.decode("utf-8", "replace")
            except Exception:
                text = str(s)
            self._out.append(text)
            return 0

        def send_stat(s, ident, user):
            try:
                text = s.decode("utf-8", "replace")
            except Exception:
                text = str(s)
            self._err.append(text)
            return 0

        def controlled_exit(status, immediate, quit, user):
            return 0

        def send_data(vec, size, user):
            # Not decoded here; we use ``write`` to a rawfile for data.
            return 0

        def send_init_data(vec, user):
            return 0

        def bg_thread(running, ident, user):
            return 0

        self._send_char = self._CB_CHAR(send_char)
        self._send_stat = self._CB_STAT(send_stat)
        self._controlled_exit = self._CB_EXIT(controlled_exit)
        self._send_data = self._CB_DATA(send_data)
        self._send_init_data = self._CB_INITDATA(send_init_data)
        self._bg_thread_running = self._CB_BG(bg_thread)

    def command(self, cmd: str) -> int:
        self._out.clear()
        self._err.clear()
        return self.lib.ngSpice_Command(cmd.encode("utf-8"))

    def circ(self, lines) -> int:
        """Load a circuit from a list of netlist lines (ngSpice_Circ)."""
        arr = (c_char_p * (len(lines) + 1))()
        for i, line in enumerate(lines):
            arr[i] = line.encode("utf-8")
        arr[len(lines)] = None
        self._out.clear()
        self._err.clear()
        return self.lib.ngSpice_Circ(arr)

    def run_file(self, path: str) -> int:
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f if ln.strip() and not ln.lstrip().startswith("*")]
        # The first SPICE line is always the title, never a device.
        lines.insert(0, "* ngspice runner netlist")
        # ngSpice_Circ expects the directives including the terminating .end.
        return self.circ(lines)

    def text(self) -> str:
        return "".join(self._out) + "".join(self._err)

    def reset(self) -> None:
        self.lib.ngSpice_Reset()


def main(argv):
    if len(argv) < 2:
        print("usage: ngspice_runner.py <netlist.cir> [commands...]")
        return 2
    ng = NgSpice()
    rc = ng.run_file(argv[1])
    print(f"circ rc={rc}")
    print(ng.text())
    for cmd in argv[2:]:
        ng.command(cmd)
        print(f"> {cmd}\n{ng.text()}")
    if not argv[2:]:
        ng.command("run")
        print(ng.text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

# Quartus / USB-Blaster / COM18 Probe Report

- **Date:** 2026-11-08
- **Host:** Windows 10 19045 x64, user `Lenovo` (member of local `Administrators`, but the shell is **not elevated** — `IsInRole(Administrator) = False`)
- **Work directory:** `D:\Document\tempPrj\74Series-CNN\Simulation\quartus_probe`
- **Nothing under `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System` was modified.**

## TL;DR

| Question | Answer |
|---|---|
| Did the design compile? | **No.** Quartus 18.0 Standard aborts before synthesis: the configured license file does not exist. |
| Exact LE / register / memory usage | **Not available** — no synthesis or fitter run ever completed, so no report exists. Not estimated here. |
| Can a bitstream be programmed right now? | **No.** Two independent blockers: (1) there is no `.sof` because compilation is blocked; (2) the USB-Blaster has no driver bound (Code 28), so `jtagconfig`/`quartus_pgm` see no hardware. |
| Is JTAG reachable? | **No.** No cable detected, no IDCODE read, nothing programmed. |
| COM18 at 115200 8N1 | **OK** — opens and closes cleanly (PowerShell and pyserial). |

---

## 1. Toolchain inventory

```
$ quartus_sh --version
Quartus Prime Shell
Version 18.0.0 Build 614 04/24/2018 SJ Standard Edition

C:\intelFPGA\18.0\quartus\version.txt:
  Version=18.0.0.614
  [ACDS]
  Version=18.0.0.614
  Edition=standard
```

The matching installer is on disk at `D:\Download\Quartus-18.0.0.614-windows-complete\`
(`QuartusSetup-18.0.0.614-windows.exe` + all device `.qdz` components, including
`cyclone-18.0.0.614.qdz`). This is the **Standard Edition "complete" package**; no Quartus
Prime **Lite** installer is present on the machine.

---

## 2. Task 1 — `probe` project and compile attempt

### 2.1 Files created

| File | Purpose |
|---|---|
| `D:\Document\tempPrj\74Series-CNN\Simulation\quartus_probe\probe.qpf` | Quartus project, revision `probe` |
| `D:\Document\tempPrj\74Series-CNN\Simulation\quartus_probe\probe.qsf` | `FAMILY "Cyclone IV E"`, `DEVICE EP4CE10F17C8`, `TOP_LEVEL_ENTITY probe_top` |
| `D:\Document\tempPrj\74Series-CNN\Simulation\quartus_probe\probe_top.v` | 32-bit free-running counter; `led = counter[27:24]`; ports `clk` (in), `led[3:0]` (out) |

No pin/location assignments were made (intentional, per task).

### 2.2 Commands run and exact output

```
$ quartus_map probe
Error (292026): Specified license file does not exist.
[exit code 3]

$ quartus_fit probe
Error (11720): Run Analysis and Synthesis (quartus_map) with top-level entity name "probe"
before running Fitter (quartus_fit)
Error: Quartus Prime Fitter was unsuccessful. 1 error, 0 warnings
[exit code 3]        <- consequence of the map failure, not an independent fault

$ quartus_asm probe
Error (292026): Specified license file does not exist.
[exit code 3]

$ quartus_sh --flow compile probe
Info: Project Name = D:/Document/tempPrj/74Series-CNN/Simulation/quartus_probe/probe
Info: Revision Name = probe
Error (292026): Specified license file does not exist.
Error (293001): Quartus Prime Full Compilation was unsuccessful. 1 error, 0 warnings
Error (23031): Evaluation of Tcl script .../qsh_flow.tcl unsuccessful
[exit code 3]
```

`output_files/` was never created. The only artifacts are `db\probe.db_info` and
`db\probe.fit.qmsg`. **No `.map.rpt`, `.fit.rpt`, `.asm.rpt` or `.sof` exists**, therefore
no LE / register / memory-bit numbers can be reported.

### 2.3 Root cause

```
C:\Users\Lenovo\quartus2.ini
    [General 18.0]
    LICENSE_FILE = C:\Users\Lenovo\Desktop\license.dat
```

`C:\Users\Lenovo\Desktop\license.dat` **does not exist**. No other license source is
configured (no `LM_LICENSE_FILE`/`QUARTUS_LICENSE_FILE` env vars, no `HKCU\Software\Altera`
or `HKLM\SOFTWARE\WOW6432Node\Altera` values), and no `*.dat`/`*.lic` Quartus license exists
anywhere on `D:\` or in the user profile.

To confirm this is a genuine "license required" state and not just a bad path, the compile
was re-run with `USERPROFILE`, `HOME`, `HOMEDRIVE` and `HOMEPATH` redirected to an empty
directory inside the probe folder (no `quartus2.ini` at all):

```
$ USERPROFILE=<empty dir> HOME=<empty dir> quartus_map probe
Error (292025): License file is not specified.
```

Repeated with a different family (`MAX 10`, `10M08SAE144C8G`) — identical error. So the
requirement is **global to this installation**, not project-, device- or family-specific.
There is no free/evaluation fallback in this build.

> **Integrity caveat (factual observation, not an endorsement):**
> `C:\intelFPGA\18.0\quartus\bin64\Quartus_18.0patch.exe` exists (138,240 bytes,
> 2026-11-07 21:15) and its embedded strings reference `sys_cpt.dll` and `Quartus.bin`;
> `sys_cpt.dll` (the FlexLM copy-protection module) carries a 2026-11-07 21:16 timestamp
> while the genuine binaries are dated 2018-04-25. This indicates the copy-protection DLL
> was modified after installation by a third-party licensing patcher. It was **not executed**
> as part of this probe. The supported fixes are in §5.2.

### 2.4 Device validity check (independent of the license)

`EP4CE10F17C8` is a legal part in the installed device database — verified via Tcl
(`quartus_sh -t`, `get_part_list -family "Cyclone IV E"` returns 158 parts):

```
PART: EP4CE10F17C6
PART: EP4CE10F17A7
PART: EP4CE10F17C7
PART: EP4CE10F17I7
PART: EP4CE10F17C8      <- our target
PART: EP4CE10F17C8L
PART: EP4CE10F17I8L
PART: EP4CE10F17C9L
```

The device name is `EP4CE10F17C8` (no `N`); the `N` in `EP4CE10F17C8N` is the lead-free
packaging suffix and is not part of the Quartus part number. Speed-grade-8 timing data for
`cycloneive` is present in `C:\intelFPGA\18.0\quartus\common\devinfo\cycloneive`.

---

## 3. Task 2 — USB-Blaster diagnosis

### 3.1 JTAG tool output

```
$ jtagconfig
No JTAG hardware available          [exit 0]

$ jtagconfig --enum
No JTAG hardware available

$ jtagconfig --serverinfo
Installed JTAG server is 'C:\intelFPGA\18.0\quartus\bin64\jtagserver.exe'
  Service manager reports server is running
Server reports path: C:\intelFPGA\18.0\quartus\bin64\jtagserver.exe
Server reports version: Version 18.0.0 Build 614 04/24/2018 SJ Standard Edition
Remote clients are disabled (no password)

$ quartus_pgm --list
No JTAG hardware available
Info: Quartus Prime Programmer was successful. 0 errors, 0 warnings    [exit 0]
```

The JTAG server service (`jtagserver.exe`, PID 4536) is running and healthy. The problem is
purely below it: no USB device is bound to a driver, so the server has nothing to enumerate.

### 3.2 PnP state of the blaster

```
InstanceId : USB\VID_09FB&PID_6001\00000000
FriendlyName: USB-Blaster
Status     : Error
Problem    : CM_PROB_FAILED_INSTALL
ProblemCode: 28 (0x1C)          ProblemStatus: 0xC0000490
ConfigFlags: 64                 (CONFIGFLAG_FAILEDINSTALL)
DriverInfPath : (empty)
DriverDesc    : (empty)
DriverVersion : (empty)
Service       : (empty)
HardwareIDs   : USB\VID_09FB&PID_6001&REV_0400, USB\VID_09FB&PID_6001
CompatibleIDs : USB\Class_FF&SubClass_FF&Prot_FF, USB\Class_FF&SubClass_FF, USB\Class_FF
Location      : Port_#0004.Hub_#0004, parent USB\ROOT_HUB30\7&1e49e2e6&0&0
BusReportedDeviceDesc: USB-Blaster

$ pnputil /enum-devices /instanceid "USB\VID_09FB&PID_6001\00000000"
设备描述: USB-Blaster
状态: 问题
问题代码: 28 (0x1C) [CM_PROB_FAILED_INSTALL]
问题状态: 0xC0000490
```

Code 28 with empty `DriverInfPath`/`Service` means **Windows enumerated the device (it reads
the descriptors fine — the device is present and powered) but no driver package was ever
successfully installed for it.** This is not a dead cable or a dead device.

### 3.3 Driver install attempt

```
$ pnputil /add-driver "C:\intelFPGA\18.0\quartus\drivers\usb-blaster\usbblstr.inf" /install
正在添加驱动程序包:  usbblstr.inf
无法添加驱动程序包: 拒绝访问。            ("Access denied")
驱动程序包总数:  1
已添加驱动程序包数: 0
[exit code 5]
```

Expected for a non-elevated shell. The driver package is **not** in the driver store:

```
$ pnputil /enum-drivers | grep -i usbblstr      -> (no match)
```

The driver store *does* contain FTDI's generic `ftdibus.inf` (oem133.inf / oem144.inf,
provider FTDI, v2.12.28.0, 2017-08-16), but that INF contains **no `VID_09FB` entry**, so it
cannot bind to the Altera blaster. The Altera INF is mandatory.

### 3.4 Driver package details

`C:\intelFPGA\18.0\quartus\drivers\usb-blaster\usbblstr.inf`

```
Class=USB
CatalogFile=usbblstr.cat
DriverVer=08/26/2014,2.12.00
Models: AlteraUSBBlaster.NT      (x86)   USB\VID_09FB&PID_6001 .. 6009
        AlteraUSBBlaster.NTamd64 (x64)   USB\VID_09FB&PID_6001 .. 6009
Payload: x64\usbblstr.sys, usbblstr64.dll, usbblstrlang.dll, usbblstrui.dll
```

Signature check:
- `usbblstr.cat` → **Valid**, CN = Delaware Altera Corporation
- `x64\usbblstr.sys` → **Valid**, CN = Future Technology Devices International Ltd

So the package is signed; a "Windows can't verify the publisher" prompt during install is a
2014-era catalog issue, not a corrupted package.

### 3.5 Is the JTAG link onboard or a separate dongle?

Host-side evidence only:

| Device | Parent hub | Port |
|---|---|---|
| USB-Blaster `VID_09FB&PID_6001` | `USB\ROOT_HUB30\7&1e49e2e6&0&0` | Port_#0004.Hub_#0004 |
| CH340 `VID_1A86&PID_7523` (COM18) | `USB\ROOT_HUB30\7&30488cf4&0&0` | Port_#0003.Hub_#0003 |

The two devices sit on **different USB root hubs (different PCIe root ports)**, i.e. they are
two separate physical USB connections, not one composite device.

**Onboard vs. dongle cannot be decided from the host side.** No board manual/schematic for
this board exists on disk (see §3.6), so the vendor's arrangement is unverified here. The
topology is equally consistent with (a) an onboard USB-Blaster behind its own USB connector
on the board, or (b) a standalone dongle on a second cable. Definitive test: unplug the
CH340 cable only — if the USB-Blaster stays enumerated, it is on a different connector
(onboard or dongle); unplug the board's power/USB entirely and see whether the blaster
disappears.

### 3.6 Board documentation search on `D:\`

Time-boxed shallow scan (`Get-ChildItem -Recurse -Depth 4`, then a targeted depth-6 scan of
`D:\Document\tempPrj`, `D:\Download`, `D:\tools` for `EP4CE|ALIENTEK|正点原子|开拓者|FPGA|开发板|开发指南|Cyclone`):

- **No ALIENTEK / 正点原子 EP4CE10 board material found** (no manual, schematic, pinout, demo
  project, `.sof`, `.qsf` for this board).
- Only 正点原子 material present is for a different product:
  `D:\Download\【正点原子】7寸RGB LCD电容触摸屏模块 800480资料\` (7-inch RGB LCD module).
- Other FPGA-adjacent items: `D:\Download\Quartus-18.0.0.614-windows-complete\` (installer) and
  `D:\Download\oss-cad-suite-windows-x64-20261022\` (yosys / openFPGALoader / openocd).
- The only Quartus project files on `D:\` are the ones created by this probe.

---

## 4. Task 3 — COM18

```
$ powershell: New-Object System.IO.Ports.SerialPort 'COM18',115200,'None',8,'One'; $p.Open()
OPEN_OK IsOpen=True Baud=115200 Parity=None DataBits=8 StopBits=One DTR=False RTS=False
BytesToRead=0
CLOSED_OK IsOpen=False

$ python -I -c "import serial; p=serial.Serial('COM18',115200,bytesize=8,parity='N',stopbits=1,timeout=0.3); ..."
pyserial open OK: COM18 115200 8 N 1 is_open= True
in_waiting= 0
closed OK, is_open= False
```

Port identity: `USB-SERIAL CH340 (COM18)`, `USB\VID_1A86&PID_7523\8&1A49E5CD&0&3`,
Status **OK** (driver bound normally).

**Scope note:** the port was only opened and closed. No bytes were transmitted and no
response was expected or observed (`in_waiting = 0`). Nothing here says anything about the
FPGA's UART logic — no bitstream is loaded.

---

## 5. Conclusions

### 5.1 Can a bitstream be programmed right now?

**No.** Both preconditions fail, independently:

1. **No bitstream exists.** `quartus_map`/`quartus_asm` abort with `Error (292026)` before
   producing any netlist; there is no `.sof`/`.pof` in the project or anywhere on `D:\`.
2. **No JTAG transport.** The USB-Blaster is in `CM_PROB_FAILED_INSTALL` (Code 28) with no
   driver, no service and no INF path. `jtagconfig` and `quartus_pgm --list` both report
   `No JTAG hardware available`.

Even if a `.sof` were supplied, programming would fail immediately. Nothing was programmed
and no JTAG IDCODE was read.

### 5.2 Precise administrator steps

**A. Fix the USB-Blaster driver** (account `Lenovo` is already in `Administrators`; only UAC
elevation is missing):

1. Open an **elevated** prompt (Win+X → *Terminal (Admin)* / *PowerShell (Admin)*), or
   right-click → *Run as administrator*.
2. Install the package:
   ```
   pnputil /add-driver "C:\intelFPGA\18.0\quartus\drivers\usb-blaster\usbblstr.inf" /install
   ```
   Expected on success: `已添加驱动程序包数: 1` / "Driver package added successfully".
3. Or via Device Manager (`devmgmt.msc`, elevated):
   - The device appears under **Other devices** as `USB-Blaster` with a yellow `!`
     (Problem code 28).
   - Right-click → **Update driver** → **Browse my computer for drivers** →
     **Let me pick from a list of available drivers on my computer** → **Have Disk…**
   - Browse to `C:\intelFPGA\18.0\quartus\drivers\usb-blaster\usbblstr.inf`
     (pick the `x64` payload automatically; do **not** point at `x32`).
   - Select **Altera USB-Blaster** → Next. Accept the publisher prompt if shown
     (catalog is signed by "Delaware Altera Corporation", dated 2014).
4. Unplug and replug the blaster's USB cable.
5. Verify (no admin needed):
   ```
   jtagconfig
   ```
   Expected: a line like `1) USB-Blaster [USB-0]` and, with the board powered,
   `EP4CE10` + its JTAG IDCODE underneath. `quartus_pgm --list` should then show
   `USB-Blaster`.

   If Device Manager still refuses the 2014 catalog on this Windows build, the fallback is
   *Disable driver signature enforcement* (Shift+Restart → Troubleshoot → Advanced options →
   Startup Settings → 7), then repeat step 2/3.

**B. Fix the missing license** (required before any compile):

- Restore a valid Quartus license to the path already configured:
  `C:\Users\Lenovo\Desktop\license.dat` (or edit `LICENSE_FILE` in
  `C:\Users\Lenovo\quartus2.ini` to point at the real file), **or**
- install **Quartus Prime Lite Edition 18.0**, which is free, needs no license, and supports
  Cyclone IV E / EP4CE10F17C8 — the current install is the Standard "complete" package and
  has no license-free mode (proved by the 292025 test in §2.3).

### 5.3 Quartus fit results and device caveats

- **Fit results: none.** The fitter never ran to completion; `output_files/` does not exist.
  No LE, register or memory-bit figures are reported here because none were measured.
- **Device:** `EP4CE10F17C8` — Cyclone IV E, 10,320 LEs, 414 Kbit embedded RAM (M9K),
  23 × 18×18 multipliers, 2 PLLs; `F17` = 256-pin FBGA; `C8` = commercial 0…85 °C, speed
  grade 8. (Datasheet figures, not measured.) Device is present in the installed database
  (§2.4).
- **Pin caveats:**
  - The project has **no location assignments**. A fitter run would auto-place `clk` and
    `led[3:0]` on arbitrary pins — meaningless for the real board and potentially driving
    pins that are inputs or power on the EP4CE10F17C8N board.
  - Unassigned/unused pins default to *As input tri-stated*; on a board with peripherals
    wired to those pins this is usually acceptable but should be made explicit.
  - The 50 MHz clock in `probe_top.v` is an **assumption** (typical for this class of board);
    it was not verified against a schematic. `led[3]` would toggle at ~0.37 Hz at 50 MHz.
  - A real build needs the board's `.qsf` pin assignments (clock pin, LED pins, I/O standard
    3.3-V LVTTL) plus a timing constraint (`create_clock`) before the fitter/STA results mean
    anything.

### 5.4 COM18 status

**Working.** `USB-SERIAL CH340 (COM18)`, `VID_1A86&PID_7523`, Status OK. Opens and closes at
115200 baud, 8 data bits, no parity, 1 stop bit via both `System.IO.Ports.SerialPort` and
pyserial 3.5. No data was exchanged.

---

## 6. Exact command log

```
quartus_sh --version
quartus_map probe                                   -> Error (292026), exit 3
quartus_fit probe                                   -> Error (11720), exit 3
quartus_asm probe                                   -> Error (292026), exit 3
quartus_sh --flow compile probe                     -> Error (292026)/(293001), exit 3
quartus_sh -t q_parts.tcl                           -> 158 Cyclone IV E parts, EP4CE10F17C8 legal
USERPROFILE/HOME redirected -> quartus_map probe    -> Error (292025) (no license fallback)
jtagconfig                                          -> No JTAG hardware available
jtagconfig --enum                                   -> No JTAG hardware available
jtagconfig --serverinfo                             -> server running, 18.0.0.614
quartus_pgm --list                                  -> No JTAG hardware available
Get-PnpDevice / Get-PnpDeviceProperty (USB\VID_09FB&PID_6001\00000000)
                                                    -> Error, Code 28, no INF/service
pnputil /enum-devices /instanceid ...               -> 问题代码 28 (0x1C)
pnputil /add-driver "...\usb-blaster\usbblstr.inf" /install
                                                    -> 拒绝访问 (access denied), exit 5
pnputil /enum-drivers                               -> no usbblstr; ftdibus oem133/oem144 present
Get-AuthenticodeSignature usbblstr.cat / .sys       -> Valid / Valid
PowerShell System.IO.Ports.SerialPort COM18         -> open OK, close OK
python -I -c "import serial; ..."                   -> open OK, close OK
Get-ChildItem D:\ -Recurse -Depth 4 (board name patterns)  -> no board docs
```

## 7. What was NOT verified

- No synthesis, no fit, no assembly, no timing analysis, no `.sof`.
- No JTAG cable detected, no IDCODE read, no device programmed, no flash written.
- No UART traffic to/from the FPGA.
- Board manual/schematic/pinout: not available on this machine.

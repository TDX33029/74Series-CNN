#!/usr/bin/env bash
# ModelSim regression for the FPGA bridge.  Override MODELSIM if needed:
#   MODELSIM=/c/intelFPGA/18.0/modelsim_ase/win32aloem ./run_sim.sh
set -e
cd "$(dirname "$0")"
MODELSIM="${MODELSIM:-/c/intelFPGA/18.0/modelsim_ase/win32aloem}"
mkdir -p sim_work
cd sim_work
[ -d work ] || "$MODELSIM/vlib.exe" work
"$MODELSIM/vlog.exe" -quiet ../uart_rx.v ../uart_tx.v ../b12_port.v \
                              ../host_bridge.v ../tb_host_bridge.v
"$MODELSIM/vsim.exe" -c tb_host_bridge -do "run -all; quit -f"

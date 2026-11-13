#!/bin/bash
# Parallel one-vector-per-core regression: 8 vsim processes, each runs
# exactly one vector (+nvec=1 +vfirst=K) in its own directory with its own
# compiled library.  ModelSim ASE is single-threaded per process, so the
# only way to use all cores is process-level parallelism.
export PATH="/c/intelFPGA/18.0/modelsim_ase/win32aloem:$PATH"
cd "$(dirname "$0")"

# absolute weights path: the TB defaults to "../../weights/x28s/" which is
# only correct when vsim runs from Simulation/rtl itself; each parallel run
# has its own directory, so pass the prefix explicitly
WBASE="$(cd ../.. && pwd -W 2>/dev/null || pwd)/weights/x28s/"

: > sim_par_status.txt
VECS="${@:-0 1 2 3 4 5 6 7}"
for k in $VECS; do
  d=sim_v$k
  rm -rf "$d"
  mkdir -p "$d"
  cp -r init "$d/init"
  (
    cd "$d" || exit 1
    vlib work > vlib.log 2>&1
    vlog -sv -work work ../models.v ../cnn74_top.v ../tb_numeric.v > vlog.log 2>&1
    if [ $? -ne 0 ]; then
      echo "v$k compile FAILED" >> ../sim_par_status.txt
      exit 1
    fi
    vsim -c -voptargs="+acc" work.tb_numeric "+nvec=1" "+vfirst=$k" \
         "+wbase=$WBASE" -do "run -all; quit -f" > sim.log 2>&1
    echo "v$k exit=$?" >> ../sim_par_status.txt
  ) &
done
wait
echo "=== ALL PARALLEL RUNS DONE ==="
cat sim_par_status.txt

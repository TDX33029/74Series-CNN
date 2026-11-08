@echo off
setlocal
cd /d "%~dp0"
set PATH=C:\intelFPGA\18.0\modelsim_ase\win32aloem;%PATH%

echo === generating models ===
python gen_models.py || exit /b 1
python gen_timing_rom.py || exit /b 1
echo === generating structural top ===
python gen_rtl.py || exit /b 1

echo === compiling ===
if exist work rmdir /s /q work
vlib work || exit /b 1
vlog -sv models.v cnn74_top.v tb_cnn74.v || exit /b 1

echo === running ===
vsim -c -voptargs=+acc tb_cnn74 -do "run -all; quit -f"

when {/tb_cnn28_core/dut/st === 5'b00101} {
  echo "FIRST C1 WRITE"
  examine -radix hex /tb_cnn28_core/dut/acc
  examine -radix hex /tb_cnn28_core/dut/prod_r
  examine -radix unsigned /tb_cnn28_core/dut/s_r
  examine -radix hex /tb_cnn28_core/dut/m_r
  examine -radix unsigned /tb_cnn28_core/dut/sat8
  examine -radix hex /tb_cnn28_core/dut/raw
  examine -radix hex /tb_cnn28_core/dut/sx
  examine -radix hex /tb_cnn28_core/dut/bias_r
  stop
}
run 900us
quit -f

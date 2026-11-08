`timescale 1ns/1ps
module tb_osc;
  wire o;
  m_Oscillator_ASE_xxxMHz X10001 (.p1(1'b1), .p3(o));
  initial begin
    #1000;
    $display("t=%0t o=%b clk=%b half=%0f", $time, o, X10001.clk, X10001.HALF_NS);
    $finish;
  end
endmodule

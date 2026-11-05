# Model Review Report - iceman-contributor-free
Date: 2026-11-05
Reviewer: iceman-contributor-free (independent review)
Main project: D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System
Plan/spec: D:/Document/tempPrj/74Series-CNN/CNN_74xx_MNIST_28x28_v1.txt
Brief: D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/docs/MODEL_REVIEW_BRIEF.md
Work copy (isolated): D:/Document/tempPrj/74Series-CNN/Cache/_review_iceman-contributor-free/work
Report dir: D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/iceman-contributor-free/

## 1) Environment / Commands / Timing
- Platform: win32 (Git Bash), repo present.
- Setup: copied entire project to isolated work copy (removed old review dir first). Created report directory in main project.
- Tests executed in work copy (all RC=0):
  1. python sim/run_all.py - 9/9 checks passed (lut_contents, lut_spice, glue, supervisor, timing, mem_decode, pool, argmax, conv_fc_engines). Logs in sim/*.log.
  2. python tools/gen_lut.py (RC:0)
  3. python sim/gen_lut_tb.py (RC:0)
  4. python sim/gen_glue_tb.py (RC:0)
  5. python sim/gen_supervisor_tb.py (RC:0)
  6. python sim/gen_timing_tb.py (RC:0)
  7. python sim/gen_mem_decode_tb.py (RC:0)
  8. python sim/gen_pool_tb.py (RC:0)
  9. python sim/gen_argmax_tb.py (RC:0)
  10. python sim/gen_engine_tb.py (RC:0) - conv1/conv2/fc all PASS.

Full command list with RCs in commands.log.

## 2) Topology understanding
- 28x28x1 MNIST, CONV1 5x5/8ch->POOL1 2x2/2, CONV2 3x3/16ch->POOL2 2x2/2, FC1 400->32, FC2 32->10, ARGMAX. 8-bit bus, 32-bit accumulators, LUT multiply, requant/ReLU.
- S01 Supervisor, S02 Timing (shared per brief), S04 Memories (SRAM/LUT, 24-bit addr + MEM_SEL), S05 Pool, S06 Argmax, S07 Conv1, S08 Conv2, S09 FC, S10 Top IO. Global labels, root overview/connection table.

## 3) Test results (PASS/FAIL)
All executed: PASS. run_all 9/9. Engine TB matches golden MACs/addresses/bounds. Logs in sim/*.log.

## 4) Joint logic verification
- A) FSM->engine->storage: supervisor PASS.
- B) S02<->S04: timing/mem_decode PASS.
- C) Engine address/data: engine TB PASS for all MACs.
- D) Static netlist audit: inspected schematics/connection matrix/ERCs (findings F-001/F-002).
- E) Data path: pool/argmax/engines covered by run_all.

## 5) Schematic/ERC/BOM
- Top ERC: CNN_74xx_System.rpt - 940 Errors, 42 Warnings, 898 (42 pin_not_driven at top per brief; needs classification).
- Per-sheet ERCs in output/erc/.
- BOM: output/bom/CNN_74xx_System_BOM.csv - 27C512x17, 6264x7, 28C256x12, LUT_Mult_Unitx12, Requant_Blockx3, S02_MEM_IFx3, 8MHz x1 etc.
- Connection matrix flags START fanout and possible DONE multi-driver.

## 6) Findings
See findings.json (F-001 major shared S02 vs per-engine IFs, F-002 major engine->S04 reachability, F-003 major LUT mapping, F-004 major Requant implementation, F-005 major top pin_not_driven classification, F-006/F-007 minor).

## 7) Conflicts with docs
- run_all 9/9 confirmed. Top 42 pin_not_driven confirmed. S02_MEM_IF presence suggests placeholders/instances need wiring verification vs "one shared S02" claim.

## 8) Must-fix before tapeout
- Classify all 42 top pin_not_driven (external vs internal). Fix internal breaks.
- Verify engine S02_MEM_IF -> shared S02 -> S04 connectivity/ADDR/MEM_SEL.
- Resolve LUT_Mult_Unit (12) vs 4 lanes vs 8x27C512 mapping.
- Check DONE multi-driver and S01 control of S05/S06.
- Verify Requant_Block implementation.

## 9) Unverified
- Full hierarchical net connectivity (need kicad-cli netlist). S02_MEM_IF internal wiring. Complete classification of 42 pin_not_driven. 10-100Hz vs 8MHz margins. BOM 490 ICs reconciliation.

Conclusion: Sim tests PASS (9/9). Schematic-level joint connectivity/ERC classification are the main gaps requiring netlist-level verification.

import json
seq = (['LEDP1'] +
  ['LED_DIR_SEL','LED_LOAD_EN_I','LED_LOAD_NOE_I','LED_LOAD_NWE_I','LED_MEM_NOE_INT','LED_MEM_NWE_INT',
   'LED_NCS_SRAM_FC1OUT','LED_NCS_SRAM_FC2LOG','LED_READ_DIR'] +
  ['LED_DATA4','LED_DATA5','LED_DATA6','LED_MEM_D0','LED_MEM_D1','LED_MEM_D2','LED_MEM_D3','LED_MEM_D4',
   'LED_MEM_D5','LED_MEM_D6','LED_MEM_D7'])
mods = {
 'LEDP1':   (None, 'RP1', None),
 'LED_DATA4':('Q3005','R3010','R3009'),
 'LED_DATA5':('Q3006','R3012','R3011'),
 'LED_DATA6':('Q3007','R3014','R3013'),
 'LED_MEM_NOE_INT':('Q3008','R1','R3015'),
 'LED_MEM_NWE_INT':('Q3009','R2','R3016'),
 'LED_READ_DIR':('Q3010','R3','R3017'),
 'LED_DIR_SEL':('Q3011','R4008','R4007'),
 'LED_LOAD_EN_I':('Q3012','R4010','R4009'),
 'LED_LOAD_NOE_I':('Q3013','R4012','R4011'),
 'LED_LOAD_NWE_I':('Q3014','R4014','R4013'),
 'LED_MEM_D0':('Q3015','R4016','R4015'),
 'LED_MEM_D1':('Q3016','R4018','R4017'),
 'LED_MEM_D2':('Q3017','R4020','R4019'),
 'LED_MEM_D3':('Q3018','R4022','R4021'),
 'LED_MEM_D4':('Q3019','R4024','R4023'),
 'LED_MEM_D5':('Q3020','R4026','R4025'),
 'LED_MEM_D6':('Q3021','R4028','R4027'),
 'LED_MEM_D7':('Q3022','R4030','R4029'),
 'LED_NCS_SRAM_FC1OUT':('Q3023','R4032','R4031'),
 'LED_NCS_SRAM_FC2LOG':('Q3024','R4034','R4033'),
}
X_LED = 3822.5
X_Q = 3570.0
X_R1K = 3380.0
X_R10K = 3300.0
PITCH = 122.0
# bottom = y more negative end (far from header-side content); rows go UP = y increasing
ys = []
yy = -3146.0
for i in range(len(seq)):
    if i == 1 or i == 10:
        yy += 60.0
    ys.append(yy)
    yy += PITCH
led_plan, q_plan, r_plan = [], [], []
for led, yv in zip(seq, ys):
    led_plan.append([led, X_LED, yv, 0])
    q, r10k, r1k = mods[led]
    if q: q_plan.append([q, X_Q, yv, 90])
    if r10k: r_plan.append([r10k, X_R10K, yv, 0])
    if r1k: r_plan.append([r1k, X_R1K, yv, 0])
iso = [['R4001',X_R10K,-580,0],['R4003',X_R1K,-580,0],['R4004',X_R10K,-680,0],['R4005',X_R1K,-680,0],['R4006',3340.0,-780,0]]
out = {
 'led': led_plan, 'q': q_plan, 'r': r_plan + iso,
 'chip_move': [['U4020', 3050.0, -800.0, 90]],
 'meta': {'x_led':X_LED,'x_q':X_Q,'x_r1k':X_R1K,'x_r10k':X_R10K,'pitch':PITCH,'y_bottom_start':-3146.0,
          'order_bottom_to_top':seq,'coord_note':'y negative up = toward y=0; bottom = -3228 end',
          'x_u4020_new':3050.0}
}
with open(r'D:/Document/tempPrj/74Series-CNN/tools/eda_scripts/b031_passive_plan.json','w') as f:
    json.dump(out, f, indent=1)
print("LED rows:", len(led_plan), "Q:", len(q_plan), "R total:", len(r_plan)+len(iso))
print("ys:", ys)
print("bottom edge:", ys[0]-60, "top edge:", ys[-1]+60)

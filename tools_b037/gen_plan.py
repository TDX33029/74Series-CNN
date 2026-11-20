# -*- coding: utf-8 -*-
import json

LEDX = 3822.5
QX = 3565
R10K_X = 3410
R1K_X = 3475

# bottom -> top: (designator, y) ; group boundaries get +192 instead of +122
led_rows = []
y = -3140
# power group
led_rows.append(('LEDP1', y))
y += 192
# control group (sorted by designator)
for des in ['LED_MEM_SEL1', 'LED_POOL1_MEM_NCE_OUT', 'LED_POOL1_READ_OE', 'LED_POOL2_READ_OE']:
    led_rows.append((des, y))
    y += 122
y += 70
# data group (sorted by designator)
for des in ['LED_ADDR0', 'LED_ADDR1',
            'LED_POOL1_IN_ADDR0', 'LED_POOL1_IN_ADDR1', 'LED_POOL1_IN_ADDR2', 'LED_POOL1_IN_ADDR3',
            'LED_POOL1_IN_ADDR5', 'LED_POOL1_IN_ADDR6', 'LED_POOL1_IN_ADDR7',
            'LED_POOL1_OUT_ADDR0', 'LED_POOL1_OUT_ADDR11', 'LED_POOL1_OUT_ADDR6', 'LED_POOL1_OUT_ADDR7',
            'LED_POOL1_OUT_ADDR8', 'LED_POOL1_OUT_ADDR9', 'LED_POOL2_IN_ADDR0']:
    led_rows.append((des, y))
    y += 122

ledy = dict(led_rows)

# module map: LED -> (Q, R1k, R10k)
mods = {
 'LED_POOL1_READ_OE':('Q1','R1','R4003'), 'LED_POOL2_READ_OE':('Q2','R2','R4004'),
 'LED_MEM_SEL1':('Q3','R3','R4005'), 'LED_POOL1_MEM_NCE_OUT':('Q4','R4','R4006'),
 'LED_ADDR0':('Q5','R5','R4007'), 'LED_ADDR1':('Q6','R6','R4008'),
 'LED_POOL1_IN_ADDR0':('Q7','R4010','R4009'), 'LED_POOL1_IN_ADDR1':('Q8','R4012','R4011'),
 'LED_POOL1_IN_ADDR2':('Q9','R4014','R4013'), 'LED_POOL1_IN_ADDR3':('Q10','R4016','R4015'),
 'LED_POOL1_IN_ADDR5':('Q11','R4018','R4017'), 'LED_POOL1_IN_ADDR6':('Q12','R4020','R4019'),
 'LED_POOL1_IN_ADDR7':('Q13','R4022','R4021'), 'LED_POOL1_OUT_ADDR0':('Q14','R4024','R4023'),
 'LED_POOL1_OUT_ADDR11':('Q15','R4026','R4025'), 'LED_POOL1_OUT_ADDR6':('Q16','R4028','R4027'),
 'LED_POOL1_OUT_ADDR7':('Q17','R4030','R4029'), 'LED_POOL1_OUT_ADDR8':('Q18','R4032','R4031'),
 'LED_POOL1_OUT_ADDR9':('Q19','R4034','R4033'), 'LED_POOL2_IN_ADDR0':('Q20','R4036','R4035'),
}

plan_led = [[des, LEDX, yy] for des, yy in led_rows]
plan_q = []
plan_r1k = []
plan_r10k = []
for led, (q, r1, r10) in sorted(mods.items(), key=lambda kv: ledy[kv[0]]):
    yy = ledy[led]
    plan_q.append([q, QX, yy])
    plan_r1k.append([r1, R1K_X, yy])
    plan_r10k.append([r10, R10K_X, yy])
plan_rp1 = [['RP1', QX, ledy['LEDP1']]]
plan_isolated = [['R4002', R10K_X, -450]]

out = {'led': plan_led, 'q': plan_q, 'r1k': plan_r1k, 'r10k': plan_r10k,
       'rp1': plan_rp1, 'isolated': plan_isolated, 'ledy': {k: v for k, v in led_rows}}
json.dump(out, open(r'D:/Document/tempPrj/74Series-CNN/tools_b037/plan_taskB.json', 'w'), indent=1)
print('LED rows bottom->top:')
for des, yy in led_rows:
    m = mods.get(des)
    tag = f"  module: {m[0]}/{m[1]}/{m[2]}" if m else "  RP1 only"
    print(f'{des:<28} y={yy:<8}{tag}')
print('isolated R4002 ->', plan_isolated)
print('counts: led', len(plan_led), 'q', len(plan_q), 'r1k', len(plan_r1k), 'r10k', len(plan_r10k))

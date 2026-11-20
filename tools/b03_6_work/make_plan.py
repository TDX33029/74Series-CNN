import json

# actual LED list from survey (21 total)
leds_power = ['LEDP1']
leds_ctrl = ['LED_ARGMAX_BUSY_N','LED_C2_BUSY_N','LED_IMAGE_DONE_N','LED_POOL1_READ_OE','LED_POOL2_BUSY_N','LED_POOL2_MEM_WE','LED_POOL2_READ_OE']
leds_data = ['LED_C2_ADDR0','LED_C2_ADDR1','LED_C2_ADDR10','LED_C2_ADDR11','LED_C2_ADDR12','LED_C2_ADDR13','LED_C2_ADDR14','LED_C2_ADDR15','LED_C2_ADDR2','LED_C2_ADDR3','LED_C2_ADDR4','LED_C2_ADDR5','LED_DATA7']
order = leds_power + sorted(leds_ctrl) + sorted(leds_data)
assert len(order) == 21, len(order)

# bottom->top: y from -3140 increasing (up). pitch 122, group gap +70 extra
y = -3140.0
plan_led = {}
for i, led in enumerate(order):
    plan_led[led] = y
    step = 122.0
    if i == 0 or i == len(leds_power) + len(leds_ctrl) - 1:
        step += 70.0
    y += step
print('top LED center y =', plan_led[order[-1]], 'pad edge', plan_led[order[-1]]+27.55, 'vs board top 0')

q_map = {
 'LED_ARGMAX_BUSY_N':'Q3012','LED_C2_ADDR0':'Q3016','LED_C2_ADDR1':'Q3017','LED_C2_ADDR10':'Q3018',
 'LED_C2_ADDR11':'Q3019','LED_C2_ADDR12':'Q3020','LED_C2_ADDR13':'Q3021','LED_C2_ADDR14':'Q3022',
 'LED_C2_ADDR15':'Q3023','LED_C2_ADDR2':'Q3024','LED_C2_ADDR3':'Q3025','LED_C2_ADDR4':'Q3026',
 'LED_C2_ADDR5':'Q3027','LED_C2_BUSY_N':'Q3013','LED_DATA7':'Q3008','LED_IMAGE_DONE_N':'Q3011',
 'LED_POOL1_READ_OE':'Q3009','LED_POOL2_BUSY_N':'Q3014','LED_POOL2_MEM_WE':'Q3015','LED_POOL2_READ_OE':'Q3010'}
r1k_map = {
 'LED_ARGMAX_BUSY_N':'R3020','LED_C2_ADDR0':'R4014','LED_C2_ADDR1':'R4016','LED_C2_ADDR10':'R4018',
 'LED_C2_ADDR11':'R4020','LED_C2_ADDR12':'R4022','LED_C2_ADDR13':'R4024','LED_C2_ADDR14':'R4026',
 'LED_C2_ADDR15':'R4028','LED_C2_ADDR2':'R4030','LED_C2_ADDR3':'R4032','LED_C2_ADDR4':'R4034',
 'LED_C2_ADDR5':'R4036','LED_C2_BUSY_N':'R3021','LED_DATA7':'R3015','LED_IMAGE_DONE_N':'R3019',
 'LED_POOL1_READ_OE':'R3017','LED_POOL2_BUSY_N':'R4010','LED_POOL2_MEM_WE':'R4012','LED_POOL2_READ_OE':'R3018'}
r10k_map = {
 'LED_ARGMAX_BUSY_N':'R4','LED_C2_ADDR0':'R4015','LED_C2_ADDR1':'R4017','LED_C2_ADDR10':'R4019',
 'LED_C2_ADDR11':'R4021','LED_C2_ADDR12':'R4023','LED_C2_ADDR13':'R4025','LED_C2_ADDR14':'R4027',
 'LED_C2_ADDR15':'R4029','LED_C2_ADDR2':'R4031','LED_C2_ADDR3':'R4033','LED_C2_ADDR4':'R4035',
 'LED_C2_ADDR5':'R4037','LED_C2_BUSY_N':'R5','LED_DATA7':'R3016','LED_IMAGE_DONE_N':'R3',
 'LED_POOL1_READ_OE':'R1','LED_POOL2_BUSY_N':'R4011','LED_POOL2_MEM_WE':'R4013','LED_POOL2_READ_OE':'R2'}

used = []
plan = {'led': {}, 'q': {}, 'r1k': {}, 'r10k': {}, 'rp1': None, 'orphan': {}}
for led in order:
    yy = plan_led[led]
    plan['led'][led] = [3822.5, yy]
    if led == 'LEDP1':
        plan['rp1'] = ['RP1', 3565, yy]
        continue
    for m, key, xx in ((q_map,'q',3565),(r1k_map,'r1k',3475),(r10k_map,'r10k',3410)):
        comp = m[led]
        assert comp not in used, 'duplicate ' + comp
        used.append(comp)
        plan[key][comp] = [xx, yy]
plan['orphan']['R4009'] = [3410, -450]

# coverage check
all_r = ['R1','R2','R3','R4','R5','R3015','R3016','R3017','R3018','R3019','R3020','R3021'] + ['R40%d'%i for i in range(10,38)]
all_q = ['Q30%02d'%i for i in range(8,28)]
print('missing R:', [r for r in all_r if r not in used])
print('missing Q:', [q for q in all_q if q not in used])
print('placed R count:', sum(len(plan[k]) for k in ('r1k','r10k')), 'Q count:', len(plan['q']))

json.dump(plan, open(r'D:\Document\tempPrj\74Series-CNN\tools\b03_6_work\passive_plan.json','w'), indent=1)
print('plan saved')

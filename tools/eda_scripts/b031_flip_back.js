// flip all Q and R/RP to backside layer 2
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const des_list = ['Q3005','Q3006','Q3007','Q3008','Q3009','Q3010','Q3011','Q3012','Q3013','Q3014',
 'Q3015','Q3016','Q3017','Q3018','Q3019','Q3020','Q3021','Q3022','Q3023','Q3024',
 'R1','R2','R3','R3009','R3010','R3011','R3012','R3013','R3014','R3015','R3016','R3017',
 'R4001','R4003','R4004','R4005','R4006','R4007','R4008','R4009','R4010','R4011','R4012','R4013',
 'R4014','R4015','R4016','R4017','R4018','R4019','R4020','R4021','R4022','R4023','R4024','R4025',
 'R4026','R4027','R4028','R4029','R4030','R4031','R4032','R4033','R4034','RP1'];
let flipped = 0, missing = [];
for (const des of des_list) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_Layer(2);
  await a.done();
  flipped++;
}
// verify
const comps2 = await eda.pcb_PrimitiveComponent.getAll();
const wrong = [];
for (const des of des_list) {
  const c = comps2.find(k => k.getState_Designator() === des);
  if (c && c.getState_Layer() !== 2) wrong.push([des, c.getState_Layer()]);
}
return JSON.stringify({flipped, missing, wrong});

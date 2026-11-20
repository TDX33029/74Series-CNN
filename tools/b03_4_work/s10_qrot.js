const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const qdes = ['QTQ5','Q17','Q18','Q1','Q6','Q8','Q7','Q15','Q2','Q9','Q10','Q11','Q12','Q13','Q14','Q3','Q4','Q19','Q20','Q16'];
let n = 0;
for (const des of qdes) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) continue;
  const a = c.toAsync();
  a.setState_Rotation(90);
  await a.done();
  n++;
}
return 'rot90 set on ' + n + ' Q';

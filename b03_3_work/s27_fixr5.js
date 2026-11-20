const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// R4 horizontal at (3410,-260): pad1 at 3392.9, pad2 3427.1, y=-260. U4050_10 at (3325.03,-250): dist to pad1 = sqrt(67.9^2+10^2)=68.7 <88.
// Rotate R4 90deg like the other two: pads dy=±17 => (3410,-277),(3410,-243): dist to U4050_10 = sqrt(84.97^2+7^2)=85.3 <88. Move x to 3420: sqrt(94.97^2)=95 OK
const plan = [['R4', 3420, -260, 90], ['R3035', 3420, -350, 90], ['R3037', 3420, -440, 90], ['R5', 3410, -170, 90], ['R3013', 3475, -170, 90], ['R3012', 3475, -260, 90], ['R3034', 3475, -350, 90], ['R3036', 3475, -440, 90]];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  await a.done();
}
return 'ok';

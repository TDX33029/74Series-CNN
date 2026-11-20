const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
// 88mil check: back SMD pads (layer2 comps: Q/R/RP) vs front TH pads (all layer1 comps pads)
const comps = await eda.pcb_PrimitiveComponent.getAll();
const backPads = [], frontTH = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const layer = c.getState_Layer();
  const a = c.toAsync();
  const pins = await a.getAllPins();
  for (const p of pins) {
    if (layer === 2) backPads.push({des, n: p.padNumber, x: p.x, y: p.y, r: Math.max(p.pad[1]||0, p.pad[2]||0)/2});
    else if (p.pad && (p.pad[0] === 'ELLIPSE' || p.pad[0] === 'RECT' || p.pad[0] === 'OVAL')) {
      // TH pads on front: chips, J, LEDs (all TH)
      frontTH.push({des, n: p.padNumber, x: p.x, y: p.y, r: Math.max(p.pad[1]||0, p.pad[2]||0)/2});
    }
  }
}
// exclude back pads of LEDs? LEDs are front. back pads belong to Q/R/RP only.
let minD = 1e9, worst = null, violations = 0;
for (const b of backPads) {
  for (const f of frontTH) {
    const dx = b.x - f.x, dy = b.y - f.y;
    const cdist = Math.sqrt(dx*dx + dy*dy);
    const gap = cdist - b.r - f.r;
    if (gap < minD) { minD = gap; worst = {b: b.des+'_'+b.n, f: f.des+'_'+f.n, cdist: Math.round(cdist*10)/10}; }
    // user rule: center distance >= 88mil
    if (cdist < 88) { violations++; }
  }
}
return JSON.stringify({nBack: backPads.length, nFront: frontTH.length, minCenterDist: worst, violations88: violations});

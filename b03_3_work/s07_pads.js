const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const pads = await eda.pcb_PrimitivePad.getAll();
// outline pads = pads with no net? board outline layer pads won't exist. Instead check pads near x in [0,3937] y in [0,3228] region
let inOutlineRegion = 0, samples = [];
for (const p of pads) {
  if (p.x >= -10 && p.x <= 3947 && p.y >= -10 && p.y <= 3238) { inOutlineRegion++; if (samples.length < 5) samples.push({x:p.x,y:p.y,net:p.net}); }
}
// J pads
const jp = pads.filter(p => p.x > 20 && p.x < 170 && p.y > -3200 && p.y < -50);
let jminx=1e9,jmaxx=-1e9,jminy=1e9,jmaxy=-1e9;
for (const p of jp) { jminx=Math.min(jminx,p.x); jmaxx=Math.max(jmaxx,p.x); jminy=Math.min(jminy,p.y); jmaxy=Math.max(jmaxy,p.y); }
return JSON.stringify({inOutlineRegion, samples, jCount: jp.length, jBBox: {jminx, jmaxx, jminy, jmaxy}});

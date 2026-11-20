// DRC detail: dump Clearance Error entries
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const clr = arr.find(c => c.name === 'Clearance Error');
if (!clr) return 'NO CLEARANCE ERROR';
const items = [];
for (const sub of (clr.list || [])) {
  for (const e of (sub.list || [])) {
    items.push({
      type: sub.name,
      msg: (e.msg || e.message || e.text || '').toString().slice(0, 200),
      minDistance: e.minDistance,
      x: e.x, y: e.position ? e.position.x : undefined, y2: e.position ? e.position.y : undefined,
      pos: e.position,
      obj1: e.obj1 ? {type: e.obj1.primitiveType, id: e.obj1.primitiveId, des: e.obj1.designator, net: e.obj1.net, x: e.obj1.x, y: e.obj1.y} : null,
      obj2: e.obj2 ? {type: e.obj2.primitiveType, id: e.obj2.primitiveId, des: e.obj2.designator, net: e.obj2.net, x: e.obj2.x, y: e.obj2.y} : null
    });
  }
}
return JSON.stringify({total: items.length, items: items.slice(0, 60)});

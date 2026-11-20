const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const out = arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
return JSON.stringify(out);

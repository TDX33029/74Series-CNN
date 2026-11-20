const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r1 = await eda.pcb_Document.zoomToBoardOutline();
let r2 = null;
try { r2 = await eda.pcb_Document.zoomToAllPrimitives(); } catch(e) { r2 = String(e); }
return JSON.stringify({zoomOutline: r1, zoomAll: r2});

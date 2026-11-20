// step1: open project + document, verify uuid
const PROJECT = '86c1d8c59be2462ebb49fab075a5c297';
const PCB = 'd760df1fa8af5bfc';
try {
  const cur0 = await eda.dmt_SelectControl.getCurrentDocumentInfo();
  if (cur0 && cur0.uuid === PCB) {
    return 'ALREADY_OPEN ' + cur0.uuid + ' type=' + cur0.documentType;
  }
} catch (e) { /* ignore */ }
await eda.dmt_Project.openProject(PROJECT);
await eda.dmt_EditorControl.openDocument(PCB);
const cur = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (cur.uuid !== PCB) return 'ABORT: wrong document ' + cur.uuid;
return 'OPENED ' + cur.uuid + ' type=' + cur.documentType;

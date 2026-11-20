const TARGET = '1595c28f09776867';
const doc0 = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc0 && doc0.uuid === TARGET) return 'ALREADY OPEN: ' + doc0.uuid;
const prj = await eda.dmt_Project.getCurrentProjectInfo();
if (!prj || prj.uuid !== '86c1d8c59be2462ebb49fab075a5c297') {
  const op = await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
  if (!op) return 'ABORT: openProject failed';
}
await eda.dmt_EditorControl.openDocument(TARGET);
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({uuid: doc.uuid, type: doc.documentType});

const TARGET = '822ec5745398cfb8';
try {
  const info = await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
  var r1 = 'openProject ok';
} catch(e) { var r1 = 'openProject err: ' + e; }
try {
  await eda.dmt_EditorControl.openDocument(TARGET);
  await new Promise(res => setTimeout(res, 1500));
} catch(e) { var r2 = 'openDocument err: ' + e; }
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({r1: r1, doc: doc.uuid, docType: doc.documentType});

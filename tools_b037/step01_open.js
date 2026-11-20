const TARGET = '046a237b7518687e';
await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await eda.dmt_EditorControl.openDocument('046a237b7518687e');
await new Promise(r => setTimeout(r, 1500));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
return JSON.stringify({uuid: doc.uuid, type: doc.documentType});

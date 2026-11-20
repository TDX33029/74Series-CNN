const r1 = await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await eda.dmt_EditorControl.openDocument('e4b2cb67c3463844');
await new Promise(res => setTimeout(res, 3000));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({openProject: r1, uuid: doc.uuid, docType: doc.documentType});

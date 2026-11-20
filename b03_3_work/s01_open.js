const TARGET = '7ce97899ea288f46';
const info = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (info.uuid === TARGET) return 'ALREADY_OPEN uuid=' + info.uuid + ' docType=' + info.documentType;
await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await eda.dmt_EditorControl.openDocument(TARGET);
await new Promise(r => setTimeout(r, 3000));
const info2 = await eda.dmt_SelectControl.getCurrentDocumentInfo();
return JSON.stringify({uuid: info2.uuid, docType: info2.documentType});

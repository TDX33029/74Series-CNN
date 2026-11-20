const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// try eda.dmt_EditorControl methods list
const ec = eda.dmt_EditorControl;
return JSON.stringify(Object.getOwnPropertyNames(Object.getPrototypeOf(ec) || ec).slice(0, 60));

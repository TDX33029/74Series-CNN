const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
const names = Object.keys(eda).filter(k => /view|zoom|canvas/i.test(k));
return JSON.stringify(names);

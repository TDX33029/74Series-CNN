#!/bin/bash
# Retry wrapper: run bridge_run.py on JS file; if ABORT or error, re-open target doc, wait 20s, retry (max 15)
JS="$1"; OUT="$2"
TARGET_PCB=a8a7bb9eb952a5f7
for i in $(seq 1 15); do
  python -I D:/Document/tempPrj/74Series-CNN/tools/bridge_run.py "$JS" "$OUT" > /c/Users/Lenovo/AppData/Local/Temp/eda_last_run.txt 2>&1
  rc=$?
  if [ $rc -eq 0 ] && ! grep -q "^ABORT" /c/Users/Lenovo/AppData/Local/Temp/eda_last_run.txt; then
    echo "OK attempt=$i"
    head -c 200 /c/Users/Lenovo/AppData/Local/Temp/eda_last_run.txt
    exit 0
  fi
  echo "attempt $i failed: $(head -c 150 /c/Users/Lenovo/AppData/Local/Temp/eda_last_run.txt | tr '\n' ' ')"
  # re-open target document then wait
  cat > /c/Users/Lenovo/AppData/Local/Temp/eda_reopen.js <<EOF2
const doc0=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc0&&doc0.uuid==='a8a7bb9eb952a5f7') return 'ALREADY';
try{await eda.dmt_EditorControl.openDocument('a8a7bb9eb952a5f7');}catch(e){return 'OPENFAIL:'+e}
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
return 'REOPENED:'+(doc?doc.uuid:'null');
EOF2
  python -I D:/Document/tempPrj/74Series-CNN/tools/bridge_run.py /c/Users/Lenovo/AppData/Local/Temp/eda_reopen.js >/dev/null 2>&1
  sleep 20
done
echo "FAILED after 15 attempts"
exit 1

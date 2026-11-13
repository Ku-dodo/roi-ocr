import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const dir = new URL('../',import.meta.url);
const data=JSON.parse(await fs.readFile(new URL('data.json',import.meta.url),'utf8'));
const wb=Workbook.create();
function populate(name,values,widths,tableName){
  const s=wb.worksheets.add(name);
  s.showGridLines=false;
  const range=s.getRangeByIndexes(0,0,values.length,values[0].length);
  range.values=values;
  range.setNumberFormat('@');
  range.format.font={name:'Arial',size:11,color:'#172B4D'};
  range.format.rowHeight=29;
  range.format.verticalAlignment='center';
  range.format.wrapText=true;
  widths.forEach((w,i)=>s.getRangeByIndexes(0,i,values.length,1).format.columnWidthPx=w);
  const t=s.tables.add(range,true,tableName); t.showFilterButton=true;
  s.getRangeByIndexes(0,0,1,values[0].length).format={fill:'#24456A',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',rowHeight:34};
  s.freezePanes.freezeRows(1);
  return s;
}
const db=populate('L10N_DB',data.db,[220,90,430],'L10NDatabase');
db.tabColor='#24456A';
const audit=populate('검수이력',data.audit,[220,90,360,120,100,360,100,160,225,230,600],'ReviewHistory');
audit.getRange('K2:K57').format.rowHeight=70;
audit.getRange('G2:G57').conditionalFormats.addCustom('G2="수정"',{fill:'#FFF0C2',font:{color:'#7A4A00',bold:true}});
const rules=populate('작성기준',data.rules,[180,850],'TranscriptionRules');
rules.getRange('A2:B15').format.rowHeight=55;
const start=data.rules.length+3;
rules.getRangeByIndexes(start,0,data.sources.length,3).values=data.sources;
rules.getRangeByIndexes(start,0,data.sources.length,3).format.font={name:'Arial',size:11,color:'#172B4D'};
rules.getRangeByIndexes(start,0,1,3).format={fill:'#24456A',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:34};
rules.getRangeByIndexes(start+1,0,data.sources.length-1,3).format.rowHeight=65;
rules.getRangeByIndexes(start+1,0,data.sources.length-1,3).format.wrapText=true;
rules.getRangeByIndexes(start,2,data.sources.length,1).format.columnWidthPx=560;
wb.recalculate();
for(const [name,range] of [['L10N_DB','A1:C16'],['검수이력','A15:H29'],['작성기준','A1:B15']]){
 console.log((await wb.inspect({kind:'table',range:`'${name}'!${range}`,include:'values',tableMaxRows:3,tableMaxCols:8,maxChars:1500})).ndjson);
 const preview=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(new URL(`work/preview_${name}.png`,dir),new Uint8Array(await preview.arrayBuffer()));
}
for(const [label,range] of [['th','A30:C43'],['ch_tra','A44:C57']]){
 const preview=await wb.render({sheetName:'L10N_DB',range,scale:1,format:'png'});
 await fs.writeFile(new URL(`work/preview_${label}.png`,dir),new Uint8Array(await preview.arrayBuffer()));
}
const result=await SpreadsheetFile.exportXlsx(wb);
await result.save(new URL('L10N_DB.xlsx',dir).pathname.replace(/^\/(\w:)/,'$1'));
console.log('EXPORTED L10N_DB.xlsx');

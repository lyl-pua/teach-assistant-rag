const fs=require('fs');
const sh=fs.readFileSync(process.argv[2],'utf8');
console.log('shell脚本总长度=',sh.length);
const checks=[
  ['PAYLOAD_EOF_ZZZZ',2],
  ['MAIN_EOF_ZZZZ',2],
  ['/tmp/teach_payload.b64',3],
  ['location ^~ /teach',1],
  ['DEEPSEEK_API_KEY',2],
  ['ZHIPU_API_KEY',2],
  ['28.914',1],
  ['111.976',1],
];
for(const c of checks){
  const re=new RegExp(c[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g');
  const m=sh.match(re);
  const cnt=m?m.length:0;
  console.log((cnt===c[1]?'OK':'BAD').padEnd(5), 'need',c[1],'→',c[0].padEnd(30),'实际=',cnt);
}
// 统计 PAYLOAD_EOF_ZZZZ 中间有多少 base64 行
const s=sh.indexOf("<<'PAYLOAD_EOF_ZZZZ'");
const e=sh.indexOf("PAYLOAD_EOF_ZZZZ",s+1);
const block=sh.substring(s,e).trim();
console.log('payload块字符数=',block.length);
console.log('payload块首100=',block.slice(0,100).replace(/\\s+/g,' '));

const fs=require('fs');const B=require('./dsp.js');const tag=process.argv[2];const l=[0,1].flatMap(i=>fs.readFileSync(`aud_${tag}_${i}.jsonl`,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse));
const nm=id=>{const m=id.match(/^r(\d+)(off|next)$/);if(m)return B.EFFECTS[+m[1]].name+' '+m[2];const p=id.match(/^pa(\d)_(\d)([pm])$/);if(p)return B.ATTR[+p[1]].name+' '+'abcdef'[+p[2]]+(p[3]=='p'?'+':'-');const a=id.match(/^at(\d)$/);if(a)return 'add '+B.ATTR[+a[1]].name;return id;};
const nu=l.filter(x=>x.tag==='null'),r=l.filter(x=>x.tag!=='null');console.log('nulls false pass',nu.filter(x=>x.pass).map(x=>x.s+'/'+x.id+':'+x.score+x.why).join(' ')||'none','/'+nu.length);
for(const s of ['Swarm','SwarmStereo']){const q=r.filter(x=>x.s===s);console.log(s,'pass',q.filter(x=>x.pass).length+'/'+q.length,'FAIL',q.filter(x=>!x.pass).map(x=>nm(x.id)+' '+x.score+' '+x.why).join(', '));}
console.log('silent',l.filter(x=>x.lv<=-70).map(x=>x.id).join(' ')||'none');

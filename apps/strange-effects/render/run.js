// Strange Effects offline render: search a formula (or pick a system), then play it through the app's own engine
// and record the sound and what each frame shows.  Settings come from environment variables set by the workflow.
const fs=require('fs'),path=require('path');const B=require('./engine.js');
const E=process.env,out=E.SE_OUT||'out';fs.mkdirSync(out,{recursive:true});
const R=48000,FPS=30,SPF=R/FPS;const SECONDS=Math.max(10,Math.min(600,+E.SE_SECONDS||120));
const report=[];const log=(...a)=>{const t=a.join(' ');console.log(t);report.push(t);};
const specs={'Cavity':'cavity.json','Fibonacci ring':'fibonacci-ring.json','Feedback attractor':'feedback-attractor.json'};
let idx=-1,title='',field='';
const formula=(E.SE_FORMULA||'').trim();
if(formula){log('Formula:',formula);const t0=Date.now();
 const r=B.ND.searchAll(formula,(m,f)=>{})||B.formulaSearch(formula);log('Search took',((Date.now()-t0)/1000).toFixed(1)+' s');
 if(!r||!r.spec){log('Result: no attractor.',r&&r.fail||'');fs.writeFileSync(path.join(out,'report.md'),report.join('\n\n')+'\n');fs.writeFileSync(path.join(out,'status.txt'),'none');process.exit(0);}
 const def=r.spec.nd?B.ND.attr(r.spec,E.SE_LABEL||'Formula'):B.formulaAttr(r.spec,E.SE_LABEL||'Formula');B.ATTR.push(def);idx=B.ATTR.length-1;title=E.SE_LABEL||'Formula';field=r.spec.nd?r.spec.N+' variables':'one variable';
 fs.writeFileSync(path.join(out,'spec.json'),JSON.stringify(r.spec));
 log('Result: chaotic.',r.spec.nd?r.spec.N+' variables.':'One variable.','Exponents:',r.spec.L.join(', ')+'.','Dimension:',(r.spec.dimText||r.spec.dky)+'.','Settings:',r.spec.p.join(', ')+'.');}
else{const name=(E.SE_SYSTEM||'Fibonacci ring').trim();
 if(specs[name]){const sp=JSON.parse(fs.readFileSync(path.join(__dirname,'specs',specs[name]),'utf8'));B.ATTR.push(sp.nd?B.ND.attr(sp,name):B.formulaAttr(sp,name));idx=B.ATTR.length-1;}
 else idx=B.ATTR.findIndex(a=>a.name.toLowerCase()===name.toLowerCase());
 if(idx<0){log('Unknown system:',name,'— choose one of:',B.ATTR.map(a=>a.name).concat(Object.keys(specs)).join(', '));fs.writeFileSync(path.join(out,'report.md'),report.join('\n\n')+'\n');fs.writeFileSync(path.join(out,'status.txt'),'none');process.exit(0);}
 title=name;field=B.ATTR[idx].field||'';log('System:',name);}
const D=B.makeDSP(R);B.EFFECTS.forEach((e,i)=>D.route[i]=B.SWARM_ROUTES[e.id]??-1);
// routes point at the shown system, as the app does when only it is on
D.route.forEach((r,e)=>{if(r>=0&&r<100)D.route[e]=idx*3+r%3;});
D.V.forEach((v,i)=>v.on=i===idx);
const tone=(E.SE_TONE||'gentle').toLowerCase(),space=(E.SE_SPACE||'hall').toLowerCase(),rt=space==='room'?1.8:space==='cathedral'?9:4.5;
Object.assign(D,{swarm:true,nP:Math.max(1,Math.min(128,+E.SE_PARTICLES||4)),gentle:tone==='gentle',strange:tone==='strange',recv:true,cine:false,alive:false,rank:false,move:.35,hallRT:rt,hallSize:rt>8?1.5:rt>3?1:.7,pitch:1});
log('Tone:',tone+'. Particles:',D.nP+'. Space:',space+'. Length:',SECONDS+' s.');
const L=new Float32Array(SECONDS*R),Rr=new Float32Array(SECONDS*R);const fo=fs.openSync(path.join(out,'frames.jsonl'),'w');const v=D.V[idx];
const pre=[];for(let i=0;i+v.dim-1<v.pool.length;i+=v.dim)pre.push(+((v.pool[i]-v.c[0])/v.sc).toFixed(3),+((v.pool[i+1]-v.c[1])/v.sc).toFixed(3),+((v.pool[i+2]-v.c[2])/v.sc).toFixed(3));
const t0=Date.now();
for(let f=0;f<SECONDS*FPS;f++){const o=D.process(SPF);L.set(o.L,f*SPF);Rr.set(o.R,f*SPF);const rec={s:0,on:[idx],tr:{},pt:{}};if(f===0)rec.pre={[idx]:pre};
 if(o.trail[idx].length)rec.tr[idx]=o.trail[idx].map(x=>+x.toFixed(3));if(o.parts&&o.parts[idx])rec.pt[idx]=Array.from(o.parts[idx],x=>+x.toFixed(3));fs.writeSync(fo,JSON.stringify(rec)+'\n');
 if(f%(FPS*30)===0)console.log('rendered',f/FPS,'s of',SECONDS);}
fs.closeSync(fo);log('Render speed:',((SECONDS*1000)/(Date.now()-t0)).toFixed(2)+'× real time.','Broken samples:',(D.bad||0)+'.','Notes:',D.pings+'.');
const fi=R*1.5,fd=R*4;for(let i=0;i<fi;i++){const g=i/fi;L[i]*=g;Rr[i]*=g;}for(let i=0;i<fd;i++){const g=i/fd,j=L.length-1-i;L[j]*=g;Rr[j]*=g;}
const n=L.length,buf=Buffer.alloc(44+n*4);buf.write('RIFF',0);buf.writeUInt32LE(36+n*4,4);buf.write('WAVEfmt ',8);buf.writeUInt32LE(16,16);buf.writeUInt16LE(1,20);buf.writeUInt16LE(2,22);buf.writeUInt32LE(R,24);buf.writeUInt32LE(R*4,28);buf.writeUInt16LE(4,32);buf.writeUInt16LE(16,34);buf.write('data',36);buf.writeUInt32LE(n*4,40);
for(let i=0;i<n;i++){buf.writeInt16LE(Math.round(Math.max(-1,Math.min(1,L[i]))*32000),44+i*4);buf.writeInt16LE(Math.round(Math.max(-1,Math.min(1,Rr[i]))*32000),46+i*4);}
fs.writeFileSync(path.join(out,'audio.wav'),buf);
fs.writeFileSync(path.join(out,'scenes.json'),JSON.stringify({total:SECONDS,scenes:[[0,title+(field?' · '+field:'')+' · '+tone+' · '+D.nP+' particles']]}));
fs.writeFileSync(path.join(out,'report.md'),'# '+title+'\n\n'+report.join('\n\n')+'\n');fs.writeFileSync(path.join(out,'status.txt'),'ok');

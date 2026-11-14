// Minimal miniSEED 2 reader for the browser: fixed header + blockette 1000, encodings int16/int32/float32/float64,
// Steim-1 and Steim-2 (SEED Reference Manual v2.4, ch. 8 and appendix B). Returns [{start(ms), rate, samples}] per record.
function MSEED(){
function btime(v,o,le){const y=v.getUint16(o,le),d=v.getUint16(o+2,le),h=v.getUint8(o+4),m=v.getUint8(o+5),s=v.getUint8(o+6),f=v.getUint16(o+8,le);
 return Date.UTC(y,0,1)+(d-1)*864e5+h*36e5+m*6e4+s*1e3+f/10;}
function rateOf(f,m){let r=f>0?f:f<0?-1/f:0;if(m>0)r*=m;else if(m<0)r/=-m;return r;}
function steim(v,off,end,n,ver,le){const out=new Int32Array(n),diffs=[];let x0=0;
 const sx=(x,bits)=>x&(1<<(bits-1))?x-(1<<bits):x,take=(w,bits,cnt)=>{for(let j=cnt-1;j>=0;j--)diffs.push(sx((w>>>(j*bits))&((1<<bits)-1),bits));};
 for(let fo=off;fo+64<=end&&diffs.length<n+16;fo+=64){const w0=v.getUint32(fo,le);
  for(let i=1;i<16;i++){const c=(w0>>>(30-2*i))&3,w=v.getUint32(fo+4*i,le);
   if(fo===off&&i<=2){if(i===1)x0=w|0;continue;}
   if(c===0)continue;const wo=fo+4*i;if(c===1){if(le)for(let b=0;b<4;b++)diffs.push(v.getInt8(wo+b));else take(w,8,4);continue;}
   if(ver===1){if(c===2){if(le)diffs.push(v.getInt16(wo,true),v.getInt16(wo+2,true));else take(w,16,2);}else diffs.push(w|0);continue;}
   const dn=w>>>30;if(c===2){if(dn===1)take(w,30,1);else if(dn===2)take(w,15,2);else if(dn===3)take(w,10,3);}
   else{if(dn===0)take(w,6,5);else if(dn===1)take(w,5,6);else if(dn===2)take(w,4,7);}}}
 if(!n)return out;out[0]=x0;for(let i=1;i<n&&i<diffs.length;i++)out[i]=out[i-1]+diffs[i];return out;}
function parse(buf){const v=new DataView(buf),recs=[];let o=0;
 while(o+48<=buf.byteLength){let le=false;const yr=v.getUint16(o+20,false);if(yr<1900||yr>2100)le=true;
  const n=v.getUint16(o+30,le),rf=v.getInt16(o+32,le),rm=v.getInt16(o+34,le),dOff=v.getUint16(o+44,le);let bo=v.getUint16(o+46,le),enc=11,wle=le,len=4096;
  for(let guard=0;bo&&guard<8;guard++){const t=v.getUint16(o+bo,le),next=v.getUint16(o+bo+2,le);if(t===1000){enc=v.getUint8(o+bo+4);wle=v.getUint8(o+bo+5)===0;len=1<<v.getUint8(o+bo+6);}bo=next;}
  const rate=rateOf(rf,rm),st=btime(v,o+20,le),end=o+len,d=o+dOff;let s;
  if(enc===10||enc===11)s=steim(v,d,end,n,enc===10?1:2,wle);
  else{s=new Float64Array(n);for(let i=0;i<n;i++)s[i]=enc===1?v.getInt16(d+2*i,wle):enc===3?v.getInt32(d+4*i,wle):enc===4?v.getFloat32(d+4*i,wle):enc===5?v.getFloat64(d+8*i,wle):0;}
  recs.push({start:st,rate,samples:s,enc});o+=len;}
 return recs;}
return{parse};}
if(typeof module!=='undefined')module.exports=MSEED;

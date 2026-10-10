// Earthlight | oscillators, harmonic voices, mono bass and pan-safe ambience.
export const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
export function sm(param,value,ctx,time=.07){if(!param)return;const t=ctx.currentTime;param.cancelScheduledValues(t);param.setTargetAtTime(value,t,Math.max(.009,time));}
export function makeVoices(ctx,P,monoBus,atmos){
 const g=(n=1)=>{const x=ctx.createGain();x.gain.value=n;return x};
 const f=(type,Hz,q=.707)=>{let x=ctx.createBiquadFilter();x.type=type;x.frequency.value=Hz;x.Q.value=q;return x};
 const sources=[],start=ctx.currentTime+.035;
 const osc=(type,Hz)=>{let x=ctx.createOscillator();x.type=type;x.frequency.value=Hz;x.start(start);sources.push(x);return x};
 const root=osc('sine',P.root),subAmp=g(.45*P.sub),low=f('lowpass',P.subTone);
 root.connect(subAmp);subAmp.connect(low);low.connect(monoBus);
 const lfo=osc('sine',.036),swell=g(.07*P.subSwell);lfo.connect(swell);swell.connect(subAmp.gain);
 // Harmonics are exact integer multiples, never detuned sub-bass oscillators.
 const h2=osc('sine',P.root*2),h2gain=g(P.subHarm*.115),h2hp=f('highpass',82),h2lp=f('lowpass',340);
 h2.connect(h2gain);h2gain.connect(h2hp);h2hp.connect(h2lp);h2lp.connect(monoBus);
 const h3=osc('triangle',P.root*3),h3gain=g(P.warmth*.06),h3hp=f('highpass',120);
 h3.connect(h3gain);h3gain.connect(h3hp);h3hp.connect(monoBus);
 // Upper midrange harmonic body. Protected by two highpasses before spatial effects.
 const bodyAmp=g(P.body*.14),bodyDrive=g(1+P.bodyDrive*5),bodyHP=f('highpass',180),bodyHP2=f('highpass',180),bodyLP=f('lowpass',P.bodyCutoff);
 const shape=ctx.createWaveShaper(),curve=new Float32Array(1024);
 for(let i=0;i<curve.length;i++){let x=i/(curve.length-1)*2-1;curve[i]=Math.tanh(1.6*x)/Math.tanh(1.6);}
 shape.curve=curve;shape.oversample='2x';
 const bo1=osc('sawtooth',P.root*3),bo2=osc('triangle',P.root*4),v1=g(.45),v2=g(.55);
 bo1.connect(v1);bo2.connect(v2);v1.connect(bodyDrive);v2.connect(bodyDrive);bodyDrive.connect(shape);shape.connect(bodyHP);bodyHP.connect(bodyHP2);bodyHP2.connect(bodyLP);bodyLP.connect(bodyAmp);bodyAmp.connect(atmos);
 // Independent chord tones, never delayed or polarity-inverted copies.
 const padGain=g(P.pad*.58),padHP=f('highpass',195),padHP2=f('highpass',195),padLP=f('lowpass',P.padBrightness);
 padGain.connect(padHP);padHP.connect(padHP2);padHP2.connect(padLP);padLP.connect(atmos);
 const voicings=[[24,31,36,39,43],[29,36,41,45,48],[24,31,36,39,43],[34,41,46,50,53]];
 const panPositions=[-.86,.66,.12,-.68,.92],pads=[];
 function hrtf(){try{let p=ctx.createPanner();p.panningModel='HRTF';p.distanceModel='inverse';p.refDistance=2;p.maxDistance=35;p.rolloffFactor=.2;p.setPosition(0,0,-3);return p}catch(_){return null}}
 for(let i=0;i<5;i++){
  const x=osc(i%2?'triangle':'sawtooth',P.root*Math.pow(2,voicings[0][i]/12));
  const env=g(.039+(i>1?.09:.038)*P.padDensity),cut1=f('highpass',205),cut2=f('highpass',205),pan=ctx.createStereoPanner?ctx.createStereoPanner():g(1),dry=g(1),bin=hrtF=>hrtF?g(0):null;
  const hp=hrtf(),hGate=bin(hp);
  x.connect(env);env.connect(cut1);cut1.connect(cut2);
  cut2.connect(pan);pan.connect(dry);dry.connect(padGain);
  if(hp){cut2.connect(hp);hp.connect(hGate);hGate.connect(padGain)}
  pads.push({o:x,env,pan,dry,hp,hGate,i});
 }
 const shimmer=osc('sine',P.root*8),shGain=g(P.shimmer*.032),shHP=f('highpass',390);
 shimmer.connect(shGain);shGain.connect(shHP);shHP.connect(atmos);
 let chordIndex=0,mode='speaker',lastChord=ctx.currentTime;
 function chord(i,gliss=false){
  chordIndex=((i%4)+4)%4;lastChord=ctx.currentTime;
  for(const x of pads){let pitch=P.root*Math.pow(2,voicings[chordIndex][x.i]/12);if(gliss)x.o.frequency.setValueAtTime(pitch*Math.pow(2,.18/12),ctx.currentTime);sm(x.o.frequency,pitch,ctx,Math.max(.10,P.glide/3));}
 }
 function panUpdate(t=0){for(const x of pads){
   let theta=t*(.05+P.motion*.14)+x.i*2.31;
   let value=clamp(P.width*(panPositions[x.i]*.6+Math.sin(theta)*P.orbit*.38),-.96,.96);
   if(x.pan.pan)sm(x.pan.pan,value,ctx,.19);
   if(x.hp){sm(x.hp.positionX,Math.sin(theta)*P.width*P.orbit*3.0,ctx,.20);sm(x.hp.positionZ,-2.5+Math.cos(theta)*P.orbit*.5,ctx,.20);}
 }}
 function spatial(next){mode=next;for(const x of pads){let binaural=next==='headphone'&&!!x.hp;sm(x.dry.gain,binaural?0:1,ctx,.11);if(x.hGate)sm(x.hGate.gain,binaural?1:0,ctx,.11);}panUpdate(ctx.currentTime)}
 function apply(k,v){switch(k){
  case'root':for(const [node,m] of [[root,1],[h2,2],[h3,3],[bo1,3],[bo2,4],[shimmer,8]])sm(node.frequency,v*m,ctx,.11);chord(chordIndex);break;
  case'sub':sm(subAmp.gain,.45*v,ctx);break;
  case'subHarm':sm(h2gain.gain,.115*v,ctx);break;
  case'warmth':sm(h3gain.gain,.06*v,ctx);break;
  case'subTone':sm(low.frequency,v,ctx);break;
  case'subSwell':sm(swell.gain,.07*v,ctx);break;
  case'body':sm(bodyAmp.gain,.14*v,ctx);break;
  case'bodyDrive':sm(bodyDrive.gain,1+5*v,ctx);break;
  case'bodyCutoff':sm(bodyLP.frequency,v,ctx);break;
  case'pad':sm(padGain.gain,.58*v,ctx);break;
  case'padBrightness':sm(padLP.frequency,v,ctx);break;
  case'padDensity':for(const x of pads)sm(x.env.gain,.039+(x.i>1?.09:.038)*v,ctx);break;
  case'shimmer':sm(shGain.gain,.032*v,ctx);break;
  case'width':case'orbit':panUpdate(ctx.currentTime);break;
  case'glide':chord(chordIndex,true);break;
 }}
 function update(t){const now=ctx.currentTime;
  if(now-lastChord>=P.dwell)chord(chordIndex+1);
  for(const x of pads){let depth=P.motion*.21,amp=.039+(x.i>1?.09:.038)*P.padDensity;
    sm(x.env.gain,amp*(1+depth*Math.sin(t*(.13+x.i*.011)+x.i*1.35)),ctx,.32)}
  sm(padLP.frequency,P.padBrightness*(1+P.motion*.15*Math.sin(t*.17)),ctx,.28);
  panUpdate(t);
 }
 chord(0);panUpdate(0);
 return {apply,spatial,chord,update,stop:()=>{sources.forEach(x=>{try{x.stop();x.disconnect()}catch(_){}})},pads,get chordIndex(){return chordIndex},sources,sub:root};
}
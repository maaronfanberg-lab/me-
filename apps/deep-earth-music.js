// Earthlight music conductor: original, evolving melodic ambient instrumental.
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const chordPitches=[
 [24,27,31,38,43], // Fm(add9)
 [24,29,33,36,41], // Bb/F
 [24,27,31,34,39], // Ab/F
 [24,29,34,38,41], // Eb/F
 [24,27,31,38,43],
 [24,29,33,36,41],
 [24,29,34,38,41],
 [24,27,31,38,43],
 [24,27,31,38,43],
 [24,27,31,34,39],
 [24,29,33,36,41],
 [24,29,34,38,41],
 [24,27,31,38,43],
 [24,29,34,38,41],
 [24,29,33,36,41],
 [24,27,31,38,43]
];
// Beat offsets within each four-bar section, all intervals relative to F4.
// These are newly composed phrases, never taken from a recording.
const sections=[
 {name:'I · BLUE HORIZON',level:.75,pulse:.32,notes:[
 [0,7,2.55],[3,10,.75],[4,12,2.6],[8,10,1.4],[9.5,9,.5],[10.25,7,1.75],
 [12.5,3,1.3],[14,2,1.45]]},
 {name:'II · OPEN SKY',level:.95,pulse:.70,notes:[
 [0,9,2.3],[3,7,.8],[4,12,2.35],[7,14,.65],[8,15,1.75],[10,14,.8],
 [11,12,.8],[12,9,2.65],[15,7,.65]]},
 {name:'III · THE SUMMIT',level:1.0,pulse:.90,notes:[
 [0,12,1.25],[1.5,15,2.0],[4,14,1.0],[5.5,12,1.4],[7.5,10,.9],
 [8.5,9,.8],[9.5,10,1.1],[11,12,1.65],[13,15,1.75],[15,12,.8]]},
 {name:'IV · AFTERGLOW',level:.65,pulse:.27,notes:[
 [0,7,2.7],[3,10,.7],[4,12,3.5],[8.4,10,1.6],[11,7,2.3]]}
];
export const musicSections=sections.map(s=>s.name);
const makeGain=(ctx,x=1)=>{const g=ctx.createGain();g.gain.value=x;return g};
const makeFilter=(ctx,type,hz)=>{const f=ctx.createBiquadFilter();f.type=type;f.frequency.value=hz;f.Q.value=.707;return f};
export function createMusic(ctx,P,atmos,padVoices){
 const leadBus=makeGain(ctx,1.30*(P.lead??.8)*(P.musicDynamics??.82)),pulseBus=makeGain(ctx,.49*(P.pulse??.55)*(P.musicDynamics??.82));
 const leadTone=makeFilter(ctx,'lowpass',1050+(P.expression??.6)*2000);
 const guardA=makeFilter(ctx,'highpass',205),guardB=makeFilter(ctx,'highpass',205);
 leadBus.connect(leadTone);leadTone.connect(guardA);pulseBus.connect(guardA);guardA.connect(guardB);guardB.connect(atmos);
 let origin=ctx.currentTime+.16,cursor=0,paused=false,voiceCount=0,part=0,lastChord=-1,lastTime=0;
 let events=0,leadEvents=0,pulseEvents=0,mode='auto',loop=0,tracked=[];
 const bpm=()=>clamp(P.tempo||70,48,92),beatDuration=()=>60/bpm();
 const noteHz=(semitones)=>P.root*8*Math.pow(2,semitones/12);
 // Every note is created as a genuine oscillator voice with musical articulation.
 function note(t,semitones,length,amount,type='lead',accent=1){
  if(t<ctx.currentTime-.04)return;
  const secs=length*beatDuration(),isLead=type==='lead';
  const overall=1;
  if(overall<.003)return;
  const noteFreq=noteHz(semitones),bright=P.expression??.6;
  const a=ctx.createOscillator(),b=ctx.createOscillator(),ag=makeGain(ctx,isLead?.72:.24),bg=makeGain(ctx,isLead?.30:.7);
  a.type=isLead?'sawtooth':'triangle';b.type='sine';a.frequency.value=noteFreq;b.frequency.value=noteFreq;
  const sum=makeGain(ctx),env=makeGain(ctx,0),lp=makeFilter(ctx,'lowpass',isLead?1500:950),
        pan=ctx.createStereoPanner?ctx.createStereoPanner():makeGain(ctx);
  const hp1=makeFilter(ctx,'highpass',220),hp2=makeFilter(ctx,'highpass',220);
  if(pan.pan)pan.pan.value=(isLead?.11:-.14)*clamp(P.width??.6,0,1);
  a.connect(ag);b.connect(bg);ag.connect(sum);bg.connect(sum);
  sum.connect(lp);lp.connect(env);env.connect(hp1);hp1.connect(hp2);hp2.connect(pan);
  pan.connect(isLead?leadBus:pulseBus);
  let attack=isLead?.05:.035,release=isLead?.60:.36;
  let value=(isLead?.26:.17)*overall*amount*accent*(P.musicDynamics??.82);
  value=clamp(value,0,.33);
  env.gain.setValueAtTime(0,t);
  env.gain.linearRampToValueAtTime(value,t+attack);
  env.gain.setTargetAtTime(value*(isLead?.68:.46),t+attack,.2);
  const releaseStart=t+Math.max(attack+.15,secs-(isLead?.38:.17));
  env.gain.setTargetAtTime(.000001,releaseStart,isLead?.29:.15);
  lp.frequency.setValueAtTime(isLead?1400+bright*2200:780+bright*770,t);
  lp.frequency.setTargetAtTime(isLead?700+bright*1200:660+bright*430,t+.14,isLead?.65:.16);
  if(isLead&&secs>.85){
   a.detune.setValueAtTime(-3,t);a.detune.linearRampToValueAtTime(0,t+.11);
   // Oscillator pitch stays unison; slow detune after attack is subtle vibrato.
   a.detune.setTargetAtTime(Math.sin(semitones*1.7)*2.3,t+.4,.5);
  }
  const end=t+secs+Math.max(1.8,release*3.2);
  a.start(t);b.start(t);a.stop(end);b.stop(end);
  voiceCount+=2;events++;if(isLead)leadEvents++;else pulseEvents++;
  let cleaned=false;const clean=()=>{if(cleaned)return;cleaned=true;try{a.disconnect();b.disconnect();ag.disconnect();bg.disconnect();sum.disconnect();env.disconnect();lp.disconnect();hp1.disconnect();hp2.disconnect();pan.disconnect()}catch(_){}};
  a.onended=clean;
  tracked.push({a,b,end});if(tracked.length>180)tracked=tracked.filter(v=>v.end>ctx.currentTime);
 }
 function chord(bar){
   if(bar===lastChord)return;
   lastChord=bar;
   if(padVoices&&padVoices.chord){padVoices.chord(bar%4,false,chordPitches[bar%16]);}
 }
 function pulsePattern(bar,beatWithinBar){
  const i=bar%16,chord=chordPitches[i],index=Math.round(beatWithinBar*2)%5;
  return chord[[2,3,2,1,3][index]];
 }
 function scheduleBar(b){
  const bar=b%16,sectionIndex=Math.floor(bar/4),section=sections[sectionIndex],barStart=origin+b*4*beatDuration();
  if(b%4===0)part=sectionIndex;
  chord(bar);
  // Expressive lead phrases appear early and repeat with intentional space.
  const sectionBeat=bar%4*4;
  for(const [at,pitch,duration] of section.notes){
   if(at<sectionBeat||at>=sectionBeat+4)continue;
   const loopNumber=Math.floor(b/16);
   let variance=(loopNumber%3===2&&at===8.4)?-2:0;
   const atTime=barStart+(at-sectionBeat)*beatDuration();
   note(atTime,pitch+variance,duration,section.level,'lead');
  }
  // Gentle ostinato: recognizable pulse rather than a bass drum.
  const steps=P.pulseDensity===0?0:P.pulseDensity<.38?2:P.pulseDensity<.75?4:8;const pattern=steps===2?[0,2.5]:steps===4?[0,1.5,2.5,3.5]:[0,.5,1.5,2,2.5,3,3.5,3.75];
  for(let n=0;n<steps;n++){
   const localBeat=pattern[n],atTime=barStart+localBeat*beatDuration();
   const pitch=pulsePattern(bar,localBeat)-36;
   const dynamics=section.pulse*[1.12,.68,.82,.62,.78,.66,.74,.57][n];
   note(atTime,pitch,Math.min(.9,3.2/steps),dynamics,'pulse');
  }
 }
 // Always quantize to bar grid. Dedicated lookahead runs off the audio clock.
 function tick(){
  if(paused)return;
  const horizon=ctx.currentTime+1.0;
  const d=beatDuration();
  if(ctx.currentTime-origin>0&&origin+cursor*4*d<ctx.currentTime-.5){
   cursor=Math.floor((ctx.currentTime-origin)/(4*d));
  }
  while(origin+cursor*4*d<horizon && cursor<100000){
   scheduleBar(cursor);cursor++;
  }
 }
 function setParam(id,v){
  if(id==='tempo'){const elapsed=Math.max(0,ctx.currentTime-origin),old=lastTime||beatDuration();const beat=elapsed/old;origin=ctx.currentTime-beat*beatDuration();lastTime=beatDuration();cursor=Math.max(cursor,Math.floor((ctx.currentTime-origin)/(4*lastTime))); }
  if(id==='section'){if(v>0){const selected=clamp(Math.round(v)-1,0,3);origin=ctx.currentTime+.08;cursor=selected*4;lastChord=-1;}else{origin=ctx.currentTime+.08;cursor=0;lastChord=-1;}}
  if(id==='lead')leadBus.gain.setTargetAtTime(1.30*v*P.musicDynamics,ctx.currentTime,.07);
  if(id==='pulse'||id==='pulseDensity')pulseBus.gain.setTargetAtTime((P.pulseDensity===0?0:.49*P.pulse*P.musicDynamics),ctx.currentTime,.07);
  if(id==='musicDynamics'){leadBus.gain.setTargetAtTime(1.30*P.lead*v,ctx.currentTime,.06);pulseBus.gain.setTargetAtTime((P.pulseDensity===0?0:.49*P.pulse*v),ctx.currentTime,.06);}
  if(id==='expression')leadTone.frequency.setTargetAtTime(1050+v*2000,ctx.currentTime,.06);
 }
 lastTime=beatDuration();
 // Essential: first notes are scheduled even for offline simulations without JS timers.
 tick();
 return {tick,setParam,get section(){return sections[part].name},get stats(){return {notes:events,lead:leadEvents,pulse:pulseEvents,bar:cursor,section:sections[part].name}},get sections(){return sections},pause(){paused=true},resume(){paused=false;tick()},stop(){paused=true;for(const v of tracked){try{v.a.stop();v.b.stop()}catch(_){}}}};
}

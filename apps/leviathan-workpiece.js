/* LEVIATHAN WORKPIECE I — THE CATHEDRAL MACHINE
   30-minute original generative score for the existing LEVIATHAN engine plus
   a lightweight WebAudio orchestra. The existing instrument code is untouched.
*/
(()=>{
  const BPM=112;
  const BEAT=60/BPM;
  const BAR=BEAT*4;
  const TOTAL=30*60;
  const TOTAL_BARS=840; // exactly 30:00 at 112 BPM
  const LOOK=0.32;

  const W={
    running:false,paused:false,timer:null,bar:0,nextBar:0,startCtx:0,
    sources:new Set(),timeouts:new Set(),fxReady:false,fxCtx:null,
    musicBus:null,drumBus:null,pianoBus:null,leadBus:null,rev:null,revGain:null,
    delay:null,delayFeedback:null,noise:null,
    playBtn:null,pauseBtn:null,stopBtn:null,status:null,clock:null,fill:null,section:null
  };

  const HARM=[
    {name:'B minor add9', root:35, piano:[59,62,66,73], pad:[47,54,59,62]},
    {name:'G major 7',    root:31, piano:[55,59,62,66], pad:[43,50,55,59]},
    {name:'D add9',       root:38, piano:[57,62,64,66], pad:[50,57,62,66]},
    {name:'A add9',       root:33, piano:[57,61,64,71], pad:[45,52,57,61]},
    {name:'E minor 7',    root:28, piano:[55,59,62,64], pad:[40,47,50,55]},
    {name:'G major',      root:31, piano:[55,59,62,67], pad:[43,50,55,59]},
    {name:'D/F#',         root:30, piano:[54,57,62,66], pad:[42,50,57,62]},
    {name:'A sus2',       root:33, piano:[57,59,64,69], pad:[45,52,57,59]}
  ];

  const MOTIF_A=[
    71,null,74,76,78,76,74,71,
    69,null,71,74,66,null,69,71,
    74,76,78,81,78,76,74,71,
    69,71,74,76,74,null,71,null
  ];
  const MOTIF_B=[
    66,69,71,null,74,71,69,66,
    71,74,76,78,76,74,71,null,
    78,81,83,81,78,76,74,71,
    69,null,71,74,76,74,71,null
  ];
  const MOTIF_C=[
    74,76,78,null,81,78,76,74,
    71,74,76,71,69,null,66,69,
    71,74,78,76,74,71,69,66,
    69,71,74,76,74,null,71,null
  ];

  const SECTIONS=[
    {a:0,b:112, name:'I · Nave — aluminum piano alone'},
    {a:112,b:224,name:'II · Pulse enters'},
    {a:224,b:336,name:'III · First lift'},
    {a:336,b:448,name:'IV · Open sky'},
    {a:448,b:532,name:'V · Cathedral break'},
    {a:532,b:672,name:'VI · Dark machinery'},
    {a:672,b:784,name:'VII · Final ascent'},
    {a:784,b:840,name:'VIII · Return to the nave'}
  ];

  function sectionFor(bar){return SECTIONS.find(s=>bar>=s.a&&bar<s.b)||SECTIONS[SECTIONS.length-1];}
  function chordFor(bar){return HARM[bar%HARM.length];}
  function hz(m){return 440*Math.pow(2,(m-69)/12);}
  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function fmt(sec){sec=Math.max(0,Math.floor(sec));const m=Math.floor(sec/60),s=sec%60;return m+':'+String(s).padStart(2,'0');}

  function keep(src){
    W.sources.add(src);
    src.addEventListener('ended',()=>W.sources.delete(src),{once:true});
    return src;
  }
  function later(t,fn){
    let id=null;
    const fire=()=>{
      if(id!==null)W.timeouts.delete(id);
      if(!W.running)return;
      const ms=(t-ctx.currentTime)*1000;
      if(ms>8||W.paused){id=setTimeout(fire,Math.min(80,Math.max(20,ms)));W.timeouts.add(id);return;}
      fn();
    };
    id=setTimeout(fire,Math.min(80,Math.max(0,(t-ctx.currentTime)*1000)));W.timeouts.add(id);return id;
  }

  function makeNoise(){
    const n=Math.floor(ctx.sampleRate*1.0),b=ctx.createBuffer(1,n,ctx.sampleRate),d=b.getChannelData(0);
    for(let i=0;i<n;i++)d[i]=Math.random()*2-1;
    return b;
  }
  function makeIR(seconds=5.8){
    const n=Math.floor(ctx.sampleRate*seconds),b=ctx.createBuffer(2,n,ctx.sampleRate);
    for(let c=0;c<2;c++){
      const d=b.getChannelData(c);
      for(let i=0;i<n;i++){
        const x=i/n,decay=Math.pow(1-x,2.55);
        const early=(i<ctx.sampleRate*.16)?1.18:1;
        d[i]=(Math.random()*2-1)*decay*early;
      }
    }
    return b;
  }

  function setupFx(){
    if(W.fxReady&&W.fxCtx===ctx)return;
    W.fxReady=true;W.fxCtx=ctx;
    const target=comp||master||ctx.destination;

    W.musicBus=ctx.createGain();W.musicBus.gain.value=.82;
    W.drumBus=ctx.createGain();W.drumBus.gain.value=.70;
    W.pianoBus=ctx.createGain();W.pianoBus.gain.value=.95;
    W.leadBus=ctx.createGain();W.leadBus.gain.value=.72;

    const dry=ctx.createGain();dry.gain.value=.80;
    W.rev=ctx.createConvolver();W.rev.buffer=makeIR();
    W.revGain=ctx.createGain();W.revGain.gain.value=.47;

    W.delay=ctx.createDelay(1.0);W.delay.delayTime.value=BEAT*.75;
    W.delayFeedback=ctx.createGain();W.delayFeedback.gain.value=.24;
    const delayWet=ctx.createGain();delayWet.gain.value=.28;

    W.pianoBus.connect(W.musicBus);
    W.leadBus.connect(W.musicBus);
    W.leadBus.connect(W.delay);W.delay.connect(W.delayFeedback);W.delayFeedback.connect(W.delay);W.delay.connect(delayWet);delayWet.connect(W.musicBus);
    W.musicBus.connect(dry);W.musicBus.connect(W.rev);W.rev.connect(W.revGain);
    dry.connect(target);W.revGain.connect(target);W.drumBus.connect(target);
    W.noise=makeNoise();
  }

  function envGain(t,peak,attack,release,end){
    const g=ctx.createGain();
    g.gain.setValueAtTime(.0001,t);
    g.gain.exponentialRampToValueAtTime(Math.max(.0002,peak),t+attack);
    g.gain.exponentialRampToValueAtTime(.0001,Math.max(t+attack+.01,end-release));
    g.gain.setValueAtTime(.0001,end);
    return g;
  }

  // Bright modal strike: intentionally metallic rather than a sampled piano.
  function aluminumPiano(m,t,vel=.7,tail=4.6){
    const f=hz(m),rat=[1,2.01,4.08],amp=[1,.36,.13],dec=[1,.63,.34];
    for(let i=0;i<rat.length;i++){
      const end=t+tail*dec[i]+.12;
      const o=keep(ctx.createOscillator()),g=envGain(t,vel*.062*amp[i],.006,.08,end);
      o.type='sine';o.frequency.setValueAtTime(f*rat[i],t);
      o.connect(g);g.connect(W.pianoBus);o.start(t);o.stop(end+.02);
    }
    if(vel>.48){
      const s=keep(ctx.createBufferSource()),hp=ctx.createBiquadFilter(),g=envGain(t,vel*.010,.003,.035,t+.055);
      s.buffer=W.noise;hp.type='highpass';hp.frequency.value=3200;s.connect(hp);hp.connect(g);g.connect(W.pianoBus);s.start(t);s.stop(t+.06);
    }
  }

  function padNote(m,t,dur,vel=.42){
    const f=hz(m),end=t+dur+.8;
    [-7,7].forEach(det=>{
      const o=keep(ctx.createOscillator()),g=ctx.createGain(),lp=ctx.createBiquadFilter();
      o.type='triangle';o.frequency.setValueAtTime(f,t);o.detune.value=det;
      lp.type='lowpass';lp.frequency.value=1300;
      g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(vel*.016,t+.8);g.gain.setValueAtTime(vel*.016,t+Math.max(.9,dur-.8));g.gain.exponentialRampToValueAtTime(.0001,end);
      o.connect(lp);lp.connect(g);g.connect(W.musicBus);o.start(t);o.stop(end+.02);
    });
  }

  function leadNote(m,t,dur,vel=.55){
    const f=hz(m),end=t+dur+.22;
    const lp=ctx.createBiquadFilter();lp.type='lowpass';lp.Q.value=.7;lp.frequency.setValueAtTime(2400,t);lp.frequency.linearRampToValueAtTime(5200,t+.08);
    const g=ctx.createGain();g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(vel*.032,t+.025);g.gain.setValueAtTime(vel*.028,t+Math.max(.04,dur*.72));g.gain.exponentialRampToValueAtTime(.0001,end);
    ['sawtooth','sine'].forEach((type,i)=>{
      const o=keep(ctx.createOscillator());o.type=type;o.frequency.setValueAtTime(f,t);o.detune.value=i?5:-5;o.connect(lp);o.start(t);o.stop(end+.02);
    });
    lp.connect(g);g.connect(W.leadBus);
  }

  function arpNote(m,t,dur=.18,vel=.30){
    const o=keep(ctx.createOscillator()),g=envGain(t,vel*.024,.008,.06,t+dur),lp=ctx.createBiquadFilter();
    o.type='triangle';o.frequency.setValueAtTime(hz(m),t);lp.type='lowpass';lp.frequency.value=3600;o.connect(lp);lp.connect(g);g.connect(W.leadBus);o.start(t);o.stop(t+dur+.02);
  }

  function bronzeBell(m,t,vel=.35){
    const f=hz(m),rat=[1,1.49,2.18,3.06],amp=[1,.46,.25,.11];
    rat.forEach((r,i)=>{
      const end=t+5.8/(1+i*.4),o=keep(ctx.createOscillator()),g=envGain(t,vel*.028*amp[i],.008,.10,end);
      o.type='sine';o.frequency.setValueAtTime(f*r,t);o.connect(g);g.connect(W.musicBus);o.start(t);o.stop(end+.02);
    });
  }

  function kick(t,vel=.8){
    const o=keep(ctx.createOscillator()),g=ctx.createGain();o.type='sine';
    o.frequency.setValueAtTime(118,t);o.frequency.exponentialRampToValueAtTime(45,t+.14);
    g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(vel*.24,t+.006);g.gain.exponentialRampToValueAtTime(.0001,t+.28);
    o.connect(g);g.connect(W.drumBus);o.start(t);o.stop(t+.3);
  }
  function hat(t,vel=.5,open=false){
    const s=keep(ctx.createBufferSource()),hp=ctx.createBiquadFilter(),g=ctx.createGain(),dur=open?.18:.055;
    s.buffer=W.noise;hp.type='highpass';hp.frequency.value=open?6500:8200;
    g.gain.setValueAtTime(vel*.034,t);g.gain.exponentialRampToValueAtTime(.0001,t+dur);
    s.connect(hp);hp.connect(g);g.connect(W.drumBus);s.start(t);s.stop(t+dur+.01);
  }
  function snare(t,vel=.6){
    const s=keep(ctx.createBufferSource()),bp=ctx.createBiquadFilter(),g=ctx.createGain();
    s.buffer=W.noise;bp.type='bandpass';bp.frequency.value=1750;bp.Q.value=.7;
    g.gain.setValueAtTime(vel*.075,t);g.gain.exponentialRampToValueAtTime(.0001,t+.16);
    s.connect(bp);bp.connect(g);g.connect(W.drumBus);s.start(t);s.stop(t+.17);
  }

  function wub(m,t,dur,vel=.62,rate=4){
    const f=hz(m),end=t+dur+.08,lp=ctx.createBiquadFilter(),g=ctx.createGain();
    lp.type='lowpass';lp.Q.value=7;g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(vel*.060,t+.02);g.gain.setValueAtTime(vel*.055,t+Math.max(.04,dur-.07));g.gain.exponentialRampToValueAtTime(.0001,end);
    const steps=Math.max(2,Math.floor(dur/(BEAT/rate)));
    for(let i=0;i<=steps;i++){
      const tt=t+(dur*i/steps),fc=i%2?470:1500;
      if(i===0)lp.frequency.setValueAtTime(fc,tt);else lp.frequency.linearRampToValueAtTime(fc,tt);
    }
    ['sawtooth','triangle'].forEach((type,i)=>{const o=keep(ctx.createOscillator());o.type=type;o.frequency.value=f*(i?1:.5);o.detune.value=i?6:-6;o.connect(lp);o.start(t);o.stop(end+.02);});
    lp.connect(g);g.connect(W.musicBus);
    const sub=keep(ctx.createOscillator()),sg=envGain(t,vel*.055,.01,.05,end);sub.type='sine';sub.frequency.value=f*.5;sub.connect(sg);sg.connect(W.musicBus);sub.start(t);sub.stop(end+.02);
  }

  function leviathan(m,t,dur=.72*BAR){
    if(typeof noteOn!=='function'||typeof noteOff!=='function')return;
    const f=hz(m),semi=12*Math.log2(f/fOpen())-S.octave*12;
    later(t,()=>noteOn(semi));later(t+dur,()=>noteOff(semi));
  }

  function pianoArp(ch,t,mode='sparse',vel=.68){
    const p=ch.piano;
    if(mode==='sparse'){
      [[0,0],[1.25,1],[2.1,2],[3.05,3]].forEach(([b,i])=>aluminumPiano(p[i],t+b*BEAT,vel,4.7));
    }else if(mode==='full'){
      const seq=[0,1,2,3,2,1,3,2];
      seq.forEach((i,k)=>aluminumPiano(p[i],t+k*BEAT/2,vel*(k%2?.82:1),3.4));
    }else{
      p.forEach((m,i)=>aluminumPiano(m,t+i*.035,vel,5.2));
    }
  }

  function padChord(ch,t,bars=2,vel=.38){ch.pad.forEach((m,i)=>padNote(m,t+i*.025,BAR*bars,vel));}
  function tranceArp(ch,t,vel=.30){const seq=[0,1,2,3,2,1,3,1];seq.forEach((i,k)=>arpNote(ch.piano[i]+12,t+k*BEAT/2,BEAT*.34,vel));}
  function fullDrums(t,intensity=.75){for(let b=0;b<4;b++)kick(t+b*BEAT,intensity);for(let k=0;k<8;k++)hat(t+(k+.5)*BEAT/2,.34+(k%2)*.08,k===7);snare(t+BEAT,.52);snare(t+BEAT*3,.55);}
  function pulseDrums(t,intensity=.48){kick(t,intensity);kick(t+BEAT*2,intensity*.82);hat(t+BEAT*.5,.28);hat(t+BEAT*2.5,.30);}
  function dubDrums(t){kick(t,.78);kick(t+BEAT*2.72,.55);snare(t+BEAT*2,.72);for(let k=0;k<8;k++)if(k!==4)hat(t+k*BEAT/2+.03,.25+(k%2)*.09,k===7);}

  function leadPhrase(t,variant='A',vel=.56){
    const a=variant==='B'?MOTIF_B:variant==='C'?MOTIF_C:MOTIF_A;
    a.forEach((m,i)=>{if(m!==null)leadNote(m,t+i*BEAT/2,BEAT*.43,vel*(i%8===4?1.10:1));});
  }

  function scheduleBar(bar,t){
    const ch=chordFor(bar),sec=sectionFor(bar),local=bar-sec.a;
    if(W.section)W.section.textContent=sec.name;

    // I — four minutes of cathedral space. Piano first, then barely-there air.
    if(sec.a===0){
      if(bar%2===0)pianoArp(ch,t,'sparse',.74);
      if(bar>=56&&bar%4===0)padChord(ch,t,4,.20);
      if(bar>=84&&bar%8===0)bronzeBell(ch.piano[2]+12,t+BEAT*2.7,.22);
      if(bar>=96&&bar%4===0)leviathan(ch.root,t,BAR*1.45);
      return;
    }

    // II — pulse grows underneath the cathedral without taking it over.
    if(sec.a===112){
      pianoArp(ch,t,bar%2?'sparse':'full',.66);
      if(bar%2===0)padChord(ch,t,2,.25);
      pulseDrums(t,local<48?.32:.48);
      if(bar%2===0)leviathan(ch.root,t,BAR*.78);
      if(local>64)tranceArp(ch,t,.17);
      if(local===88)leadPhrase(t,'A',.34);
      return;
    }

    // III — first unmistakable uplifting trance section.
    if(sec.a===224){
      pianoArp(ch,t,'full',.60);if(bar%2===0)padChord(ch,t,2,.28);fullDrums(t,.58);tranceArp(ch,t,.24);leviathan(ch.root,t,BAR*.72);
      if(local%16===0)leadPhrase(t,(local/16)%2?'B':'A',.46);
      return;
    }

    // IV — the broad, soaring statement.
    if(sec.a===336){
      pianoArp(ch,t,'full',.58);if(bar%2===0)padChord(ch,t,2,.34);fullDrums(t,.72);tranceArp(ch,t,.31);leviathan(ch.root,t,BAR*.76);
      if(local%8===0)leadPhrase(t,local%24===0?'C':'A',.62);
      if(local%16===12)bronzeBell(ch.piano[3]+12,t+BEAT*2.5,.20);
      return;
    }

    // V — everything falls away into the building again.
    if(sec.a===448){
      if(bar%2===0)pianoArp(ch,t,local<40?'chord':'sparse',.72);
      if(bar%4===0)padChord(ch,t,4,.26);
      if(bar%8===4)bronzeBell(ch.piano[1]+12,t+BEAT*1.8,.33);
      if(local>56&&bar%4===0)leviathan(ch.root,t,BAR*1.25);
      if(local>68&&bar%2===0)pulseDrums(t,.22);
      return;
    }

    // VI — dubstep influence: half-time, moving filters, still harmonically beautiful.
    if(sec.a===532){
      dubDrums(t);if(bar%2===0)pianoArp(ch,t,'sparse',.55);if(bar%4===0)padChord(ch,t,4,.20);leviathan(ch.root,t,BAR*.68);
      wub(ch.root,t,BEAT*1.82,.62,local%8<4?4:8);wub(ch.root+7,t+BEAT*2.05,BEAT*1.55,.46,local%16<8?8:4);
      if(local%24===0)leadPhrase(t,'C',.42);
      if(local%16===12)bronzeBell(ch.piano[2]+12,t+BEAT*3,.18);
      return;
    }

    // VII — melody returns over the whole machine.
    if(sec.a===672){
      pianoArp(ch,t,'full',.62);if(bar%2===0)padChord(ch,t,2,.38);fullDrums(t,.78);tranceArp(ch,t,.34);leviathan(ch.root,t,BAR*.78);
      if(local%8===0)leadPhrase(t,local%16?'B':'A',.70);
      if(local%16===8)wub(ch.root,t+BEAT*2,BEAT*1.7,.34,8);
      if(local%24===20)bronzeBell(ch.piano[3]+12,t+BEAT*2.6,.22);
      return;
    }

    // VIII — drums disappear in stages; the aluminum piano gets the last word.
    if(sec.a===784){
      if(local<20){fullDrums(t,.55);tranceArp(ch,t,.22);leviathan(ch.root,t,BAR*.70);if(local%8===0)leadPhrase(t,'A',.46);}
      else if(local<36){pulseDrums(t,.30);if(bar%2===0)leviathan(ch.root,t,BAR*.65);}
      if(bar%2===0)pianoArp(ch,t,local>36?'sparse':'full',.70);
      if(bar%4===0)padChord(ch,t,Math.min(4,Math.max(1,840-bar)),local>36?.15:.24);
      if(local===44)bronzeBell(78,t+BEAT*2,.28);
      if(bar===838){[59,62,66,73].forEach((m,i)=>aluminumPiano(m,t+i*.07,.80,7.0));}
    }
  }

  function updateUi(){
    if(!W.running)return;
    const elapsed=clamp(ctx.currentTime-W.startCtx,0,TOTAL);
    if(W.clock)W.clock.textContent=fmt(elapsed)+' / 30:00';
    if(W.fill)W.fill.style.width=(elapsed/TOTAL*100).toFixed(2)+'%';
    if(W.status)W.status.textContent=W.paused?'Paused':'Playing · '+sectionFor(Math.min(W.bar,839)).name;
  }

  function scheduler(){
    if(!W.running||W.paused)return;
    while(W.bar<TOTAL_BARS&&W.nextBar<ctx.currentTime+LOOK){scheduleBar(W.bar,W.nextBar);W.bar++;W.nextBar+=BAR;}
    updateUi();
    if(W.bar>=TOTAL_BARS&&ctx.currentTime>=W.startCtx+TOTAL+.6)finish();
  }

  async function start(){
    stop(false);
    if(typeof window.stopClassics==='function')window.stopClassics(false);
    await boot();if(ctx.state==='suspended')await ctx.resume();setupFx();
    W.running=true;W.paused=false;W.bar=0;W.startCtx=ctx.currentTime+.10;W.nextBar=W.startCtx;
    if(W.playBtn)W.playBtn.textContent='↻ RESTART — THE CATHEDRAL MACHINE';
    if(W.pauseBtn){W.pauseBtn.disabled=false;W.pauseBtn.textContent='PAUSE';}
    if(W.stopBtn)W.stopBtn.disabled=false;
    if(W.status)W.status.textContent='Starting · cathedral doors opening…';
    if(W.clock)W.clock.textContent='0:00 / 30:00';if(W.fill)W.fill.style.width='0%';
    W.timer=setInterval(scheduler,50);scheduler();
  }

  async function pauseResume(){
    if(!W.running)return;
    if(W.paused){await ctx.resume();W.paused=false;if(W.pauseBtn)W.pauseBtn.textContent='PAUSE';scheduler();}
    else{await ctx.suspend();W.paused=true;if(W.pauseBtn)W.pauseBtn.textContent='RESUME';updateUi();}
  }

  function clearAudio(){
    for(const id of W.timeouts)clearTimeout(id);W.timeouts.clear();
    for(const src of [...W.sources]){try{src.stop();}catch(_){}}W.sources.clear();
    if(typeof panic==='function')panic();
  }

  function stop(update=true){
    if(W.timer){clearInterval(W.timer);W.timer=null;}
    const was=W.running||W.paused;W.running=false;W.paused=false;clearAudio();
    if(update&&was&&W.status)W.status.textContent='Stopped';
    if(W.pauseBtn){W.pauseBtn.textContent='PAUSE';W.pauseBtn.disabled=true;}
    if(W.stopBtn)W.stopBtn.disabled=true;
    if(W.playBtn)W.playBtn.textContent='▶ PLAY — THE CATHEDRAL MACHINE · 30:00';
  }

  function finish(){
    if(W.timer){clearInterval(W.timer);W.timer=null;}W.running=false;W.paused=false;
    if(W.status)W.status.textContent='Complete · 30:00';if(W.clock)W.clock.textContent='30:00 / 30:00';if(W.fill)W.fill.style.width='100%';
    if(W.pauseBtn)W.pauseBtn.disabled=true;if(W.stopBtn)W.stopBtn.disabled=true;if(W.playBtn)W.playBtn.textContent='▶ PLAY AGAIN · 30:00';
  }

  function bindUi(){
    W.playBtn=document.getElementById('workpiecePlay');W.pauseBtn=document.getElementById('workpiecePause');W.stopBtn=document.getElementById('workpieceStop');
    W.status=document.getElementById('workpieceStatus');W.clock=document.getElementById('workpieceClock');W.fill=document.getElementById('workpieceFill');W.section=document.getElementById('workpieceSection');
    if(!W.playBtn)return;
    W.playBtn.addEventListener('click',()=>start().catch(err=>{console.error(err);if(W.status)W.status.textContent='Could not start audio — tap PLAY again';}));
    W.pauseBtn.addEventListener('click',()=>pauseResume().catch(console.error));W.stopBtn.addEventListener('click',()=>stop());
    W.pauseBtn.disabled=true;W.stopBtn.disabled=true;
    const panicBtn=document.getElementById('panic');if(panicBtn)panicBtn.addEventListener('click',()=>stop(false));
    const cq=document.getElementById('classicQuick');if(cq)cq.addEventListener('click',e=>{if(W.running&&e.target.closest('button'))stop(false);},true);
  }

  window.playLeviathanWorkpiece=start;
  window.stopLeviathanWorkpiece=stop;
  bindUi();
})();

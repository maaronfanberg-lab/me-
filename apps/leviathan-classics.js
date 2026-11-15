/* LEVIATHAN CLASSICS — three long-form public-domain-inspired arrangements.
   These are compact LEVIATHAN arrangements, sequenced through the live modal
   string engine rather than prerecorded audio. */

(()=>{
  const NOTE_PC={C:0,'C#':1,Db:1,D:2,'D#':3,Eb:3,E:4,F:5,'F#':6,Gb:6,G:7,'G#':8,Ab:8,A:9,'A#':10,Bb:10,B:11};
  const C={running:false,events:[],ix:0,total:0,started:0,tick:null,offs:new Set(),label:'',panel:null,status:null,fill:null};

  function midi(name){
    const m=/^([A-G](?:#|b)?)(-?\d)$/.exec(name);
    if(!m) throw new Error('Bad note '+name);
    return 12*(+m[2]+1)+NOTE_PC[m[1]];
  }
  function semiForMidi(m){
    const f=440*Math.pow(2,(m-69)/12);
    return 12*Math.log2(f/fOpen())-S.octave*12;
  }
  function n(e,t,note,dur){e.push({t,type:'note',m:midi(note),dur});}
  function ch(e,t,notes,dur){notes.forEach(x=>n(e,t,x,dur));}

  function bach(){
    const e=[], beat=60000/72, six=beat/4;
    const bars=[
      ['C3','E3','G3','C4','E4'],['C3','D3','A3','D4','F4'],['B2','D3','G3','B3','F4'],
      ['C3','E3','G3','C4','E4'],['C3','E3','A3','C4','E4'],['C3','D3','F#3','A3','D4'],
      ['B2','D3','G3','B3','D4'],['G2','C3','E3','G3','C4'],['A2','C3','F3','A3','C4'],
      ['F#2','C3','D3','A3','D4'],['G2','B2','D3','G3','B3'],['G#2','B2','E3','G#3','D4'],
      ['A2','C3','E3','A3','C4'],['C3','F3','A3','C4','F4'],['D3','F3','A3','C4','F4'],
      ['G2','B2','D3','F3','G3'],['E3','G3','C4','E4','G4'],['F2','A2','C3','F3','A3'],
      ['G2','B2','D3','F3','B3'],['C3','E3','G3','C4','E4'],['C2','G2','C3','E3','G3']
    ];
    const pat=[0,1,2,3,4,2,3,4,0,1,2,3,4,2,3,4];
    let t=0;
    for(const v of bars){
      pat.forEach((ix,j)=>n(e,t+j*six,v[ix],six*.82));
      t+=16*six;
    }
    ch(e,t-2*six,['C3','E3','G3','C4','E4'],beat*1.6);
    return {events:e,duration:t+beat*1.7};
  }

  function moonlight(){
    const e=[], beat=60000/56, trip=beat/3, bar=beat*4;
    const bars=[
      {b:'C#2',a:['G#3','C#4','E4'],m:['G#4','C#5']},{b:'B1',a:['G#3','B3','E4'],m:['B4','G#4']},
      {b:'A1',a:['E3','A3','C#4'],m:['A4','E4']},{b:'G#1',a:['D#3','G#3','C4'],m:['G#4','F#4']},
      {b:'C#2',a:['G#3','C#4','E4'],m:['E4','G#4']},{b:'B1',a:['F#3','B3','D#4'],m:['F#4','D#4']},
      {b:'E2',a:['G#3','B3','E4'],m:['G#4','B4']},{b:'B1',a:['F#3','A3','D#4'],m:['A4','F#4']},
      {b:'A1',a:['E3','A3','C#4'],m:['E4','C#5']},{b:'F#1',a:['C#3','F#3','A3'],m:['F#4','A4']},
      {b:'G#1',a:['D#3','G#3','B3'],m:['D#4','G#4']},{b:'C#2',a:['G#3','C#4','E4'],m:['C#5','B4']},
      {b:'F#1',a:['A3','C#4','F#4'],m:['A4','G#4']},{b:'G#1',a:['G#3','C4','D#4'],m:['G#4','F#4']},
      {b:'C#2',a:['G#3','C#4','E4'],m:['E4','D#4']},{b:'G#1',a:['D#3','G#3','C4'],m:['C#4','B3']},
      {b:'C#2',a:['G#3','C#4','E4'],m:['C#4','G#4']}
    ];
    let t=0;
    bars.forEach((x,bi)=>{
      n(e,t,x.b,bar*.88);
      for(let k=0;k<12;k++) n(e,t+k*trip,x.a[k%3],trip*.78);
      n(e,t+trip*.15,x.m[0],beat*1.55);
      n(e,t+beat*2+trip*.12,x.m[1],beat*1.45);
      if(bi===0||bi===8||bi===16) ch(e,t+beat*3.05,[x.a[0],x.a[1],x.a[2]],beat*.78);
      t+=bar;
    });
    ch(e,t-bar*.16,['C#3','E3','G#3','C#4'],beat*2.1);
    return {events:e,duration:t+beat*1.8};
  }

  function satie(){
    const e=[], beat=60000/72, bar=beat*3;
    const harm=[
      {b:'G2',c:['F#3','B3','D4']},{b:'D2',c:['C#3','F#3','A3']},{b:'G2',c:['F#3','B3','D4']},
      {b:'D2',c:['C#3','F#3','A3']},{b:'E2',c:['D3','G3','B3']},{b:'B1',c:['A2','D3','F#3']},
      {b:'A1',c:['G2','C#3','E3']},{b:'D2',c:['C#3','F#3','A3']},{b:'G2',c:['F#3','B3','D4']},
      {b:'D2',c:['C#3','F#3','A3']},{b:'C2',c:['B2','E3','G3']},{b:'B1',c:['A2','D3','F#3']},
      {b:'E2',c:['D3','G3','B3']},{b:'A1',c:['G2','C#3','E3']}
    ];
    const mel1=['F#4','A4','G4','F#4','C#4','E4','D4','B3','D4','E4','F#4','A4','G4','F#4'];
    const mel2=['B4','A4','F#4','E4','C#4','D4','E4','F#4','A4','G4','E4','D4','F#4','E4'];
    let t=0;
    for(let pass=0;pass<2;pass++){
      harm.forEach((h,i)=>{
        n(e,t,h.b,bar*.9);
        ch(e,t+beat*.92,h.c,beat*1.72);
        const melody=pass?mel2[i]:mel1[i];
        n(e,t+beat*.22,melody,beat*1.34);
        if(i%3===1) n(e,t+beat*2.02,pass?mel1[i]:mel2[i],beat*.72);
        t+=bar;
      });
    }
    ch(e,t-bar*.12,['G2','F#3','B3','D4','F#4'],beat*2.3);
    return {events:e,duration:t+beat*1.9};
  }

  const PIECES={
    bach:{title:'Bach — Prelude in C major',sub:'BWV 846 · LEVIATHAN arrangement',build:bach},
    moon:{title:'Beethoven — Moonlight Sonata',sub:'Op. 27 No. 2, I · LEVIATHAN arrangement',build:moonlight},
    satie:{title:'Satie — Gymnopédie No. 1',sub:'LEVIATHAN arrangement',build:satie}
  };

  async function readyAudio(){
    await boot();
    if(ctx.state==='suspended') await ctx.resume();
    const p=document.getElementById('power'); if(p)p.remove();
    const k=document.getElementById('kbwrap'); if(k)k.style.display='block';
    sizeCanvas();
  }

  function stopClassics(update=true){
    C.running=false;
    if(C.tick){clearInterval(C.tick);C.tick=null;}
    for(const id of C.offs) clearTimeout(id); C.offs.clear();
    if(typeof panic==='function') panic();
    if(update&&C.status)C.status.textContent='Stopped';
    if(C.fill)C.fill.style.width='0%';
  }

  function trigger(ev){
    if(ev.type==='marker'){
      C.label=ev.title;
      if(C.status)C.status.textContent=ev.title;
      return;
    }
    const s=semiForMidi(ev.m);
    noteOn(s);
    const id=setTimeout(()=>{C.offs.delete(id);noteOff(s);},Math.max(70,ev.dur));
    C.offs.add(id);
  }

  async function perform(ids){
    stopClassics(false);
    await readyAudio();
    const events=[]; let offset=0;
    ids.forEach((id,idx)=>{
      const p=PIECES[id], built=p.build();
      events.push({t:offset,type:'marker',title:p.title});
      built.events.forEach(ev=>events.push({...ev,t:ev.t+offset}));
      offset+=built.duration;
      if(idx<ids.length-1)offset+=1400;
    });
    events.sort((a,b)=>a.t-b.t);
    C.events=events;C.ix=0;C.total=offset;C.started=performance.now();C.running=true;
    C.label=ids.length>1?'Classics playlist':PIECES[ids[0]].title;
    if(C.status)C.status.textContent='Starting…';
    C.tick=setInterval(()=>{
      if(!C.running)return;
      const elapsed=performance.now()-C.started;
      while(C.ix<C.events.length&&C.events[C.ix].t<=elapsed+18) trigger(C.events[C.ix++]);
      if(C.fill)C.fill.style.width=Math.min(100,elapsed/C.total*100).toFixed(2)+'%';
      if(C.status&&C.label){
        const remain=Math.max(0,Math.ceil((C.total-elapsed)/1000));
        C.status.textContent=C.label+' · '+remain+'s left';
      }
      if(elapsed>C.total+350&&C.ix>=C.events.length){
        C.running=false;clearInterval(C.tick);C.tick=null;
        if(C.status)C.status.textContent='Performance complete';
        if(C.fill)C.fill.style.width='100%';
      }
    },20);
  }

  function buildUI(){
    const tabs=document.querySelector('.tabs'); if(!tabs)return;
    const tab=document.createElement('button');tab.className='tab';tab.dataset.p='cl';tab.textContent='CLASSICS';tabs.appendChild(tab);
    const panel=document.createElement('div');panel.className='panel';panel.id='p-cl';
    panel.innerHTML=`
      <h2 class="sec">Automatic performances</h2>
      <div class="note" style="margin-top:0">Three long-form LEVIATHAN arrangements, each about 70 seconds. They are generated live by the cable/rod modal engine — no prerecorded audio.</div>
      <div id="classicCards"></div>
      <div class="seg" style="margin-top:12px">
        <button class="btn wide" id="classicAll">PLAY ALL · ~3½ MIN</button>
        <button class="btn" id="classicStop">STOP</button>
      </div>
      <div style="height:7px;border:1px solid var(--rule);background:#0A0E18;margin-top:12px;overflow:hidden"><div id="classicFill" style="height:100%;width:0%;background:var(--violet)"></div></div>
      <div id="classicStatus" class="note" style="border-top:0;margin-top:7px;padding-top:0">Ready</div>`;
    document.body.appendChild(panel);
    C.panel=panel;C.status=panel.querySelector('#classicStatus');C.fill=panel.querySelector('#classicFill');
    const cards=panel.querySelector('#classicCards');
    Object.entries(PIECES).forEach(([id,p])=>{
      const row=document.createElement('div');row.className='row';row.style.flexWrap='wrap';
      row.innerHTML=`<span class="lbl" style="flex:1 0 100%;color:var(--text);font-size:12px">${p.title}</span><span style="flex:1;color:var(--dim);font-size:10px">${p.sub} · ~70s</span><button class="btn sm">PLAY</button>`;
      row.querySelector('button').onclick=()=>perform([id]);cards.appendChild(row);
    });
    panel.querySelector('#classicAll').onclick=()=>perform(['bach','moon','satie']);
    panel.querySelector('#classicStop').onclick=()=>stopClassics();
    const panicBtn=document.getElementById('panic');if(panicBtn)panicBtn.addEventListener('click',()=>stopClassics(false));
    tab.onclick=()=>{
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
      document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
      tab.classList.add('on');panel.classList.add('on');
    };
  }

  window.stopClassics=stopClassics;
  window.playLeviathanClassic=id=>perform([id]);
  buildUI();
})();

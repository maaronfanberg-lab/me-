class PhysicalGraphProcessor extends AudioWorkletProcessor {
  constructor(){
    super();
    this.bodies=[];
    this.springs=[];
    this.mic={gain:0.35,spread:0.35};
    this.outLP=0;
    this.port.onmessage=e=>this.onMessage(e.data||{});
  }
  onMessage(m){
    if(m.t==='graph'){
      this.bodies=(m.bodies||[]).map(b=>({
        x:b.x||0,v:0,m:Math.max(.05,b.mass||1),d:Math.max(0,b.damping||.05),anchor:!!b.anchor
      }));
      this.springs=(m.springs||[]).map(s=>({a:s.a,b:s.b,k:Math.max(0,s.stiffness||100),d:Math.max(0,s.damping||1)}));
    } else if(m.t==='hit'){
      const b=this.bodies[m.index]; if(b&&!b.anchor) b.v += (m.amount||1)/Math.sqrt(b.m);
    } else if(m.t==='body'){
      const b=this.bodies[m.index]; if(b){if(m.mass!=null)b.m=Math.max(.05,m.mass);if(m.damping!=null)b.d=Math.max(0,m.damping);if(m.anchor!=null)b.anchor=!!m.anchor;}
    } else if(m.t==='spring'){
      const s=this.springs[m.index]; if(s){if(m.stiffness!=null)s.k=Math.max(0,m.stiffness);if(m.damping!=null)s.d=Math.max(0,m.damping);}
    } else if(m.t==='mic'){
      if(m.gain!=null)this.mic.gain=m.gain;if(m.spread!=null)this.mic.spread=m.spread;
    }
  }
  process(inputs,outputs){
    const out=outputs[0],L=out[0],R=out[1]||out[0];
    const dt=1/sampleRate;
    for(let n=0;n<L.length;n++){
      for(const s of this.springs){
        const a=this.bodies[s.a],b=this.bodies[s.b]; if(!a||!b)continue;
        const rel=b.x-a.x, rv=b.v-a.v, f=s.k*rel+s.d*rv;
        if(!a.anchor)a.v+=f/a.m*dt;
        if(!b.anchor)b.v-=f/b.m*dt;
      }
      let sig=0;
      for(let i=0;i<this.bodies.length;i++){
        const b=this.bodies[i];
        if(!b.anchor){
          b.v += (-b.d*b.v)*dt;
          b.x += b.v*dt;
          sig += b.v*(0.3+0.7*((i%5)/4));
        }
      }
      sig/=Math.max(1,this.bodies.length);
      this.outLP += 0.15*(sig-this.outLP);
      const s=Math.tanh((sig*.75+this.outLP*.4)*this.mic.gain);
      L[n]=s*(1-this.mic.spread*.12);
      R[n]=s*(1+this.mic.spread*.12);
    }
    return true;
  }
}
registerProcessor('physical-graph',PhysicalGraphProcessor);
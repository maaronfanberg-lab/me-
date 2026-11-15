/*
 * Noise Removal: engine-preserving focus and gap reducer.
 * Copyright (C) 2026 Noise Removal contributors
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This mode deliberately avoids the frame-by-frame spectral peak masking
 * used by the previous engine mode, which could make the output chirp.
 *
 * It uses only smooth fixed biquad EQ (110 Hz high-pass, 3400 Hz low-pass)
 * and a sustained mid-band energy detector to fade down pauses.
 * It cannot fully separate an engine from overlapping sounds.
 */
(function(global){
  'use strict';
  function biquad(type,rate,frequency,Q=.7071) {
    const w=2*Math.PI*Math.min(frequency,rate*.46)/rate;
    const cos=Math.cos(w),alpha=Math.sin(w)/(2*Q);
    const a0=1+alpha;
    const b0=type==='lowpass'?(1-cos)/2:(1+cos)/2;
    const b1=type==='lowpass'?1-cos:-(1+cos);
    const b2=b0;
    const a1=-2*cos,a2=1-alpha;
    return [b0/a0,b1/a0,b2/a0,a1/a0,a2/a0];
  }
  function applyBiquad(signal,coeff) {
    const [b0,b1,b2,a1,a2]=coeff;
    let x1=0,x2=0,y1=0,y2=0;
    const out=new Float32Array(signal.length);
    for(let i=0;i<signal.length;i++) {
      const x=signal[i],y=b0*x+b1*x1+b2*x2-a1*y1-a2*y2;
      out[i]=Number.isFinite(y)?y:0;
      x2=x1;x1=x;y2=y1;y1=y;
    }
    return out;
  }
  function smoother(values,sigma) {
    const radius=Math.ceil(sigma*4),weights=new Float64Array(radius*2+1);
    let norm=0;
    for(let j=-radius;j<=radius;j++){const w=Math.exp(-.5*(j/sigma)**2);weights[j+radius]=w;norm+=w;}
    const result=new Float32Array(values.length);
    for(let i=0;i<values.length;i++) {
      let total=0;
      for(let j=-radius;j<=radius;j++){
        const ix=Math.max(0,Math.min(values.length-1,i+j));
        total+=weights[j+radius]*values[ix];
      }
      result[i]=total/norm;
    }
    return result;
  }
  function morphology(src,width,operation) {
    const n=src.length,out=new Uint8Array(n),sum=new Uint32Array(n+1);
    const radius=Math.max(0,Math.floor(width));
    for(let i=0;i<n;i++)sum[i+1]=sum[i]+(src[i]?1:0);
    for(let i=0;i<n;i++){
      const lo=Math.max(0,i-radius),hi=Math.min(n-1,i+radius),on=sum[hi+1]-sum[lo];
      out[i]=operation==='dilate'?(on>0?1:0):(on===hi-lo+1?1:0);
    }
    return out;
  }
  function percentile(sorted,q){return sorted[Math.min(sorted.length-1,Math.floor((sorted.length-1)*q))]}
  function revGain(channels,rate){
    const n=channels[0].length,step=Math.max(128,Math.round(rate*.025)),count=Math.ceil(n/step);
    const hp=biquad('highpass',rate,145),lp=biquad('lowpass',rate,1300);
    const activity=new Float64Array(count);
    for(const ch of channels){
      const d=applyBiquad(applyBiquad(ch,hp),lp);
      for(let i=0;i<count;i++){
        const lo=i*step,hi=Math.min(n,lo+step);let power=0;
        for(let j=lo;j<hi;j++)power+=d[j]*d[j];
        activity[i]+=power/Math.max(1,(hi-lo)*channels.length);
      }
    }
    const envelope=smoother(Float32Array.from(activity,x=>Math.sqrt(x)),4);
    const sorted=Array.from(envelope).sort((a,b)=>a-b);
    const high=percentile(sorted,.95),low=percentile(sorted,.20);
    const activityThreshold=Math.max(high*.23,low*1.6,1e-7);
    // If sound is uniformly active, avoid a false gate that
    // would mangle a continuous engine recording.
    if(high<low*1.8)return {gain:new Float32Array(count).fill(1),step,threshold:activityThreshold,activeFrames:count};
    const signal=Uint8Array.from(envelope,e=>e>activityThreshold?1:0);
    // Bridge gaps shorter than 150 ms; reject bursts shorter than 175 ms.
    const joined=morphology(morphology(signal,3,'dilate'),3,'erode');
    const sustained=morphology(morphology(joined,4,'erode'),4,'dilate');
    // Keep brief rev onset and the natural trailing decay; then fade gently.
    const raised=morphology(sustained,9,'dilate');
    const gain=smoother(raised,3.5);
    return {gain,step,threshold:activityThreshold,activeFrames:sustained.reduce((s,v)=>s+v,0)};
  }
  async function process(buffer,settings={},progress){
    if(!buffer||!buffer.length)throw Error('Load an audio recording first.');
    const rate=buffer.sampleRate,n=buffer.length,chans=buffer.numberOfChannels;
    const processed=[];
    for(let c=0;c<chans;c++){
      // Fixed frequency response, no FFT bin-wise speech/noise classification.
      let y=applyBiquad(buffer.getChannelData(c),biquad('highpass',rate,110));
      y=applyBiquad(y,biquad('lowpass',rate,3400));
      processed.push(y);
      if(progress)progress(.35*(c+1)/chans);
      await new Promise(resolve=>setTimeout(resolve,0));
    }
    const gate=revGain(processed,rate);
    if(progress)progress(.48);
    const floor=.0025,output=[];
    for(let c=0;c<chans;c++){
      const y=processed[c],dst=new Float32Array(n);
      for(let i=0;i<n;i++){
        const at=i/gate.step,lo=Math.min(gate.gain.length-1,Math.floor(at));
        const frac=at-lo;
        const g=gate.gain[lo]*(1-frac)+gate.gain[Math.min(gate.gain.length-1,lo+1)]*frac;
        const value=y[i]*(floor+(1-floor)*Math.max(0,Math.min(1,g)));
        dst[i]=settings.residue?buffer.getChannelData(c)[i]-value:value;
      }
      output.push(dst);
      if(progress)progress(.48+.52*(c+1)/chans);
      await new Promise(resolve=>setTimeout(resolve,0));
    }
    return {channels:output,sampleRate:rate,length:n,gateThreshold:gate.threshold,activeFrames:gate.activeFrames};
  }
  global.EngineGateDSP={process,algorithm:'Broadband engine preserve + sustained rev gate',license:'GPL-3.0-or-later'};
})(typeof window!=='undefined'?window:globalThis);

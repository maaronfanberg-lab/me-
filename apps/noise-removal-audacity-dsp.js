/*
 * Noise Removal Audacity Noise Reduction core — JavaScript adaptation
 *
 * Adapted from Audacity's NoiseReductionBase.cpp (audacity3 branch):
 * https://github.com/audacity/audacity/blob/audacity3/libraries/lib-builtin-effects/NoiseReductionBase.cpp
 * Original authors: Dominic Mazzoni; detailed rewriting by Paul Licameli.
 * Audacity contributors retain their copyrights. Modified for browser execution in 2026.
 * Copyright (C) 2026 Noise Removal contributors for the adaptations.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 * You may copy, modify and redistribute this software under GNU GPL v3 or later.
 * Full license: https://www.gnu.org/licenses/gpl-3.0.html
 *
 * This is an adaptation of the Audacity algorithm, not a build of Audacity's
 * unmodified C++ processing engine. UI, FFT, chunking and browser plumbing differ.
 *
 * Audacity-derived elements:
 * - first pass: robust frequency statistics from quiet reference windows
 *   and per-bin medians to reduce contamination by incidental speech
 * - second pass: discard highest outlier, classify using second-highest of
 *   5 neighboring windows and sensitivity * ln(10) * mean noise power
 * - attenuate noise bins by 10^(-reductionDb / 20)
 * - additional conservative Wiener-style mask for overlapping steady noise
 * - 20 ms attack (backward), 100 ms release (forward)
 * - frequency smoothing of log gains, overlap-add resynthesis
 * - 'Residue / Noise Only' preview of the rejected signal
 *
 * Audio is processed entirely on the device; no network APIs are used here.
 */
(function(global) {
  'use strict';
  const N=2048, H=512, K=N/2+1;
  const hann=new Float32Array(N), rev=new Uint16Array(N), stages=[];
  for(let i=0;i<N;i++){
    hann[i]=0.5-0.5*Math.cos(2*Math.PI*(i+0.5)/N);
    let x=i,v=0;
    for(let bit=0;bit<11;bit++){v=(v<<1)|(x&1);x>>=1}
    rev[i]=v;
  }
  for(let len=2;len<=N;len*=2){
    const c=new Float32Array(len/2),s=new Float32Array(len/2);
    for(let i=0;i<len/2;i++){c[i]=Math.cos(2*Math.PI*i/len);s[i]=-Math.sin(2*Math.PI*i/len)}
    stages.push({len,c,s});
  }
  function fft(re,im,inverse){
    for(let i=0;i<N;i++){const j=rev[i];if(j>i){let t=re[i];re[i]=re[j];re[j]=t;t=im[i];im[i]=im[j];im[j]=t}}
    for(const st of stages){
      const half=st.len/2;
      for(let a=0;a<N;a+=st.len)for(let j=0;j<half;j++){
        const q=a+j,r=q+half,cs=st.c[j],sn=inverse?-st.s[j]:st.s[j];
        const tr=re[r]*cs-im[r]*sn,ti=re[r]*sn+im[r]*cs;
        re[r]=re[q]-tr;im[r]=im[q]-ti;re[q]+=tr;im[q]+=ti;
      }
    }
    if(inverse)for(let i=0;i<N;i++){re[i]/=N;im[i]/=N}
  }
  function frame(samples,pos,re,im) {
    re.fill(0);im.fill(0);
    const left=Math.max(0,-pos),right=Math.min(N,samples.length-pos);
    for(let i=left;i<right;i++)re[i]=samples[pos+i]*hann[i];
    fft(re,im,false);
  }
  function spectrumPower(re,im) {
    const p=new Float32Array(K);
    for(let k=0;k<K;k++)p[k]=re[k]*re[k]+im[k]*im[k];
    return p;
  }
  function noiseProfile(buffer) {
    if(!buffer||buffer.length<2048)throw Error('Select at least a short section of noise.');
    const rate=buffer.sampleRate,nChannels=buffer.numberOfChannels;
    const total=Math.max(1,Math.floor((buffer.length-N)/H)+1);
    const stride=Math.max(1,Math.ceil(total/190));
    const re=new Float32Array(N),im=new Float32Array(N),windows=[];
    const bandLo=Math.max(1,Math.round(300*N/rate));
    const bandHi=Math.min(K-1,Math.round(6000*N/rate));
    for(let c=0;c<nChannels;c++){
      const samples=buffer.getChannelData(c);
      for(let i=0;i<total;i+=stride){
        frame(samples,i*H,re,im);
        const p=spectrumPower(re,im);
        let broadEnergy=0;
        for(let k=bandLo;k<=bandHi;k++)broadEnergy+=p[k];
        windows.push({energy:broadEnergy,powers:p});
      }
    }
    // In a reference that also contains incidental speech, speech usually
    // increases energy in short-time windows. Avoid the loudest windows, then
    // obtain a per-frequency median to reject brief voice and other outliers.
    // The sample itself is not uploaded or stored by this app.
    windows.sort((a,b)=>a.energy-b.energy);
    const keep=(windows.length>=16)?Math.max(8,Math.floor(windows.length*.62)):windows.length;
    const means=new Float32Array(K),values=new Float32Array(keep);
    for(let k=0;k<K;k++){
      for(let j=0;j<keep;j++)values[j]=windows[j].powers[k];
      const sorted=values.sort();
      const mid=Math.floor(keep/2);
      // Under stationary Gaussian noise, FFT power is exponentially
      // distributed and median power equals ln(2) times mean power.
      // Approximate that correction, with allowance for the quiet-frame cut.
      const median=keep%2?sorted[mid]:(sorted[mid-1]+sorted[mid])*.5;
      means[k]=Math.max(1e-14,median*1.8);
    }
    return {sampleRate:rate,meanPower:means,windowSize:N,stepSize:H,
      frames:keep,totalFrames:windows.length,robust:true};
  }
  function profileAtRate(profile,sampleRate) {
    const q=new Float32Array(K),p=profile.meanPower;
    for(let k=0;k<K;k++){
      // Compare at the same physical frequency even when profile and
      // target were recorded at 44.1 kHz and 48 kHz respectively.
      const i=k*sampleRate/profile.sampleRate,j=Math.floor(i),fraction=i-j;
      q[k]=j>=K-1?0:(1-fraction)*p[j]+fraction*p[j+1];
    }
    return q;
  }
  function validateSettings(settings){
    return {
      reductionDb:Math.min(48,Math.max(0,Number(settings.reductionDb)||0)),
      sensitivity:Math.min(24,Math.max(.01,Number(settings.sensitivity)||.01)),
      smoothing:Math.min(12,Math.max(0,Math.round(Number(settings.smoothing)||0))),
      residue:!!settings.residue
    };
  }
  function secondsToSamples(seconds,rate){return Math.round(seconds*rate)}
  function processChunk(samples,begin,end,rate,powerThreshold,options){
    // Each chunk includes 250 ms on both sides so that the first and last
    // output samples have full STFT windows, classifier context and smoothing.
    const pad=secondsToSamples(.25,rate);
    const left=Math.max(0,begin-pad),right=Math.min(samples.length,end+pad);
    const segment=samples.subarray(left,right);
    const frameCount=Math.max(1,Math.ceil((segment.length+N)/H));
    const re=new Float32Array(N),im=new Float32Array(N);
    const powers=new Array(frameCount);
    for(let t=0;t<frameCount;t++){
      frame(segment,t*H-(N>>1),re,im);
      powers[t]=spectrumPower(re,im);
    }
    const floor=Math.pow(10,-options.reductionDb/20);
    const thresholdMult=options.sensitivity*Math.LN10;
    const gains=new Array(frameCount);
    // Audacity DM_SECOND_GREATEST, evaluated for five neighboring windows.
    // Outlier rejection reduces false 'signal' classification.
    for(let t=0;t<frameCount;t++){
      const row=new Float32Array(K);
      for(let k=0;k<K;k++){
        let highest=0,second=0;
        for(let dt=-2;dt<=2;dt++){
          const p=powers[Math.max(0,Math.min(frameCount-1,t+dt))][k];
          if(p>=highest){second=highest;highest=p}
          else if(p>second)second=p;
        }
        const classifiedNoise=second<=powerThreshold[k]*thresholdMult;
        // Audacity's classifier is the backbone. Blend in a continuous
        // spectral estimate so steady hiss remains suppressed even when a
        // wanted sound shares some of the same FFT band.
        const observed=Math.max(1e-12,powers[t][k]);
        const wiener=Math.sqrt(Math.max(floor*floor,
          1-1.25*powerThreshold[k]/observed));
        row[k]=classifiedNoise?floor:Math.max(floor,Math.min(1,wiener));
      }
      gains[t]=row;
    }
    // Audacity gain recovery: propagate release forward, attack backward.
    const attackBlocks=Math.max(1,Math.ceil(.020*rate/H));
    const releaseBlocks=Math.max(1,Math.ceil(.100*rate/H));
    const att=Math.pow(floor,1/attackBlocks),rel=Math.pow(floor,1/releaseBlocks);
    for(let t=1;t<frameCount;t++){
      const a=gains[t-1],b=gains[t];
      for(let k=0;k<K;k++)b[k]=Math.max(b[k],a[k]*rel);
    }
    for(let t=frameCount-2;t>=0;t--){
      const a=gains[t],b=gains[t+1];
      for(let k=0;k<K;k++)a[k]=Math.max(a[k],b[k]*att);
    }
    // Audacity's frequency smoothing is an arithmetic mean in log-gain
    // space, followed by exponentiation. Prefix sums make this O(K).
    const radius=options.smoothing,prefix=new Float64Array(K+1);
    if(radius>0)for(let t=0;t<frameCount;t++){
      const g=gains[t];
      prefix[0]=0;
      for(let k=0;k<K;k++)prefix[k+1]=prefix[k]+Math.log(Math.max(1e-10,g[k]));
      for(let k=0;k<K;k++){
        const lo=Math.max(0,k-radius),hi=Math.min(K-1,k+radius);
        // Smooth suppression in neighboring bins, but don't erase a strong
        // isolated signal component just because nearby bins were noise.
        const smoothed=Math.exp((prefix[hi+1]-prefix[lo])/(hi-lo+1));
        g[k]=Math.max(g[k],smoothed);
      }
    }
    const output=new Float32Array(segment.length),weight=new Float32Array(segment.length);
    for(let t=0;t<frameCount;t++){
      const pos=t*H-(N>>1),gain=gains[t];
      frame(segment,pos,re,im);
      for(let k=0;k<K;k++){
        re[k]*=gain[k];im[k]*=gain[k];
        if(k>0&&k<K-1){re[N-k]*=gain[k];im[N-k]*=gain[k]}
      }
      fft(re,im,true);
      const lo=Math.max(0,-pos),hi=Math.min(N,segment.length-pos);
      for(let i=lo;i<hi;i++){
        const j=pos+i,w=hann[i];
        output[j]+=re[i]*w;
        weight[j]+=w*w;
      }
    }
    const cleaned=new Float32Array(end-begin);
    const offset=begin-left;
    for(let i=0;i<cleaned.length;i++){
      const j=i+offset;
      const y=weight[j]>1e-7?output[j]/weight[j]:segment[j];
      cleaned[i]=options.residue?segment[j]-y:y;
      if(!Number.isFinite(cleaned[i]))cleaned[i]=0;
    }
    return cleaned;
  }
  async function reduce(buffer,profile,settings,progress){
    if(!buffer||!profile)throw Error('Load a recording and get a noise profile first.');
    const options=validateSettings(settings||{});
    const rate=buffer.sampleRate,threshold=profileAtRate(profile,rate);
    const n=buffer.length,nChannels=buffer.numberOfChannels;
    const out=new Array(nChannels);
    // Max ~8s spectral working set, instead of holding all spectrograms in memory.
    const chunkSamples=Math.max(8192,secondsToSamples(6,rate));
    const chunks=Math.ceil(n/chunkSamples);
    for(let c=0;c<nChannels;c++){
      const src=buffer.getChannelData(c),dst=new Float32Array(n);
      for(let ci=0;ci<chunks;ci++){
        const begin=ci*chunkSamples,end=Math.min(n,begin+chunkSamples);
        dst.set(processChunk(src,begin,end,rate,threshold,options),begin);
        if(progress)progress((c+(ci+1)/chunks)/nChannels);
        await new Promise(resolve=>setTimeout(resolve,0));
      }
      out[c]=dst;
    }
    return {channels:out,sampleRate:rate,length:n};
  }
  global.AudacityNoiseDSP={noiseProfile,reduce,algorithm:'Audacity Noise Reduction (JS adaptation)',license:'GPL-3.0-or-later'};
})(typeof window!=='undefined'?window:globalThis);

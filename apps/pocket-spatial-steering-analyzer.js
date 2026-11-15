class PocketSpatialSteeringAnalyzer extends AudioWorkletProcessor {
  constructor(){
    super();
    this.samples=0;
    this.eL=0;this.eR=0;this.cross=0;this.mid=0;this.side=0;
    this.prevXL=0;this.prevXR=0;this.prevYL=0;this.prevYR=0;
    this.lp900L=0;this.lp900R=0;this.lp3500L=0;this.lp3500R=0;this.lp8000L=0;this.lp8000R=0;
    var dt=1/sampleRate,rc150=1/(2*Math.PI*150);
    this.hpAlpha=rc150/(rc150+dt);
    this.lp900Alpha=1-Math.exp(-2*Math.PI*900/sampleRate);
    this.lp3500Alpha=1-Math.exp(-2*Math.PI*3500/sampleRate);
    this.lp8000Alpha=1-Math.exp(-2*Math.PI*8000/sampleRate);
    this.fastAttack=1-Math.exp(-1/(sampleRate*.002));this.fastRelease=1-Math.exp(-1/(sampleRate*.015));
    this.slowAttack=1-Math.exp(-1/(sampleRate*.002));this.slowRelease=1-Math.exp(-1/(sampleRate*.120));
    this.windowSamples=Math.max(128,Math.round(sampleRate*.025));this.bands=[this.newBand(),this.newBand(),this.newBand()];
  }
  newBand(){return{eL:0,eR:0,cross:0,mid:0,side:0,fast:0,slow:0,transient:1};}
  env(current,target,attack,release){var a=target>current?attack:release;return current+(target-current)*a;}
  addBand(b,l,r){var m=(l+r)*.5,s=(l-r)*.5,mag=Math.max(Math.abs(l),Math.abs(r));b.eL+=l*l;b.eR+=r*r;b.cross+=l*r;b.mid+=m*m;b.side+=s*s;b.fast=this.env(b.fast,mag,this.fastAttack,this.fastRelease);b.slow=this.env(b.slow,mag,this.slowAttack,this.slowRelease);var tr=b.fast/(b.slow+1e-9);if(Number.isFinite(tr))b.transient=Math.max(b.transient,Math.min(4,tr));}
  stats(b){var eps=1e-12,n=Math.max(1,this.samples),rmsL=Math.sqrt(b.eL/n),rmsR=Math.sqrt(b.eR/n),corr=b.cross/Math.sqrt(Math.max(eps,b.eL*b.eR));if(!Number.isFinite(corr))corr=1;corr=Math.max(-1,Math.min(1,corr));var ms=b.mid+b.side,sideRatio=ms>eps?b.side/ms:0,sum=rmsL+rmsR;return{corr:corr,sideRatio:Math.max(0,Math.min(1,sideRatio)),balance:sum>eps?(rmsL-rmsR)/sum:0,rms:Math.sqrt((b.eL+b.eR)/(n*2)),transient:Math.max(0,Math.min(4,b.transient))};}
  resetBand(b){b.eL=0;b.eR=0;b.cross=0;b.mid=0;b.side=0;b.transient=1;}
  process(inputs,outputs){
    var input=inputs[0],output=outputs[0];if(!input||!input[0])return true;
    var left=input[0],right=input[1]||left,outL=output&&output[0],outR=output&&output[1];
    for(var i=0;i<left.length;i+=1){
      var xL=left[i]||0,xR=right[i]||0;if(outL)outL[i]=0;if(outR)outR[i]=0;
      var yL=this.hpAlpha*(this.prevYL+xL-this.prevXL),yR=this.hpAlpha*(this.prevYR+xR-this.prevXR);this.prevXL=xL;this.prevXR=xR;this.prevYL=yL;this.prevYR=yR;
      this.lp900L+=this.lp900Alpha*(yL-this.lp900L);this.lp900R+=this.lp900Alpha*(yR-this.lp900R);this.lp3500L+=this.lp3500Alpha*(yL-this.lp3500L);this.lp3500R+=this.lp3500Alpha*(yR-this.lp3500R);this.lp8000L+=this.lp8000Alpha*(yL-this.lp8000L);this.lp8000R+=this.lp8000Alpha*(yR-this.lp8000R);
      var b1L=this.lp900L,b1R=this.lp900R,b2L=this.lp3500L-this.lp900L,b2R=this.lp3500R-this.lp900R,b3L=this.lp8000L-this.lp3500L,b3R=this.lp8000R-this.lp3500R;
      this.addBand(this.bands[0],b1L,b1R);this.addBand(this.bands[1],b2L,b2R);this.addBand(this.bands[2],b3L,b3R);
      var m=(yL+yR)*.5,s=(yL-yR)*.5;this.eL+=yL*yL;this.eR+=yR*yR;this.cross+=yL*yR;this.mid+=m*m;this.side+=s*s;this.samples+=1;
    }
    if(this.samples>=this.windowSamples){
      var eps=1e-12,rmsL=Math.sqrt(this.eL/this.samples),rmsR=Math.sqrt(this.eR/this.samples),corr=this.cross/Math.sqrt(Math.max(eps,this.eL*this.eR));if(!Number.isFinite(corr))corr=1;corr=Math.max(-1,Math.min(1,corr));var ms=this.mid+this.side,sideRatio=ms>eps?this.side/ms:0,sumRms=rmsL+rmsR;
      this.port.postMessage({corr:corr,sideRatio:sideRatio,balance:sumRms>eps?(rmsL-rmsR)/sumRms:0,rms:Math.sqrt((this.eL+this.eR)/(Math.max(1,this.samples)*2)),b1:this.stats(this.bands[0]),b2:this.stats(this.bands[1]),b3:this.stats(this.bands[2])});
      this.samples=0;this.eL=0;this.eR=0;this.cross=0;this.mid=0;this.side=0;this.resetBand(this.bands[0]);this.resetBand(this.bands[1]);this.resetBand(this.bands[2]);
    }
    return true;
  }
}
registerProcessor('pocket-spatial-steering-analyzer',PocketSpatialSteeringAnalyzer);

class PocketSpatialSteeringAnalyzer extends AudioWorkletProcessor {
  constructor(){
    super();
    this.samples=0;
    this.eL=0;this.eR=0;this.cross=0;this.mid=0;this.side=0;
    this.prevXL=0;this.prevXR=0;this.prevYL=0;this.prevYR=0;
    var fc=160;
    var dt=1/sampleRate;
    var rc=1/(2*Math.PI*fc);
    this.hpAlpha=rc/(rc+dt);
    this.windowSamples=Math.max(128,Math.round(sampleRate*0.025));
  }
  process(inputs,outputs){
    var input=inputs[0];
    var output=outputs[0];
    if(!input||!input[0])return true;
    var left=input[0];
    var right=input[1]||left;
    var outL=output&&output[0];
    var outR=output&&output[1];
    for(var i=0;i<left.length;i+=1){
      var xL=left[i]||0;
      var xR=right[i]||0;
      if(outL)outL[i]=xL;
      if(outR)outR[i]=xR;
      var yL=this.hpAlpha*(this.prevYL+xL-this.prevXL);
      var yR=this.hpAlpha*(this.prevYR+xR-this.prevXR);
      this.prevXL=xL;this.prevXR=xR;this.prevYL=yL;this.prevYR=yR;
      var m=(yL+yR)*0.5;
      var s=(yL-yR)*0.5;
      this.eL+=yL*yL;
      this.eR+=yR*yR;
      this.cross+=yL*yR;
      this.mid+=m*m;
      this.side+=s*s;
      this.samples+=1;
    }
    if(this.samples>=this.windowSamples){
      var eps=1e-12;
      var rmsL=Math.sqrt(this.eL/this.samples);
      var rmsR=Math.sqrt(this.eR/this.samples);
      var corr=this.cross/Math.sqrt(Math.max(eps,this.eL*this.eR));
      if(!Number.isFinite(corr))corr=1;
      corr=Math.max(-1,Math.min(1,corr));
      var ms=this.mid+this.side;
      var sideRatio=ms>eps?this.side/ms:0;
      var sumRms=rmsL+rmsR;
      var balance=sumRms>eps?(rmsL-rmsR)/sumRms:0;
      var rms=Math.sqrt((this.eL+this.eR)/(Math.max(1,this.samples)*2));
      this.port.postMessage({corr:corr,sideRatio:sideRatio,balance:balance,rms:rms});
      this.samples=0;this.eL=0;this.eR=0;this.cross=0;this.mid=0;this.side=0;
    }
    return true;
  }
}
registerProcessor('pocket-spatial-steering-analyzer',PocketSpatialSteeringAnalyzer);

(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports){module.exports=api;}
  if(root){root.PocketSpatialCore=api;}
}(this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,v));}
  function exp01(x,shape){x=clamp(Number(x)||0,0,1);shape=Math.max(0.01,Number(shape)||1);return (Math.exp(shape*x)-1)/(Math.exp(shape)-1);}
  function signedPow(x,p){var s=x<0?-1:1;return s*Math.pow(Math.abs(x),p);}

  function calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent){
    var rawSpace=clamp(Number(spacePercent)||0,0,250);
    var rawAngle=clamp(Number(angleDegrees)||0,0,180);
    var rawStretch=clamp(Number(delayStretchPercent)||100,25,800);

    var spaceNorm=rawSpace/250;
    var spaceCurve=exp01(spaceNorm,3.3);
    var wet=2.8*spaceCurve;

    var angleNorm=rawAngle/180;
    var angleCurve=exp01(angleNorm,4.2);
    var baseDelayMs=0.08+7.2*angleCurve;

    var stretchNorm=(rawStretch-25)/(800-25);
    var stretchCurve=0.25+11.75*exp01(stretchNorm,3.8);
    var itd=(baseDelayMs*stretchCurve)/1000;

    var cutoff=clamp(Number(headShadowHz)||3300,400,12000);
    var polarity=clamp(Number(crossfeedPolarityPercent)||0,-100,100)/100;
    var polarityCurve=signedPow(polarity,0.72);
    var farGain=(0.04+0.78*spaceCurve)*polarityCurve;
    var directGain=Math.max(0.16,1-(0.48*spaceCurve));

    return{
      rawSpace:rawSpace,
      wet:wet,
      deg:rawAngle,
      angleCurve:angleCurve,
      stretch:stretchCurve,
      itd:itd,
      cutoff:cutoff,
      polarity:polarity,
      farGain:farGain,
      directGain:directGain
    };
  }

  function calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent){
    var rawDepth=clamp(Number(depthPercent)||0,0,300);
    var depthCurve=exp01(rawDepth/300,3.4);
    var rawRoom=clamp(Number(roomScalePercent)||100,25,600);
    var roomNorm=(rawRoom-25)/(600-25);
    var roomCurve=0.32+7.68*exp01(roomNorm,3.3);
    var tone=clamp(Number(reflectionToneHz)||3300,300,12000);
    var wrapRaw=clamp(Number(roomWrapPercent)||0,0,300);
    var wrapCurve=exp01(wrapRaw/300,3.8);

    return{
      depth:3.2*depthCurve,
      roomScale:roomCurve,
      refl1DelayL:(0.013+0.037*roomCurve),
      refl1DelayR:(0.017+0.043*roomCurve),
      refl2DelayL:(0.031+0.074*roomCurve),
      refl2DelayR:(0.037+0.086*roomCurve),
      refl1Gain:0.50*depthCurve,
      refl2Gain:0.34*depthCurve,
      reflCutoff:tone,
      reflQ:0.55,
      wrapRaw:wrapRaw,
      wrapCurve:wrapCurve,
      wrapDelayL1:0.055+0.085*roomCurve,
      wrapDelayR1:0.067+0.101*roomCurve,
      wrapDelayL2:0.118+0.151*roomCurve,
      wrapDelayR2:0.137+0.176*roomCurve,
      wrapGain1:0.58*wrapCurve,
      wrapGain2:0.38*wrapCurve,
      wrapCutoff:Math.max(550,Math.min(tone*0.72,7200))
    };
  }

  function appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var p=calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent);
    var d=calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent);
    var active=!!enabled;
    var farGain=active?p.farGain:0;
    var directGain=active?p.directGain:1;
    var refl1Gain=active?d.refl1Gain:0;
    var refl2Gain=active?d.refl2Gain:0;
    var wrapGain1=active?d.wrapGain1:0;
    var wrapGain2=active?d.wrapGain2:0;
    var worstCaseSum=Math.abs(directGain)+Math.abs(farGain)+Math.abs(refl1Gain)+Math.abs(refl2Gain)+Math.abs(wrapGain1)+Math.abs(wrapGain2);
    var masterGain=active?Math.min(0.90,0.78/Math.max(1,worstCaseSum)):1;

    return{
      wet:p.wet,
      deg:p.deg,
      depth:d.depth,
      delayStretch:p.stretch,
      delaySeconds:p.itd,
      cutoffHz:p.cutoff,
      polarity:p.polarity,
      farGain:farGain,
      directGain:directGain,
      roomScale:d.roomScale,
      refl1DelayL:d.refl1DelayL,
      refl1DelayR:d.refl1DelayR,
      refl2DelayL:d.refl2DelayL,
      refl2DelayR:d.refl2DelayR,
      refl1Gain:refl1Gain,
      refl2Gain:refl2Gain,
      reflCutoff:d.reflCutoff,
      reflQ:d.reflQ,
      wrapRaw:d.wrapRaw,
      wrapDelayL1:d.wrapDelayL1,
      wrapDelayR1:d.wrapDelayR1,
      wrapDelayL2:d.wrapDelayL2,
      wrapDelayR2:d.wrapDelayR2,
      wrapGain1:wrapGain1,
      wrapGain2:wrapGain2,
      wrapCutoff:d.wrapCutoff,
      masterGain:masterGain
    };
  }

  function readouts(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled);
    return{
      spaceText:Math.round(Number(spacePercent)||0)+'% → '+Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'° → '+(t.delaySeconds*1000).toFixed(2)+' ms',
      depthText:Math.round(Number(depthPercent)||0)+'% → '+Math.round(t.depth*100)+'%',
      delayStretchText:Math.round(t.delayStretch*100)+'%',
      headShadowText:Math.round(t.cutoffHz)+' Hz',
      roomScaleText:Math.round(Number(roomScalePercent)||0)+'% → '+t.roomScale.toFixed(2)+'×',
      reflectionToneText:Math.round(t.reflCutoff)+' Hz',
      polarityText:(t.polarity<0?'INVERTED ':'NORMAL ')+Math.round(Math.abs(t.polarity)*100)+'%',
      roomWrapText:Math.round(Number(roomWrapPercent)||0)+'% → '+Math.round(t.wrapGain1*100)+'%',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',
      cutoffText:Math.round(t.cutoffHz)+' Hz',
      farText:(t.farGain<0?'-':'')+Math.round(Math.abs(t.farGain)*100)+'%',
      directText:Math.round(t.directGain*100)+'%',
      reflectionTimesText:Math.round(t.refl1DelayL*1000)+'/'+Math.round(t.refl1DelayR*1000)+' · '+Math.round(t.refl2DelayL*1000)+'/'+Math.round(t.refl2DelayR*1000)+' ms',
      reflectionGainText:(t.refl1Gain*100).toFixed(1)+'% / '+(t.refl2Gain*100).toFixed(1)+'%',
      wrapTimesText:Math.round(t.wrapDelayL1*1000)+'/'+Math.round(t.wrapDelayR1*1000)+' · '+Math.round(t.wrapDelayL2*1000)+'/'+Math.round(t.wrapDelayR2*1000)+' ms',
      wrapGainText:(t.wrapGain1*100).toFixed(1)+'% / '+(t.wrapGain2*100).toFixed(1)+'%',
      reflectionCutoffText:Math.round(t.reflCutoff)+' Hz',
      masterText:Math.round(t.masterGain*100)+'%'
    };
  }

  return{calculate:calculate,calculateDepth:calculateDepth,appliedTargets:appliedTargets,readouts:readouts};
}));

/* Pocket Spatial Bluetooth Matrix Surround experimental output stage. */
(function(root){
  'use strict';
  if(typeof window==='undefined'||typeof document==='undefined')return;
  var AudioNodeCtor=root.AudioNode;
  if(!AudioNodeCtor||!AudioNodeCtor.prototype||!AudioNodeCtor.prototype.connect||root.PocketSpatialMatrix)return;

  var originalConnect=AudioNodeCtor.prototype.connect;
  var routes=[];
  var enabled=true;
  var amount=0.34;
  var patching=false;
  var ui=null;

  function connectRaw(node,destination,output,input){
    if(output==null)return originalConnect.call(node,destination);
    if(input==null)return originalConnect.call(node,destination,output);
    return originalConnect.call(node,destination,output,input);
  }

  function setParam(param,value,ctx){
    if(!param)return;
    try{param.setTargetAtTime(value,ctx.currentTime,0.025);}catch(e){param.value=value;}
  }

  function makeHilbertKernel(ctx,taps){
    taps=taps||129;
    if(taps%2===0)taps+=1;
    var impulse=ctx.createBuffer(1,taps,ctx.sampleRate);
    var data=impulse.getChannelData(0);
    var mid=(taps-1)/2;
    for(var n=0;n<taps;n+=1){
      var k=n-mid;
      var h=0;
      if(k!==0&&Math.abs(k%2)===1)h=2/(Math.PI*k);
      var window=0.42-0.5*Math.cos((2*Math.PI*n)/(taps-1))+0.08*Math.cos((4*Math.PI*n)/(taps-1));
      data[n]=h*window;
    }
    return impulse;
  }

  function makeRoute(source,destination){
    var ctx=source.context;
    var splitter=ctx.createChannelSplitter(2);
    var merger=ctx.createChannelMerger(2);
    var frontL=ctx.createGain(),frontR=ctx.createGain();
    var sideL=ctx.createGain(),sideR=ctx.createGain(),side=ctx.createGain();
    var hp=ctx.createBiquadFilter(),lp=ctx.createBiquadFilter(),hilbert=ctx.createConvolver();
    var rearL=ctx.createGain(),rearR=ctx.createGain();
    var protect=ctx.createDynamicsCompressor(),trim=ctx.createGain();

    hp.type='highpass';hp.frequency.value=140;hp.Q.value=.55;
    lp.type='lowpass';lp.frequency.value=7200;lp.Q.value=.55;
    hilbert.normalize=false;hilbert.buffer=makeHilbertKernel(ctx,129);
    sideL.gain.value=.5;sideR.gain.value=-.5;
    protect.threshold.value=-3;protect.knee.value=4;protect.ratio.value=12;protect.attack.value=.003;protect.release.value=.10;

    patching=true;
    try{
      connectRaw(source,splitter);
      connectRaw(splitter,frontL,0);connectRaw(frontL,merger,0,0);
      connectRaw(splitter,frontR,1);connectRaw(frontR,merger,0,1);
      connectRaw(splitter,sideL,0);connectRaw(sideL,side);
      connectRaw(splitter,sideR,1);connectRaw(sideR,side);
      connectRaw(side,hp);connectRaw(hp,lp);connectRaw(lp,hilbert);
      connectRaw(hilbert,rearL);connectRaw(rearL,merger,0,0);
      connectRaw(hilbert,rearR);connectRaw(rearR,merger,0,1);
      connectRaw(merger,protect);connectRaw(protect,trim);connectRaw(trim,destination);
    }finally{patching=false;}

    var route={ctx:ctx,rearL:rearL,rearR:rearR,trim:trim};
    routes.push(route);
    applyRoute(route);
  }

  function applyRoute(route){
    var a=enabled?amount:0;
    setParam(route.rearL.gain,a,route.ctx);
    setParam(route.rearR.gain,-a,route.ctx);
    setParam(route.trim.gain,enabled?0.78:0.94,route.ctx);
  }

  function applyAll(){for(var i=0;i<routes.length;i+=1)applyRoute(routes[i]);updateUI();}

  AudioNodeCtor.prototype.connect=function(destination,output,input){
    if(patching||!destination||!this.context||destination!==this.context.destination){return originalConnect.apply(this,arguments);}
    makeRoute(this,destination);
    return destination;
  };

  function runSteeringTest(){
    var AC=root.AudioContext||root.webkitAudioContext;if(!AC)return;
    var ctx;try{ctx=new AC();}catch(e){return;}
    var sr=ctx.sampleRate||48000,segment=1.05,gap=.28,count=5,total=Math.ceil(sr*(count*(segment+gap)));
    var buffer=ctx.createBuffer(2,total,sr),left=buffer.getChannelData(0),right=buffer.getChannelData(1);
    var f=700,amp=.22;
    function env(t){var edge=.035;if(t<edge)return t/edge;if(t>segment-edge)return Math.max(0,(segment-t)/edge);return 1;}
    for(var pos=0;pos<count;pos+=1){
      var start=Math.floor(pos*(segment+gap)*sr),frames=Math.floor(segment*sr);
      for(var i=0;i<frames;i+=1){
        var t=i/sr,e=env(t),s=Math.sin(2*Math.PI*f*t)*amp*e,q=Math.sin(2*Math.PI*f*t+Math.PI/2)*amp*e,l=0,r=0;
        if(pos===0){l=s;}
        else if(pos===1){l=s*.707;r=s*.707;}
        else if(pos===2){r=s;}
        else if(pos===3){l=-q*.49;r=q*.871;}
        else {l=-q*.871;r=q*.49;}
        left[start+i]=l;right[start+i]=r;
      }
    }
    var src=ctx.createBufferSource();src.buffer=buffer;patching=true;try{connectRaw(src,ctx.destination);}finally{patching=false;}
    if(ctx.state==='suspended'&&ctx.resume)ctx.resume();src.start(0);
    if(ui&&ui.button){ui.button.textContent='TEST PLAYING · FL C FR SR SL';root.setTimeout(updateUI,Math.ceil((total/sr)*1000)+300);}
    src.onended=function(){try{ctx.close();}catch(e){}};
  }

  function addUI(){
    if(ui||!document.body)return;
    var hero=document.querySelector('.card.hero');if(!hero||!hero.parentNode)return;
    var card=document.createElement('div');card.className='card';card.id='matrixSurroundCard';
    var title=document.createElement('div');title.textContent='RECEIVER MATRIX SURROUND · BLUETOOTH EXPERIMENT';title.style.fontWeight='700';title.style.fontSize='12px';title.style.letterSpacing='.06em';card.appendChild(title);
    var note=document.createElement('div');note.className='status';note.textContent='Bluetooth stays stereo. Pocket Spatial embeds phase-coded rear ambience for a receiver matrix decoder. Select Dolby Pro Logic / Pro Logic II / a matrix-surround mode on the receiver.';card.appendChild(note);
    var button=document.createElement('button');button.type='button';button.className='primary';button.addEventListener('click',function(){enabled=!enabled;applyAll();});card.appendChild(button);
    var wrap=document.createElement('div');wrap.className='ctrl';var label=document.createElement('label');var span=document.createElement('span');span.textContent='REAR STEERING';var read=document.createElement('b');label.appendChild(span);label.appendChild(read);wrap.appendChild(label);
    var slider=document.createElement('input');slider.type='range';slider.min='0';slider.max='100';slider.step='1';slider.value=String(Math.round(amount*100));slider.addEventListener('input',function(){amount=Number(slider.value)/100;applyAll();});wrap.appendChild(slider);card.appendChild(wrap);
    var test=document.createElement('button');test.type='button';test.textContent='TEST RECEIVER: FL → C → FR → SR → SL';test.addEventListener('click',runSteeringTest);card.appendChild(test);
    var caveat=document.createElement('div');caveat.className='legal';caveat.textContent='Experimental Lt/Rt-style matrixing. Exact steering depends on the receiver decoder and on how well the Bluetooth codec preserves inter-channel phase.';card.appendChild(caveat);
    hero.parentNode.insertBefore(card,hero.nextSibling);ui={button:button,read:read};updateUI();
  }

  function updateUI(){if(!ui)return;ui.button.textContent=enabled?'MATRIX SURROUND ON':'MATRIX SURROUND OFF';ui.read.textContent=Math.round(amount*100)+'%';}

  root.PocketSpatialMatrix={version:'20260907-bt-matrix-1',setEnabled:function(v){enabled=!!v;applyAll();},isEnabled:function(){return enabled;},setAmount:function(v){amount=Math.max(0,Math.min(1,Number(v)||0));applyAll();},getAmount:function(){return amount;},routes:routes};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',addUI);else addUI();
}(this));

(function(){
  'use strict';
  if(typeof document==='undefined')return;
  var build='20260907-bt-matrix-1';
  function versioned(src){return src+'?v='+build;}
  function load(src,next){var script=document.createElement('script');script.src=versioned(src);script.async=false;if(next)script.onload=next;document.head.appendChild(script);}
  load('pocket-spatial-commons-buffered.js',function(){load('pocket-spatial-single-playback.js',function(){load('pocket-spatial-buffered-catalog.js',function(){load('pocket-spatial-audius-catalog.js',function(){load('pocket-spatial-buffer-probe.js');});});});});
}());

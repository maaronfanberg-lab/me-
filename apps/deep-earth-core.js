import {makeVoices,sm,clamp} from './deep-earth-voices.js';
const G=(c,v=1)=>{const x=c.createGain();x.gain.value=v;return x};
const F=(c,t,h)=>{const x=c.createBiquadFilter();x.type=t;x.frequency.value=h;x.Q.value=.707;return x};
function impulse(c){const n=Math.floor(c.sampleRate*3.25),b=c.createBuffer(1,n,c.sampleRate),a=b.getChannelData(0);let seed=29713;for(let i=0;i<n;i++){seed=(Math.imul(seed,1664525)+1013904223)|0;a[i]=((seed>>>0)/2147483648-1)*Math.exp(-7*i/n)*(1-Math.exp(-i/260))}return b}
export function createEngine(c,P,opt={}){
 const mix=G(c,.77),hi1=F(c,'highpass',P.lowcut),hi2=F(c,'highpass',P.lowcut),comp=c.createDynamicsCompressor(),master=G(c,opt.offline?P.master:0),lim=c.createDynamicsCompressor();
 comp.threshold.value=-20;comp.knee.value=12;comp.ratio.value=3;comp.attack.value=.025;comp.release.value=.36;
 lim.threshold.value=-4.5;lim.knee.value=0;lim.ratio.value=20;lim.attack.value=.003;lim.release.value=.12;
 mix.connect(hi1);hi1.connect(hi2);hi2.connect(comp);comp.connect(master);master.connect(lim);
 const stereo=G(c,1),mono=G(c,0),split=c.createChannelSplitter(2),left=G(c,.5),right=G(c,.5),sum=G(c,1);
 lim.connect(stereo);stereo.connect(c.destination);lim.connect(split);
 split.connect(left,0);split.connect(right,1);left.connect(sum);right.connect(sum);sum.connect(mono);mono.connect(c.destination);
 const analyser=c.createAnalyser();analyser.fftSize=2048;analyser.smoothingTimeConstant=.8;lim.connect(analyser);
 const lowL=F(c,'lowpass',105),lowR=F(c,'lowpass',105),aL=c.createAnalyser(),aR=c.createAnalyser(),silence=G(c,0);
 aL.fftSize=aR.fftSize=2048;split.connect(lowL,0);split.connect(lowR,1);lowL.connect(aL);lowR.connect(aR);aL.connect(silence);aR.connect(silence);silence.connect(c.destination);
 const atmos=G(c),atHP=F(c,'highpass',175),atHP2=F(c,'highpass',175),air=F(c,'highshelf',1450);
 atmos.connect(atHP);atHP.connect(atHP2);atHP2.connect(air);air.connect(mix);
 const eSend=G(c,P.echo*.34),eHP=F(c,'highpass',225),eHP2=F(c,'highpass',225),delay=c.createDelay(2),damp=F(c,'lowpass',2400),feedback=G(c,P.feedback),eWet=G(c,.6),ePost=F(c,'highpass',205);
 atmos.connect(eSend);eSend.connect(eHP);eHP.connect(eHP2);eHP2.connect(delay);delay.delayTime.value=P.echoTime;
 delay.connect(damp);damp.connect(feedback);feedback.connect(delay);delay.connect(eWet);eWet.connect(ePost);ePost.connect(mix);
 const vSend=G(c,P.reverb*.59),vHP=F(c,'highpass',240),reverb=c.createConvolver(),vWet=G(c,.43),vPost=F(c,'highpass',205);
 reverb.buffer=impulse(c);atmos.connect(vSend);vSend.connect(vHP);vHP.connect(reverb);reverb.connect(vWet);vWet.connect(vPost);vPost.connect(mix);
 const voices=makeVoices(c,P,mix,atmos);
 return {c,voices,master,analyser,aL,aR,
 apply(k,v){switch(k){
 case'master':sm(master.gain,v,c,.13);break;
 case'lowcut':sm(hi1.frequency,v,c);sm(hi2.frequency,v,c);break;
 case'reverb':sm(vSend.gain,v*.59,c);break;
 case'echo':sm(eSend.gain,v*.34,c);break;
 case'echoTime':sm(delay.delayTime,v,c,.22);break;
 case'feedback':sm(feedback.gain,clamp(v,0,.6),c);break;
 case'air':sm(air.gain,(v-.45)*10,c);break;
 case'dwell':voices.chord(voices.chordIndex);break;
 case'motion':voices.update(c.currentTime);break;
 default:voices.apply(k,v);
 }},
 setSpace(m){voices.spatial(m)},
 setMono(on){sm(stereo.gain,on?0:1,c,.04);sm(mono.gain,on?1:0,c,.04)},
 output(v,sec=.13){sm(master.gain,v,c,sec)},
 update(){voices.update(c.currentTime)},
 stop(){voices.stop();master.disconnect()},
 lowCorrelation(){let L=new Float32Array(2048),R=new Float32Array(2048);aL.getFloatTimeDomainData(L);aR.getFloatTimeDomainData(R);let dot=0,l=0,r=0;for(let i=0;i<L.length;i++){dot+=L[i]*R[i];l+=L[i]*L[i];r+=R[i]*R[i]}return l+r<1e-9?null:clamp(dot/Math.sqrt(l*r+1e-15),-1,1)}
 };
}
# Stage F, calibration (preview), after measuring the first version (f1_verify.mjs):
#  - Reverb time ran long by 4-10% above 0.6 s (allpass group delay is longest at low frequencies, so
#    the slowest parts of the tail decay more slowly than the averaged trip-time formula assumes) and
#    could not go below about 0.5 s (one trip round Dattorro's figure-of-eight is 0.73 s). Measured
#    ratio fits 1 + 0.0907 T^-0.29 within 1.5% over 0.6-12 s; the design time is solved so the
#    measured T60 equals the setting. Knob minimum raised to 0.6 s.
#  - Level: the reverb alone at 100% measured 2.66 dB above the dry sound; rvK brings it to match.
#  - Hush: the 10 ms fade after Hush fed the cleared reverb again; the reverb is cleared again when
#    the body is reset at the end of the fade.
# Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1, where='page'):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT ({where}): expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

def eng(old, new):
    global s
    assert '`' not in new and '${' not in new, 'ABORT: template characters in engine edit'
    a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a); seg = s[a:b]
    if seg.count(old) != 1:
        sys.exit(f'ABORT (engine): expected 1 match, found {seg.count(old)}: {old[:90]!r}')
    s = s[:a] + seg.replace(old, new) + s[b:]

eng("    this.rvDec=Math.exp(Math.log(0.001)*trip/(4*Math.max(0.1,this.rvTime)));\n",
    "    // measured T60 runs long by r(T) = 1 + 0.0907 T^-0.29 (f1_verify): solve T_d * r(T_d) = setting\n"
    "    const Ts=Math.max(0.6,this.rvTime); let Td=Ts; for(let it=0;it<6;it++) Td=Ts/(1+0.0907*Math.pow(Td,-0.29));\n"
    "    this.rvDec=Math.exp(Math.log(0.001)*trip/(4*Td));\n")
eng("    this.rvDec=0.5; this.rvDd2=0.5; this.rvDamp=0; this.rvPreN=0; this.rvK=1; this.rvOutL=0; this.rvOutR=0;\n",
    "    this.rvDec=0.5; this.rvDd2=0.5; this.rvDamp=0; this.rvPreN=0; this.rvK=0.736; this.rvOutL=0; this.rvOutR=0;   // rvK: reverb alone at 100% = dry loudness\n")
eng("    this.vRest.fill(1); this.vMute.fill(0); this.anyMute=false;   // P1\n",
    "    this.vRest.fill(1); this.vMute.fill(0); this.anyMute=false;   // P1\n"
    "    if(this.rv) this.rvClear();   // F: also clear what the Hush fade fed into the reverb\n")
rep(" rvTime:{label:'Reverb time',min:0.3,max:12,", " rvTime:{label:'Reverb time',min:0.6,max:12,")
rep("hint:'How long the tail takes to fall by 60 dB.'}",
    "hint:'How long the tail takes to fall by 60 dB (measured below 1 kHz). A plate this size cannot ring much shorter than 0.6 s.'}")
open(P, 'w', encoding='utf-8').write(s)
print('patched OK')

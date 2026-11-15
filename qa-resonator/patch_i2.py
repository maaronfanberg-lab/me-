# Stage I, revision 2 (preview): while a circle is picked up, the next tap always puts it down.
# Before: carrying the mic, a tap within reach of the strike circle picked up the strike instead, so a
# ball near the other circle could not be reached by tap-then-tap. On the phone's short canvas (252 px
# tall in Playwright's iPhone 13) the two 30 px reaches cover much of the tank; WebKit CI hit it
# (mic #33 stayed put, target #45). Now: tap the carried circle itself to put it back; any other tap,
# even on the other circle, puts the carried one there (stacking them is allowed). A press-and-slide on
# the other circle still moves that one.
# Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:100]!r}')
    s = s.replace(old, new)

rep("""    if(state.carry===d.kind){ state.carry=null; toolMsg(''); return; }   // tapped again: put it back down
    state.carry=d.kind;""",
"""    if(state.carry===d.kind){ state.carry=null; toolMsg(''); return; }   // tapped again: put it back down
    if(state.carry){ const i=pick(x,y,true); if(i>=0&&placeMarker(state.carry,i)) audition(); state.carry=null; toolMsg(''); return; }   // I2: carrying one, a tap on the other still puts the carried one there
    state.carry=d.kind;""")

open(P, 'w', encoding='utf-8').write(s)
print('patched OK')

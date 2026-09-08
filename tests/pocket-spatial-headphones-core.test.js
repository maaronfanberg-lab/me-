'use strict';
const assert=require('assert');
const core=require('../apps/pocket-spatial-headphones-core.js');

const def=core.calculate({});
assert.strictEqual(def.crossHighpassHz,140,'spatial sends must high-pass bass');
assert.ok(def.masterGain<=0.90,'master must retain headroom');
assert.ok(def.outputBudget<=0.781,'worst-case spatial sum must remain within the 0.78 budget');
assert.ok(def.crossDelaySeconds>0 && def.crossDelaySeconds<0.001,'cross-ear delay should remain sub-millisecond');
assert.ok(def.refl1DelayL>=0.013 && def.refl2DelayR<=0.07,'early reflections must stay in the short externalization window');

const maxed=core.calculate({externalize:100,width:100,depth:100,room:100,headShadow:7000});
assert.ok(maxed.outputBudget<=0.781,'maximum preset must still obey the output budget');
assert.ok(maxed.refl2DelayR<0.07,'maximum room must avoid long slap-echo taps');

const quiet=core.calculate({externalize:0,width:0,depth:0,room:0});
assert.ok(quiet.widthGain===0 && quiet.refl1Gain===0 && quiet.refl2Gain===0,'zero width/depth must silence those enhancement sends');
console.log('Pocket Spatial Headphones core tests passed');

'use strict';
// Live, measured-data check. Exit nonzero when no station produces a fresh wave.
// Never uses a fixture, simulated data, or synthetic readings.
const assert=require('node:assert/strict');
const CAP=require('./capture-latest.js')(require('./mseed.js')());
const stations=[
  ['IU','ANMO','00','BHZ','Albuquerque'],
  ['IU','HRV','00','BHZ','Harvard'],
  ['IU','POHA','00','BHZ','Hawaii'],
  ['IU','MAJO','00','BHZ','Japan']
];
(async()=>{
  for(const s of stations){
    try {
      const at=Date.now(),r=await CAP.capture(s,{at});
      console.log(JSON.stringify({station:r.id,source:r.source,startUTC:new Date(r.startT).toISOString(),
        latestUTC:new Date(r.endT).toISOString(),ageSeconds:Math.round((Date.now()-r.endT)/1000),
        originalSamples:r.raw.length,rate:r.rate,warning:r.warning,errors:r.errors}));
      assert.ok(r.raw.length>=2);
      assert.ok(r.endT<=Date.now()+30000,'No future-dated readings');
      if(Date.now()-r.endT <=120000){console.log('FRESH_MEASURED_SAMPLES_VERIFIED');return;}
    }catch(err){console.error(s[0]+'.'+s[1]+': '+(err.stack||err));}
  }
  throw Error('No fresh original seismograph samples confirmed at test time.');
})().catch(e=>{console.error(e.message);process.exitCode=1;});

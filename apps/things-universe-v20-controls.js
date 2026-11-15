$('#add').onclick=()=>{let v=$('#q').value.trim();if(v){$('#q').value='';addThing(v)}};
$('#q').onkeydown=e=>{if(e.key==='Enter'){$('#add').click();e.preventDefault()}};
$('#auto').onclick=toggle;$('#bridge').onclick=findBridge;$('#explain').onclick=explain;$('#fit').onclick=fit;$('#reset').onclick=reset;$('#rx').onclick=()=>$('#reader').classList.remove('open');
$('#zp').onclick=()=>{let r=canvas.getBoundingClientRect();setZoomAt(view.k*1.6,r.left+r.width/2,r.top+r.height/2)};
$('#zm').onclick=()=>{let r=canvas.getBoundingClientRect();setZoomAt(view.k/1.6,r.left+r.width/2,r.top+r.height/2)};
canvas.addEventListener('wheel',e=>{e.preventDefault();setZoomAt(view.k*Math.exp(-e.deltaY*.0015),e.clientX,e.clientY)},{passive:false});

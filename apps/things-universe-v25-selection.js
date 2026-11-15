'use strict';
let connectMode=false, connectSelection=[];
function selNodes(){return connectSelection.map(byId).filter(Boolean)}
function isConnectSelected(n){return !!n&&connectSelection.includes(n.id)}
function renderSelectionMarks(){
  let host=$('#selmarks');if(!host)return;let ns=selNodes();
  while(host.children.length<ns.length){let d=document.createElement('div');d.className='selmark';host.appendChild(d)}
  while(host.children.length>ns.length)host.lastChild.remove();
  ns.forEach((n,i)=>{let d=host.children[i],x=view.x+n.x*view.k,y=view.y+n.y*view.k;d.textContent=String(i+1);d.style.transform=`translate(${x-13}px,${y-13}px)`});
}
function selectionAnimation(){renderSelectionMarks();requestAnimationFrame(selectionAnimation)}
function updateConnectUI(){
  let btn=$('#connect'),bar=$('#selectbar'),txt=$('#seltext'),go=$('#selExplain');
  if(btn){btn.classList.toggle('on',connectMode);btn.textContent=connectMode?`Connect: ${connectSelection.length}/4`:'Connect mode'}
  if(bar)bar.classList.toggle('showbar',connectMode||connectSelection.length>0);
  if(txt){let ns=selNodes();txt.textContent=ns.length?ns.map((n,i)=>`${i+1}. ${n.l}`).join('  ·  '):'Tap 2–4 nodes'}
  if(go)go.disabled=connectSelection.length<2;
  let h=$('#hint');if(h)h.textContent=connectMode?'Tap nodes to select · tap again to remove':'Drag a node to move it';
  draw();
}
function toggleConnectMode(){connectMode=!connectMode;if(connectMode)toast('Connect mode: tap 2–4 nodes');updateConnectUI()}
function toggleConnectNode(n){
  if(!n)return;
  let i=connectSelection.indexOf(n.id);
  if(i>=0)connectSelection.splice(i,1);
  else if(connectSelection.length<4)connectSelection.push(n.id);
  else return toast('You can compare up to 4 nodes');
  selected=n;updateConnectUI();
}
function clearConnectSelection(){connectSelection=[];selected=null;updateConnectUI()}
function explainSelected(){
  let ns=selNodes();if(ns.length<2)return toast('Select at least 2 nodes');
  submitClusterDiscovery(ns.map(n=>n.l),'selected')
}
selectionAnimation();

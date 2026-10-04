/* Canvas adapter. The model owns behavior; this file owns DOM and pointer lifecycle. */
'use strict';
(()=>{
 const api=acquireVsCodeApi();
 const app=document.querySelector('#app'),canvas=document.querySelector('#pet'),stage=document.querySelector('#stage');
 const context=canvas.getContext('2d',{willReadFrequently:true});
 const status=document.querySelector('#status'),sleepButton=document.querySelector('#sleep-button');
 const manifest=JSON.parse(app.dataset.manifest),images=new Map();
 const reducedQuery=matchMedia('(prefers-reduced-motion: reduce)');
 let model=null,settings={size:160,typingReactions:false,reducedMotion:false},visible=!document.hidden;
 let timer=null,press=null,frameKey='',lastAnimation='',rect={x:0,y:0,size:160},width=0,height=0,dpr=1;
 let assetsLoaded=false;
 const announceReady=()=>{if(assetsLoaded&&visible)api.postMessage({type:'ready'});};
 const now=()=>performance.now();
 const save=()=>{if(model)api.postMessage({type:'state',state:model.snapshot()});};
 function fit(){
  const bounds=stage.getBoundingClientRect();width=Math.max(1,Math.floor(bounds.width));height=Math.max(1,Math.floor(bounds.height));
  dpr=window.devicePixelRatio||1;canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);context.setTransform(dpr,0,0,dpr,0,0);context.imageSmoothingEnabled=false;
  frameKey='';paint();
 }
 function placement(){
  const size=Math.max(1,Math.min(settings.size,width-16,height-16));
  const position=model.state.position;
  return{x:Math.round(position.x*Math.max(0,width-size)),y:Math.round(position.y*Math.max(0,height-size)),size};
 }
 function paint(){
  if(!model||!visible||!width)return;
  const frame=model.tick(now());rect=placement();
  const metadata=manifest.animations[frame.animation];
  const reduced=settings.reducedMotion||reducedQuery.matches;
  const index=reduced&&frame.animation!=='dragged'?0:frame.index;
  const file=reduced&&metadata.frames&&frame.animation!=='dragged'?metadata.frames[0]:frame.path;
  const key=[file,index,rect.x,rect.y,rect.size,canvas.width,canvas.height].join(':');
  if(key!==frameKey){
   context.clearRect(0,0,width,height);const image=images.get(file)||images.get(manifest.animations.default.frames[0]);
   const cell=metadata.source_cell_size||manifest.cell_size;
   const sx=metadata.spritesheet?index*cell[0]:0;
   if(image)context.drawImage(image,sx,0,cell[0],cell[1],rect.x,rect.y,rect.size,rect.size);
   frameKey=key;
  }
  if(frame.animation!==lastAnimation){
   const messages={idle:'Just hanging out.',blink:'Just hanging out.',heart:'Happy to see you.',wake:'A little stretch…',sleep:'Getting cozy…',sleeping:'Taking a little nap.',pickup:'Up we go!',dragged:'Wheee!',drop:'Back on solid ground.',typing_intro:'Let’s build something.',typing_loop:'Typing alongside you.',typing_outro:'Taking a breather.'};
   status.textContent=messages[frame.animation]||'Just hanging out.';lastAnimation=frame.animation;
  }
  sleepButton.textContent=model.state.sleeping?'Wake':'Sleep';sleepButton.setAttribute('aria-pressed',String(model.state.sleeping));
 }
 function loop(){timer=null;if(!visible||!model)return;paint();timer=setTimeout(loop,settings.reducedMotion||reducedQuery.matches?100:33);}
 function start(){if(timer===null&&visible&&model)loop();}
 function cancelPress(cancelled=true){
  if(!press)return;
  const previous=press;press=null;
  if(previous.dragging){model.endDrag(now(),cancelled);save();}
  if(canvas.hasPointerCapture(previous.id))canvas.releasePointerCapture(previous.id);
  canvas.classList.remove('held');paint();
 }
 function setVisible(value){
  visible=value&&!document.hidden;
  if(!visible){cancelPress();if(timer!==null)clearTimeout(timer);timer=null;}
  else{if(model){model.stopTyping(now());model.started=now();model.nextBlink=now()+8000;}fit();start();}
 }
 function action(name){
  if(!model)return;cancelPress();
  if(name==='pet')model.pet(now());
  else if(name==='sleep')model.toggleSleep(now());
  else if(name==='reset'){model.stopTyping(now());model.state.position={x:.5,y:.8};}
  save();paint();start();
 }
 const coordinate=event=>{const b=canvas.getBoundingClientRect();return{x:event.clientX-b.left,y:event.clientY-b.top};};
 canvas.addEventListener('pointerdown',event=>{
  if(event.button!==0||!event.isPrimary||!model||press)return;
  const point=coordinate(event);
  const x=Math.floor(point.x*dpr),y=Math.floor(point.y*dpr);
  if(x<0||y<0||x>=canvas.width||y>=canvas.height||context.getImageData(x,y,1,1).data[3]<32)return;
  event.preventDefault();canvas.focus();
  press={id:event.pointerId,start:point,last:point,lastAt:now(),origin:{x:rect.x,y:rect.y},dragging:false,velocity:0};
  canvas.setPointerCapture(event.pointerId);
 });
 canvas.addEventListener('pointermove',event=>{
  if(!press||press.id!==event.pointerId)return;
  const point=coordinate(event),time=now(),dx=point.x-press.start.x,dy=point.y-press.start.y;
  if(!press.dragging&&Math.hypot(dx,dy)>=3){press.dragging=true;model.beginDrag(time);canvas.classList.add('held');}
  if(press.dragging){
   const travel=point.x-press.last.x,velocity=travel/Math.max(1,time-press.lastAt)*1000;
   press.velocity=Math.sign(velocity)!==Math.sign(press.velocity)&&Math.abs(travel)>=2?velocity:press.velocity*.72+velocity*.28;
   model.drag(press.velocity,time);
   model.state.position=MochiModel.clampPosition({x:width>rect.size?(press.origin.x+dx)/(width-rect.size):.5,y:height>rect.size?(press.origin.y+dy)/(height-rect.size):.8});
   paint();
  }
  press.last=point;press.lastAt=time;
 });
 canvas.addEventListener('pointerup',event=>{
  if(!press||press.id!==event.pointerId)return;
  const dragged=press.dragging;cancelPress(false);if(!dragged)action('pet');
 });
 canvas.addEventListener('pointercancel',()=>cancelPress());
 canvas.addEventListener('lostpointercapture',()=>cancelPress());
 canvas.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();if(!event.repeat)action('pet');}else if(event.key==='Escape')cancelPress();});
 document.querySelector('#pet-button').addEventListener('click',()=>action('pet'));
 sleepButton.addEventListener('click',()=>action('sleep'));
 document.querySelector('#reset-button').addEventListener('click',()=>action('reset'));
 window.addEventListener('message',event=>{
  const message=event.data;if(!message||typeof message!=='object')return;
  if(message.type==='init'){
   cancelPress();model=new MochiModel.Companion(manifest,message.state);model.started=now();model.nextBlink=now()+8000;
   settings=message.settings;lastAnimation='';frameKey='';fit();start();
  }else if(message.type==='settings'){
   settings=message.settings;if(!settings.typingReactions)model?.stopTyping(now());frameKey='';fit();
  }else if(message.type==='action')action(message.action);
  else if(message.type==='activity'&&visible)model?.activity(now(),settings.typingReactions);
  else if(message.type==='visibility'){
   setVisible(message.visible);if(message.visible)announceReady();
  }
 });
 document.addEventListener('visibilitychange',()=>{setVisible(!document.hidden);if(!document.hidden)announceReady();});
 window.addEventListener('blur',()=>cancelPress());
 window.addEventListener('pagehide',()=>{setVisible(false);observer.disconnect();});
 reducedQuery.addEventListener('change',()=>{frameKey='';paint();});
 const observer=new ResizeObserver(fit);observer.observe(stage);
 const files=[...new Set(Object.values(manifest.animations).flatMap(a=>a.frames||[a.spritesheet]))];
 Promise.all(files.map(file=>new Promise((resolve,reject)=>{
  const image=new Image();image.onload=()=>{images.set(file,image);resolve();};image.onerror=()=>reject(Error(`Unable to load Mochi animation: ${file}`));
  image.src=app.dataset.assets+'/'+file.split('/').map(encodeURIComponent).join('/');
 }))).then(()=>{assetsLoaded=true;announceReady();}).catch(()=>{
  status.textContent='Mochi’s artwork could not load. Try reopening this view.';
  for(const button of document.querySelectorAll('button'))button.disabled=true;
 });
})();

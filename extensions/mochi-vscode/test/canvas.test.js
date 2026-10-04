const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const {createCanvas,Image}=require('@napi-rs/canvas');const model=require('../media/model');
const extension=path.resolve(__dirname,'..');const manifest=require('../media/mochi/manifest.json');
class Element{
 constructor(){this.handlers={};this.textContent='';this.attrs={};this.classList={add(){},remove(){}};}
 addEventListener(name,handler){(this.handlers[name]??=[]).push(handler);}
 emit(name,event={}){for(const callback of this.handlers[name]??[])callback({preventDefault(){},...event});}
 setAttribute(name,value){this.attrs[name]=value;}
 focus(){}
}
async function fixture(options={}){
 let time=0,id=0;const timers=new Map(),messages=[];const elements={};
 for(const name of ['app','pet','stage','status','sleep-button','pet-button','reset-button'])elements[name]=new Element();
 const surface=createCanvas(328,300),pet=elements.pet;let capture=null;
 for(const name of ['width','height'])Object.defineProperty(pet,name,{get:()=>surface[name],set:value=>{surface[name]=value;}});
 pet.getContext=()=>surface.getContext('2d');pet.getBoundingClientRect=()=>({left:0,top:0,width:328,height:300});
 pet.hasPointerCapture=id=>capture===id;pet.setPointerCapture=id=>{capture=id;};pet.releasePointerCapture=()=>{capture=null;};
 elements.stage.getBoundingClientRect=()=>({width:328,height:300});
 elements.app.dataset={manifest:JSON.stringify(manifest),assets:path.join(extension,'media/mochi')};
 const window=new Element();window.devicePixelRatio=1;
 const document=new Element();document.hidden=false;document.querySelector=id=>elements[id.slice(1)];document.querySelectorAll=()=>[];
 const query=new Element();query.matches=false;
 class LocalImage extends Image{set src(file){super.src=fs.readFileSync(file);}get src(){return super.src;}}
 const sandbox={acquireVsCodeApi:()=>({postMessage:m=>messages.push(m)}),document,window,Image:LocalImage,ResizeObserver:class{constructor(cb){this.cb=cb;}observe(){this.cb();}disconnect(){}},matchMedia:()=>query,MochiModel:model,performance:{now:()=>time},setTimeout:cb=>{timers.set(++id,cb);return id;},clearTimeout:id=>timers.delete(id),console};
 vm.runInNewContext(fs.readFileSync(path.join(extension,'media/main.js'),'utf8'),sandbox);
 if(options.earlyVisibility)document.emit('visibilitychange');
 const earlyReady=messages.some(m=>m.type==='ready');
 for(let i=0;i<200&&!messages.some(m=>m.type==='ready');i++)await new Promise(r=>setTimeout(r,5));
 const message=data=>window.emit('message',{data});
 const init=settings=>message({type:'init',state:{sleeping:false,position:{x:.5,y:.8}},settings:{size:160,typingReactions:true,reducedMotion:false,...settings}});
 function advance(milliseconds){const until=time+milliseconds;while(time<until){time+=Math.min(33,until-time);const callbacks=[...timers.values()];timers.clear();for(const cb of callbacks)cb();}}
 const status=()=>elements.status.textContent;
 const point=()=>{const d=surface.getContext('2d').getImageData(0,0,surface.width,surface.height);for(let y=0;y<surface.height;y++)for(let x=0;x<surface.width;x++)if(d.data[(y*surface.width+x)*4+3]>200)return{x,y};throw Error('No real PNG pixels rendered');};
 return{elements,messages,message,init,advance,status,point,timers,document,surface,earlyReady};
}
test('real canonical PNGs render and drag/cancel recover with alpha-aware hit testing',async()=>{
 const f=await fixture();assert.ok(f.messages.some(m=>m.type==='ready'));f.init();
 assert.equal(f.status(),'Just hanging out.');const p=f.point();
 const pet=f.elements.pet;
 pet.emit('pointerdown',{button:0,isPrimary:true,pointerId:1,clientX:0,clientY:0});
 pet.emit('pointermove',{pointerId:1,clientX:20,clientY:20});assert.equal(f.status(),'Just hanging out.');
 pet.emit('pointerdown',{button:0,isPrimary:true,pointerId:1,clientX:p.x,clientY:p.y});
 pet.emit('pointermove',{pointerId:1,clientX:p.x+35,clientY:p.y});f.advance(150);
 assert.equal(f.status(),'Wheee!');pet.emit('pointercancel');f.advance(400);assert.equal(f.status(),'Just hanging out.');
 assert.ok(f.messages.some(m=>m.type==='state'&&m.state.position.x!==.5));
});
test('pet/sleep/wake/reduced motion remain usable and hiding removes all drawing timers',async()=>{
 const f=await fixture();f.init({reducedMotion:true});f.elements['pet-button'].emit('click');assert.equal(f.status(),'Happy to see you.');
 f.advance(2100);assert.equal(f.status(),'Just hanging out.');f.elements['sleep-button'].emit('click');f.advance(900);assert.equal(f.status(),'Taking a little nap.');
 f.elements['sleep-button'].emit('click');f.advance(700);assert.equal(f.status(),'Just hanging out.');
 f.message({type:'visibility',visible:false});assert.equal(f.timers.size,0);
});
test('reset position interrupts active typing before returning to idle',async()=>{
 const f=await fixture();f.init();f.message({type:'activity'});f.advance(600);assert.equal(f.status(),'Typing alongside you.');
 f.elements['reset-button'].emit('click');assert.equal(f.status(),'Taking a breather.');f.advance(400);assert.equal(f.status(),'Just hanging out.');
});

test('early visibility does not announce readiness before the PNG set finishes loading',async()=>{
 const f=await fixture({earlyVisibility:true});assert.equal(f.earlyReady,false);assert.ok(f.messages.some(m=>m.type==='ready'));
});

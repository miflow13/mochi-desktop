'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const NAMES=['default','idle','blink','bounce','squish','heart','pickup','dragged','drop','sleep','sleeping','wake','typing_intro','typing_loop','typing_outro','wave'];
function buildAssets(repo,output){
 const root=path.join(repo,'assets/mochi');
 const original=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
 if(original.format!=='mochi-animation-set-v1'||original.anchor!=='bottom-center'||original.scaling!=='nearest-neighbor')throw Error('Unsupported canonical Mochi asset contract');
 const runtime=fs.readFileSync(path.join(repo,'src/mochi/sprites.py'),'utf8');
 const tuning=fs.readFileSync(path.join(repo,'src/mochi/interaction_tuning.py'),'utf8');
 const manifest={...original,animations:{},provenance:{source:'miflow13/mochi-desktop',manifest_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'manifest.json'))).digest('hex')}};
 const files=new Map();
 for(const name of NAMES){
  const source=original.animations[name];if(!source)throw Error(`Missing canonical animation: ${name}`);
  const a={...source};
  if(!Number.isInteger(a.frame_count)||a.frame_count<1||!(a.fps>0)||!Number.isFinite(a.fps)||typeof a.loop!=='boolean')throw Error(`Invalid animation metadata: ${name}`);
  if(a.frames&&a.frames.length!==a.frame_count)throw Error(`Invalid frame count: ${name}`);
  if(['idle','blink','bounce','squish','sleep','wake'].includes(name)){
   const match=runtime.match(new RegExp(`^${name}_durations = \\(([^)]+)\\)`,'m'));
   if(!match||!/^[\d_,\s]+$/.test(match[1]))throw Error(`Review desktop timing override: ${name}`);
   a.durations_ms=match[1].split(',').map(x=>x.trim()).filter(Boolean).map(x=>Number(x.replaceAll('_','')));
  }
  if(name==='pickup'){
   const match=tuning.match(/^PICKUP_FRAME_DURATION_MS = (\d+)$/m);if(!match)throw Error('Review desktop pickup timing override');
   a.durations_ms=Array(a.frame_count).fill(Number(match[1]));
  }
  if(a.durations_ms&&(a.durations_ms.length!==a.frame_count||a.durations_ms.some(x=>!Number.isFinite(x)||x<=0)))throw Error(`Invalid timing override: ${name}`);
  const cell=a.source_cell_size??original.cell_size;
  for(const relative of a.frames??[a.spritesheet]){
   if(typeof relative!=='string'||relative.startsWith('/')||relative.includes('..')||relative.includes('\\'))throw Error(`Unsafe asset path: ${relative}`);
   const file=path.join(root,relative);if(!fs.existsSync(file))throw Error(`Missing canonical asset: ${relative}`);
   const bytes=fs.readFileSync(file);
   if(bytes.length<24||!bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))throw Error(`Invalid PNG: ${relative}`);
   const width=cell[0]*(a.spritesheet?a.frame_count:1),height=cell[1];
   if(bytes.readUInt32BE(16)!==width||bytes.readUInt32BE(20)!==height)throw Error(`Expected ${width}x${height} PNG: ${relative}`);
   files.set(relative,bytes);
  }
  manifest.animations[name]=a;
 }
 fs.mkdirSync(output,{recursive:true});
 for(const [relative,bytes]of files){const target=path.join(output,relative);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes);}
 fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');return manifest;
}
if(require.main===module){
 const extension=path.resolve(__dirname,'..');const m=buildAssets(path.resolve(extension,'../..'),path.join(extension,'media/mochi'));
 fs.writeFileSync(path.join(extension,'LICENSE'),fs.readFileSync(path.resolve(extension,'../../LICENSE'),'utf8').trimEnd()+'\n');
 console.log(`Prepared ${Object.keys(m.animations).length} canonical animations with desktop timing.`);
}
module.exports={buildAssets};

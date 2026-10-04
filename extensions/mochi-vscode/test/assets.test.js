const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const script=path.join(__dirname,'../scripts/build-assets.js');
const build=fs.existsSync(script)?require(script).buildAssets:undefined;
const repo=path.resolve(__dirname,'../../..');
test('build preserves canonical bytes, strips unrelated animations and carries runtime timing',()=>{
 assert.equal(typeof build,'function');
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'mochi-assets-'));
 try{
  const manifest=build(repo,temp);assert.equal(manifest.anchor,'bottom-center');
  assert.equal(manifest.animations.idle.durations_ms[0],900);
  assert.deepEqual(manifest.animations.pickup.durations_ms,Array(6).fill(20));
  assert.equal(manifest.animations.dance,undefined);
  assert.equal(manifest.animations.wave.source_cell_size[0],64);
  for(const a of Object.values(manifest.animations))for(const f of a.frames||[a.spritesheet]){
   assert.deepEqual(fs.readFileSync(path.join(temp,f)),fs.readFileSync(path.join(repo,'assets/mochi',f)));
  }
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('build rejects missing, wrong-size or escaping asset paths with a useful error',()=>{
 assert.equal(typeof build,'function');
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'mochi-invalid-'));
 try{
  fs.mkdirSync(path.join(temp,'assets/mochi'),{recursive:true});
  const m=JSON.parse(fs.readFileSync(path.join(repo,'assets/mochi/manifest.json')));
  m.animations.default.frames=['../../secret.png'];
  fs.writeFileSync(path.join(temp,'assets/mochi/manifest.json'),JSON.stringify(m));
  fs.mkdirSync(path.join(temp,'src/mochi'),{recursive:true});
  for(const f of ['sprites.py','interaction_tuning.py'])fs.copyFileSync(path.join(repo,'src/mochi',f),path.join(temp,'src/mochi',f));
  assert.throws(()=>build(temp,path.join(temp,'out')),/Unsafe asset path/);
  m.animations.default.frames=['master/mochi_default.png'];
  fs.writeFileSync(path.join(temp,'assets/mochi/manifest.json'),JSON.stringify(m));
  assert.throws(()=>build(temp,path.join(temp,'out')),/Missing canonical asset/);
  fs.mkdirSync(path.join(temp,'assets/mochi/master'));
  const bytes=Buffer.from(fs.readFileSync(path.join(repo,'assets/mochi/master/mochi_default.png')));
  bytes.writeUInt32BE(100,16);
  fs.writeFileSync(path.join(temp,'assets/mochi/master/mochi_default.png'),bytes);
  assert.throws(()=>build(temp,path.join(temp,'out')),/Expected 256x256/);
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
});

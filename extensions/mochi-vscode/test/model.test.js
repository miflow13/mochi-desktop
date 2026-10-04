const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
// A changed completion rule, priority guard or frame-duration lookup breaks these observable behaviors.
const modelPath=path.join(__dirname,'../media/model.js');
const model=fs.existsSync(modelPath)?require(modelPath):{};
const source=require('../../../assets/mochi/manifest.json');
const manifest=JSON.parse(JSON.stringify(source));
manifest.animations.idle.durations_ms=[900,600,450,1100,500,1400];
manifest.animations.pickup.durations_ms=Array(6).fill(20);
manifest.animations.sleep.durations_ms=[90,100,120,140,160,180];
manifest.animations.wake.durations_ms=[70,80,90,100,100,90];
const companion=()=>new model.Companion(manifest);
test('honors uneven desktop idle timing and exact loop boundaries',()=>{
 assert.equal(typeof model.frameAt,'function');
 assert.deepEqual(model.frameAt(manifest.animations.idle,899),{index:0,done:false});
 assert.deepEqual(model.frameAt(manifest.animations.idle,900),{index:1,done:false});
 assert.equal(model.frameAt(manifest.animations.idle,4950).index,0);
});
test('pet plays once, ambient typing cannot steal it, then returns to idle',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.pet(0);c.activity(30,true);
 assert.equal(c.tick(100).animation,'heart');
 assert.equal(c.tick(2000).animation,'idle');
});
test('sleep and wake transitions recover and persist only manual sleep',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.toggleSleep(0);
 assert.equal(c.tick(100).animation,'sleep');
 assert.equal(c.tick(800).animation,'sleeping');assert.equal(c.snapshot().sleeping,true);
 c.pet(900);assert.equal(c.tick(901).animation,'wake');
 assert.equal(c.tick(1500).animation,'idle');assert.equal(c.snapshot().sleeping,false);
});
test('typing enters, loops without restart, then leaves after inactivity',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.activity(0,true);assert.equal(c.tick(0).animation,'typing_intro');
 c.activity(200,true);assert.equal(c.tick(510).animation,'typing_loop');
 c.activity(1000,true);assert.equal(c.tick(1500).animation,'typing_loop');
 assert.equal(c.tick(5100).animation,'typing_outro');assert.equal(c.tick(5600).animation,'idle');
});
test('typing opt-out and sleeping suppress ambient activity',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.activity(0,false);assert.equal(c.tick(50).animation,'idle');
 c.toggleSleep(100);c.activity(200,true);assert.equal(c.tick(900).animation,'sleeping');
});
test('drag reverses named poses and release settles before dropping',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.beginDrag(0);c.drag(-200,130);
 assert.equal(c.tick(131).path,'drag/drag_left_medium.png');
 c.drag(200,160);assert.equal(c.tick(161).path,'drag/drag_right_medium.png');
 c.endDrag(180);assert.equal(c.tick(181).path,'drag/drag_settle_right.png');
 assert.equal(c.tick(260).path,'drag/drag_settle_neutral.png');
 assert.equal(c.tick(400).animation,'drop');assert.equal(c.tick(750).animation,'idle');
});
test('drag cancellation recovers and late activity cannot steal held state',()=>{
 assert.equal(typeof model.Companion,'function');
 const c=companion();c.beginDrag(0);c.activity(100,true);
 assert.equal(c.tick(200).animation,'dragged');
 c.endDrag(210,true);assert.equal(c.tick(211).animation,'drop');
 assert.equal(c.tick(600).animation,'idle');
});
test('invalid persisted values reset safely; coordinates clamp',()=>{
 assert.equal(typeof model.sanitizeState,'function');
 assert.deepEqual(model.sanitizeState({sleeping:'yes',position:{x:NaN,y:Infinity}}),{sleeping:false,position:{x:0.5,y:0.8}});
 assert.deepEqual(model.sanitizeState({sleeping:true,position:{x:2,y:-1}}),{sleeping:true,position:{x:1,y:0}});
});
test('drag hysteresis avoids medium/soft chatter and switches direction',()=>{
 assert.equal(typeof model.dragPose,'function');
 assert.equal(model.dragPose(140,'neutral'),'right_medium');
 assert.equal(model.dragPose(110,'right_medium'),'right_medium');
 assert.equal(model.dragPose(80,'right_medium'),'right_soft');
 assert.equal(model.dragPose(-80,'right_medium'),'left_soft');
});
test('nonlooping frame index holds last frame at end',()=>{
 assert.equal(typeof model.frameAt,'function');
 assert.deepEqual(model.frameAt(manifest.animations.wave,5000),{index:7,done:true});
});

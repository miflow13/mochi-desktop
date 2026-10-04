const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const {chromium}=require('playwright');const {renderWebview}=require('../src/webview');
const extension=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true, executablePath:process.env.MOCHI_CHROMIUM_PATH});
 try{
 const page=await browser.newPage({viewport:{width:360,height:680},deviceScaleFactor:2});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const {browserApi:api}=require('./helpers/browser-api');
 const webview={cspSource:'https://mochi.test',asWebviewUri:u=>u};
 const html=renderWebview(webview,{toString:()=> 'https://mochi.test'},api);
 await page.addInitScript(()=>{window.messages=[];window.acquireVsCodeApi=()=>({postMessage:m=>window.messages.push(m)});});
 await page.route('https://mochi.test/**',async route=>{
  const relative=new URL(route.request().url()).pathname;
  if(relative==='/'){await route.fulfill({body:html,contentType:'text/html'});return;}
  const file=path.join(extension,relative);if(!fs.existsSync(file)){await route.fulfill({status:404});return;}
  const type=file.endsWith('.png')?'image/png':file.endsWith('.css')?'text/css':'text/javascript';
  await route.fulfill({body:fs.readFileSync(file),contentType:type});
 });
 await page.goto('https://mochi.test/');
 await page.waitForFunction(()=>window.messages.some(m=>m.type==='ready'),null,{timeout:3000});
 await page.evaluate(()=>window.dispatchEvent(new MessageEvent('message',{data:{type:'init',state:{sleeping:false,position:{x:.5,y:.8}},settings:{size:160,typingReactions:false,reducedMotion:false}}})));
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Just hanging out.');
 await page.locator('#pet-button').click();await page.waitForFunction(()=>document.querySelector('#status').textContent==='Happy to see you.');
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Just hanging out.');
 await page.locator('#sleep-button').click();await page.waitForFunction(()=>document.querySelector('#sleep-button').textContent==='Wake');
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Taking a little nap.');
 await page.locator('#sleep-button').click();await page.waitForFunction(()=>document.querySelector('#status').textContent==='Just hanging out.');
 // Real alpha pixels locate Mochi independently of transparent cell padding.
 const point=await page.evaluate(()=>{
  const c=document.querySelector('#pet'),ctx=c.getContext('2d'),d=ctx.getImageData(0,0,c.width,c.height),r=c.getBoundingClientRect();
  for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++)if(d.data[(y*c.width+x)*4+3]>200)return{x:r.x+x*r.width/c.width,y:r.y+y*r.height/c.height};
  throw Error('No sprite pixels rendered');
 });
 await page.mouse.move(point.x,point.y);await page.mouse.down();await page.mouse.move(point.x-35,point.y-20,{steps:8});await page.mouse.move(point.x+35,point.y-25,{steps:8});await page.mouse.up();
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Just hanging out.');
 assert.ok(await page.evaluate(()=>window.messages.some(m=>m.type==='state'&&m.state.position.x!==.5)),'drag persists changed placement');
 await page.locator('#reset-button').click();
 await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:220,height:420});
 await page.locator('#pet').focus();await page.keyboard.press('Enter');
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Happy to see you.');
 await page.screenshot({path:process.env.MOCHI_SCREENSHOT||path.join(extension,'../../mochi-vscode-preview.png')});
 assert.deepEqual(errors,[]);
 console.log('Browser smoke: pet, sleep/wake, real PNG pixels, directional drag, persistence, resize, keyboard and reduced motion passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

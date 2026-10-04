const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const file=path.join(__dirname,'../src/webview.js');const render=fs.existsSync(file)?require(file).renderWebview:undefined;
test('webview uses constrained local resources and CSP without inline executable scripts',()=>{
 assert.equal(typeof render,'function');const options={};
 const view={cspSource:'vscode-webview://test',asWebviewUri:u=>u,options};
 const api={Uri:{joinPath:(base,...pieces)=>({toString:()=>base.toString()+'/'+pieces.join('/')})}};
 const html=render(view,{toString:()=> 'file:///mochi'},api);
 assert.match(html,/default-src 'none'/);assert.match(html,/connect-src 'none'/);
 assert.doesNotMatch(html,/unsafe-inline|unsafe-eval|onclick=/);
 assert.equal(view.options.localResourceRoots.length,1);assert.equal(view.options.localResourceRoots[0].toString(),'file:///mochi/media');
 assert.match(html,/aria-label="Pet Mochi"/);assert.match(html,/role="status"/);
});

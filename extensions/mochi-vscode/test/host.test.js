const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const file=path.join(__dirname,'../src/extension.js');const ext=fs.existsSync(file)?require(file):{};
function fixture(){
 const callbacks={},commands=new Map(),sent=[],saved=[],handles=[];let provider;
 const disposable=()=>{const d={disposed:false,dispose(){this.disposed=true;}};handles.push(d);return d;};
 const settings={size:160,typingReactions:false,reducedMotion:false};const document={uri:'secret.py'};
 const api={Uri:{joinPath:(base,...parts)=>({toString:()=>base.toString()+'/'+parts.join('/')})},
  workspace:{getConfiguration:()=>({get:(key,fallback)=>settings[key]??fallback}),onDidChangeConfiguration:cb=>{callbacks.config=cb;return disposable();},onDidChangeTextDocument:cb=>{callbacks.edit=cb;return disposable();}},
  window:{activeTextEditor:{document},registerWebviewViewProvider:(id,p)=>{provider=p;return disposable();}},
  commands:{registerCommand:(id,cb)=>{commands.set(id,cb);return disposable();},executeCommand:async()=>{} }};
 const context={extensionUri:{toString:()=> 'file:///mochi'},subscriptions:[],globalState:{get:()=>({sleeping:false,position:{x:Infinity,y:0}}),update:async(key,state)=>{saved.push(state);}}};
 const view={visible:true,webview:{cspSource:'vscode-resource:',asWebviewUri:u=>u,postMessage:async m=>{sent.push(m);return true;},onDidReceiveMessage:cb=>{callbacks.message=cb;return disposable();}},onDidChangeVisibility:cb=>{callbacks.visibility=cb;return disposable();},onDidDispose:cb=>{callbacks.dispose=cb;return disposable();}};
 return{api,context,view,callbacks,commands,sent,saved,settings,document,handles,get provider(){return provider;}};
}
test('ready restores sanitized state; malformed messages do not reach persistence',async()=>{
 assert.equal(typeof ext.activateWithApi,'function');const f=fixture();ext.activateWithApi(f.context,f.api);f.provider.resolveWebviewView(f.view);
 f.callbacks.message({type:'ready'});assert.equal(f.sent[0].type,'init');assert.deepEqual(f.sent[0].state.position,{x:0.5,y:0.8});
 f.callbacks.message({type:'state',state:{sleeping:'yes',position:{x:1,y:0}}});
 f.callbacks.message({type:'state',state:{sleeping:true,position:{x:NaN,y:0}}});
 await Promise.resolve();assert.equal(f.saved.length,0);
 f.callbacks.message({type:'state',state:{sleeping:true,position:{x:0.2,y:0.9}}});
 await new Promise(r=>setImmediate(r));assert.deepEqual(f.saved[0],{sleeping:true,position:{x:0.2,y:0.9}});
});
test('typing is opt-in, active document only and sends activity without document content',()=>{
 assert.equal(typeof ext.activateWithApi,'function');const f=fixture();ext.activateWithApi(f.context,f.api);f.provider.resolveWebviewView(f.view);f.callbacks.message({type:'ready'});f.sent.length=0;
 const event={document:f.document,contentChanges:[{text:'SECRET source text'}],reason:undefined};
 f.callbacks.edit(event);assert.equal(f.sent.length,0);
 f.settings.typingReactions=true;f.callbacks.edit({...event,document:{}});assert.equal(f.sent.length,0);
 f.callbacks.edit(event);assert.deepEqual(f.sent,[{type:'activity'}]);f.callbacks.edit(event);assert.equal(f.sent.length,1);
});
test('commands queue until ready, settings update and disposed provider releases handlers',async()=>{
 assert.equal(typeof ext.activateWithApi,'function');const f=fixture();ext.activateWithApi(f.context,f.api);
 await f.commands.get('mochi.pet')();f.provider.resolveWebviewView(f.view);f.callbacks.message({type:'ready'});
 assert.equal(f.sent.at(-1).action,'pet');
 f.settings.reducedMotion=true;f.callbacks.config({affectsConfiguration:()=>true});assert.equal(f.sent.at(-1).settings.reducedMotion,true);
 f.provider.dispose();assert.ok(f.handles.filter(h=>h.disposed).length>=5);
});
test('duplicate ready notifications do not overwrite a queued direct action with stale init',async()=>{
 const f=fixture();ext.activateWithApi(f.context,f.api);
 await f.commands.get('mochi.sleep')();f.provider.resolveWebviewView(f.view);
 f.callbacks.message({type:'ready'});f.callbacks.message({type:'ready'});
 assert.equal(f.sent.filter(m=>m.type==='init').length,1);
 assert.equal(f.sent.at(-1).action,'sleep');
});

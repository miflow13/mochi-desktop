'use strict';
const {sanitizeState}=require('../media/model');
const {renderWebview}=require('./webview');
const STATE_KEY='mochi.companion.v1';
function validState(state){
 return state && typeof state.sleeping==='boolean' && state.position && ['x','y'].every(k=>Number.isFinite(state.position[k])&&state.position[k]>=0&&state.position[k]<=1);
}
function activateWithApi(context,api){
 let view=null,ready=false,pending=null,lastActivity=-Infinity,disposed=false;
 let state=sanitizeState(context.globalState.get(STATE_KEY));let writes=Promise.resolve();
 const handlers=[];
 const settings=()=>{
  const config=api.workspace.getConfiguration('mochi');const size=config.get('size',160);
  return{size:Number.isFinite(size)?Math.max(96,Math.min(256,size)):160,typingReactions:config.get('typingReactions',false)===true,reducedMotion:config.get('reducedMotion',false)===true};
 };
 const post=message=>{
  if(view&&!disposed)Promise.resolve(view.webview.postMessage(message)).catch(()=>{});
 };
 const clearView=()=>{for(const handler of handlers.splice(0))handler.dispose();view=null;ready=false;};
 const provider={
  resolveWebviewView(resolved){
   clearView();view=resolved;
   handlers.push(view.webview.onDidReceiveMessage(message=>{
    if(!message||typeof message!=='object'||disposed)return;
    if(message.type==='ready'){
     if(ready||!view?.visible)return;
     ready=true;post({type:'init',state,settings:settings()});
     if(pending){post({type:'action',action:pending});pending=null;}
    }else if(message.type==='state'&&validState(message.state)){
     state=sanitizeState(message.state);const snapshot=state;
     writes=writes.then(()=>context.globalState.update(STATE_KEY,snapshot)).catch(()=>console.error('Mochi could not save companion preferences.'));
    }
   }));
   handlers.push(view.onDidChangeVisibility(()=>{
    if(!view.visible)ready=false;
    post({type:'visibility',visible:view.visible});
   }));
   handlers.push(view.onDidDispose(clearView));
   view.webview.html=renderWebview(view.webview,context.extensionUri,api);
  },
  dispose(){disposed=true;clearView();for(const item of owned.splice(0))item.dispose();}
 };
 const action=async name=>{
  if(disposed)return;
  if(ready&&view?.visible){post({type:'action',action:name});return;}
  pending=name;await api.commands.executeCommand('mochi.companion.focus');
 };
 const owned=[
  api.window.registerWebviewViewProvider('mochi.companion',provider),
  api.workspace.onDidChangeConfiguration(event=>{if(event.affectsConfiguration('mochi'))post({type:'settings',settings:settings()});}),
  api.workspace.onDidChangeTextDocument(event=>{
   if(disposed||!ready||!view?.visible||!settings().typingReactions||event.document!==api.window.activeTextEditor?.document||!event.contentChanges.length)return;
   const now=performance.now();if(now-lastActivity<1000)return;lastActivity=now;post({type:'activity'});
  }),
  api.commands.registerCommand('mochi.show',()=>api.commands.executeCommand('mochi.companion.focus')),
  ...[['mochi.pet','pet'],['mochi.sleep','sleep'],['mochi.resetPosition','reset']].map(([id,name])=>api.commands.registerCommand(id,()=>action(name)))
 ];
 context.subscriptions.push(provider);return provider;
}
function activate(context){return activateWithApi(context,require('vscode'));}
module.exports={activate,activateWithApi};

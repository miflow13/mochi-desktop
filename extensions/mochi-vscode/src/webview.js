'use strict';
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function renderWebview(webview,extensionUri,api){
 const media=api.Uri.joinPath(extensionUri,'media');
 webview.options={enableScripts:true,localResourceRoots:[media]};
 const uri=name=>webview.asWebviewUri(api.Uri.joinPath(media,name)).toString();
 const nonce=crypto.randomBytes(24).toString('base64');
 const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../media/mochi/manifest.json'),'utf8'));
 return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
 <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${escape(webview.cspSource)}; style-src ${escape(webview.cspSource)}; script-src 'nonce-${nonce}'; connect-src 'none';">
 <link rel="stylesheet" href="${escape(uri('style.css'))}"><title>Mochi</title></head>
 <body><main id="app" data-manifest="${escape(JSON.stringify(manifest))}" data-assets="${escape(uri('mochi'))}">
 <header><h1>Mochi <span aria-hidden="true">🌱</span></h1><p>A little company while you build.</p></header>
 <div id="stage"><canvas id="pet" tabindex="0" role="button" aria-label="Pet Mochi" aria-describedby="hint" width="640" height="440"></canvas></div>
 <div class="controls" aria-label="Mochi controls"><button id="pet-button" type="button">Pet</button><button id="sleep-button" type="button" aria-pressed="false">Sleep</button><button id="reset-button" type="button">Reset position</button></div>
 <p id="status" role="status" aria-live="polite">Getting comfortable…</p><p id="hint">Click to pet. Drag to move. Enter or Space to pet.</p>
 </main><script nonce="${nonce}" src="${escape(uri('model.js'))}" defer></script><script nonce="${nonce}" src="${escape(uri('main.js'))}" defer></script></body></html>`;
}
module.exports={renderWebview};

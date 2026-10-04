// Minimal Uri adapter for the browser smoke harness, preserving nested resource roots.
const browserApi={Uri:{joinPath:(base, ...parts)=>({toString:()=>base.toString().replace(/\/$/,'')+'/'+parts.join('/')})}};
module.exports={browserApi};

'use strict';
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
for(const directory of ['src','media','scripts','test']){
 for(const file of fs.readdirSync(path.join(__dirname,'..',directory))){
  if(/\.(js|cjs)$/.test(file))execFileSync(process.execPath,['--check',path.join(__dirname,'..',directory,file)],{stdio:'inherit'});
 }
}
console.log('All extension JavaScript syntax checks passed.');

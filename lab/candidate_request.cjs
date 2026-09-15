const {main,writeResult}=require('../scripts/preview/request.cjs');
const {inspect}=require('./candidate_gate.cjs');
main({inspectRequest:inspect,verify:()=>{}}).then(writeResult).catch(e=>{console.error(e.message);process.exitCode=1;});

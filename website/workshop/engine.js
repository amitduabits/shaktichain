/* Teaching reference, not the original project engine. One unit per identity. */
(function(root){
'use strict';
function numbers(xs){if(!Array.isArray(xs)||xs.some(x=>!Number.isFinite(x)||x<0))throw Error('Use finite, non-negative price arrays.');return xs;}
function clear(bids,asks,mode='mcafee'){
 numbers(bids);numbers(asks);if(!['mcafee','uniform','paybid'].includes(mode))throw Error('Unknown mechanism');
 const b=bids.map((p,id)=>({p,id})).sort((x,y)=>y.p-x.p||x.id-y.id);
 const a=asks.map((p,id)=>({p,id})).sort((x,y)=>x.p-y.p||x.id-y.id);
 let k=0;while(k<Math.min(b.length,a.length)&&b[k].p>=a[k].p)k++;
 let q=0,pb=0,ps=0,branch='no-trade';
 if(k){
  if(mode==='uniform'){q=k;pb=ps=(b[k-1].p+a[k-1].p)/2;branch='accepted-pair midpoint (strategic baseline)';}
  else if(mode==='paybid'){q=Math.max(0,k-1);branch='own-report fallback (deliberately broken)';}
  else {const p=(k<b.length&&k<a.length)?(b[k].p+a[k].p)/2:null;
   if(p!==null&&a[k-1].p<=p&&p<=b[k-1].p){q=k;pb=ps=p;branch='excluded-pair midpoint';}
   else{q=k-1;pb=b[k-1].p;ps=a[k-1].p;branch='trade reduction';}
  }
 }
 const trades=[];for(let j=0;j<q;j++)trades.push({buyer:b[j].id,seller:a[j].id,bid:b[j].p,ask:a[j].p,buyerPays:mode==='paybid'?b[j].p:pb,sellerGets:mode==='paybid'?a[j].p:ps});
 const paid=trades.reduce((s,t)=>s+t.buyerPays,0),received=trades.reduce((s,t)=>s+t.sellerGets,0);
 const welfare=trades.reduce((s,t)=>s+t.bid-t.ask,0),optimum=b.slice(0,k).reduce((s,x,j)=>s+x.p-a[j].p,0);
 return {mode,k,q,branch,buyerPrice:mode==='paybid'?null:pb,sellerPrice:mode==='paybid'?null:ps,paid,received,platformSurplus:paid-received,welfare,optimum,efficiency:optimum>0?welfare/optimum:null,trades};
}
function utility(result,role,id,value){let t=result.trades.find(x=>x[role]===id);return t?(role==='buyer'?value-t.buyerPays:t.sellerGets-value):0;}
function rng(seed){let a=seed>>>0;return()=>{a+=0x6D2B79F5;let t=a;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296;};}
function monteCarlo({seed=42,n=1000,stress=0,block=4}={}){
 if(!Number.isInteger(n)||n<50||n>20000||!Number.isInteger(block)||block<1||block>24||stress<0||stress>1)throw Error('n: 50..20000; block: 1..24; stress: 0..1');
 // Synthetic hourly margin history in INR/kWh. Same empirical marginal distribution.
 const history=Array.from({length:96},(_,i)=>((i%24>=16&&i%24<=21)?-3:1.4)+0.2*Math.sin(i));
 function run(bl,seed2){const r=rng(seed2),profits=[];for(let j=0;j<n;j++){let cash=0,minCash=0,t=0;while(t<24){let start=Math.floor(r()*history.length);for(let z=0;z<bl&&t<24;z++,t++){cash+=history[(start+z)%history.length]-stress;minCash=Math.min(minCash,cash);}}profits.push({cash,minCash});}
 const vals=profits.map(x=>x.cash).sort((a,b)=>a-b),mean=vals.reduce((a,b)=>a+b,0)/n,sd=Math.sqrt(vals.reduce((s,x)=>s+(x-mean)**2,0)/(n-1)),p=profits.filter(x=>x.minCash < -8).length/n;
 return {mean,meanCI:[mean-1.96*sd/Math.sqrt(n),mean+1.96*sd/Math.sqrt(n)],probLiquidityBreach:p,breachSE:Math.sqrt(p*(1-p)/n),p05:vals[Math.floor(.05*n)]};}
 return {label:'Synthetic teaching data; not a project ROI replication',seed,n,stress,block,iid:run(1,seed),blockBootstrap:run(block,seed+1)};
}
function profit({value=10,cost=4,price=7,q=1,fee=0.2,degradation=0.4,network=0.2,fixed=0.1}={}){
 if([value,cost,price,q,fee,degradation,network,fixed].some(x=>!Number.isFinite(x)||x<0))throw Error('Costs, values and quantities must be finite and non-negative');
 return {buyer:(value-price-fee)*q,seller:(price-cost-degradation-network)*q,operator:fee*q-fixed,feasiblePrice:[cost+degradation+network,value-fee],note:'Illustrative INR; excludes jurisdiction-specific taxes and hardware capex.'};
}
function ledger({events=[]}={}){
 if(!Array.isArray(events)||events.length>100)throw Error('Use an event array of at most 100 entries');
 let minted=0,burned=0;const seen=new Set(),log=[];
 for(const e of events){let reason=null;if(!e||!Number.isFinite(e.q)||e.q<=0)reason='Invalid positive quantity';
  else if(e.kind==='delivery'){if(!e.authorized)reason='Unauthorized simulated meter';else if(!e.id||seen.has(e.id))reason='Missing or replayed delivery ID';else{seen.add(e.id);minted+=e.q;}}
  else if(e.kind==='redeem'){if(e.q>minted-burned)reason='Insufficient outstanding units';else burned+=e.q;}
  else reason='Unknown event';log.push({event:e,accepted:!reason,reason});}
 return {minted,burned,outstanding:minted-burned,log,note:'Simulated authorization and ledger accounting only. Does not prove physical delivery, backing, redemption solvency, or stable market price.'};
}
function sha256(message){
 // Portable SHA-256 for the teaching commitment when Web Crypto is unavailable.
 const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
 const input=new TextEncoder().encode(String(message));if(input.length>1000000)throw Error('Teaching hash input too large');
 const data=new Uint8Array(Math.ceil((input.length+9)/64)*64);data.set(input);data[input.length]=128;const view=new DataView(data.buffer);view.setUint32(data.length-4,input.length*8,false);
 const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],w=new Uint32Array(64),rot=(v,n)=>(v>>>n)|(v<<(32-n));
 for(let off=0;off<data.length;off+=64){for(let i=0;i<16;i++)w[i]=view.getUint32(off+4*i,false);for(let i=16;i<64;i++){let s0=rot(w[i-15],7)^rot(w[i-15],18)^(w[i-15]>>>3),s1=rot(w[i-2],17)^rot(w[i-2],19)^(w[i-2]>>>10);w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}
  let [a,b,c,d,e,f,g,z]=h;for(let i=0;i<64;i++){let s1=rot(e,6)^rot(e,11)^rot(e,25),ch=(e&f)^(~e&g),t1=(z+s1+ch+K[i]+w[i])>>>0,s0=rot(a,2)^rot(a,13)^rot(a,22),maj=(a&b)^(a&c)^(b&c),t2=(s0+maj)>>>0;z=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
  [a,b,c,d,e,f,g,z].forEach((v,i)=>h[i]=(h[i]+v)>>>0);
 }
 return h.map(x=>x.toString(16).padStart(8,'0')).join('');
}
const api={clear,utility,monteCarlo,profit,ledger,sha256};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.WorkshopEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);

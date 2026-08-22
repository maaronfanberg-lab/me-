import { DurableObject } from "cloudflare:workers";

const cors = {"content-type":"application/json; charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"};
const json=(x,s=200)=>new Response(JSON.stringify(x),{status:s,headers:cors});

export class SaraExperimentState extends DurableObject {
  async getSession(){ return (await this.ctx.storage.get("session")) || {schema:1,participant:{id:"sara",name:"Sara"},turns:[],updated_at:null}; }
  async replaceSession(session){
    if(!session || typeof session!=="object" || !Array.isArray(session.turns)) return {accepted:false,reason:"invalid-session"};
    const record={...session,updated_at:new Date().toISOString()};
    await this.ctx.storage.put("session",record);
    return {accepted:true,turns:record.turns.length,updated_at:record.updated_at};
  }
  async appendTurn(message){
    const text=String(message?.text||message?.content||"").trim();
    const speaker=String(message?.speaker||"").trim().toLowerCase();
    if(!speaker||!text) return {accepted:false,reason:"invalid-turn"};
    const session=await this.getSession();
    const sequence=session.turns.length+1;
    session.turns.push({sequence,message:{id:String(message.id||`live-${sequence}-${crypto.randomUUID()}`),speaker,display_name:String(message.display_name||speaker),text,timestamp:String(message.timestamp||new Date().toISOString())}});
    session.updated_at=new Date().toISOString();
    await this.ctx.storage.put("session",session);
    return {accepted:true,sequence,updated_at:session.updated_at};
  }
}

// Public clients may observe the experiment, never mutate it. Write transport is
// intentionally closed until it is wired through the repository's verified
// GitHub OIDC boundary. This prevents an Internet client from impersonating Sara
// or any Room voice while still allowing us to deploy and verify the live reader.
export async function handleSaraLive(request,env){
  const url=new URL(request.url);
  const stub=env.SARA_EXPERIMENT.getByName("main");
  if(request.method==="OPTIONS") return new Response(null,{status:204,headers:{"access-control-allow-origin":"*","access-control-allow-methods":"GET,OPTIONS","access-control-allow-headers":"content-type","access-control-max-age":"86400"}});
  if(url.pathname==="/api/sara/session"&&request.method==="GET") return json(await stub.getSession());
  if(url.pathname==="/api/sara/session"||url.pathname==="/api/sara/turn") return json({error:"write-boundary-closed"},405);
  return json({error:"not-found"},404);
}

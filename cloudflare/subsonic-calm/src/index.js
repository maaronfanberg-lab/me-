const APP_URL='https://maaronfanberg-lab.github.io/me-/apps/subsonic-calm.html?v=20260820calmv4';

function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'}})}

export default {
  async fetch(request){
    const url=new URL(request.url);
    if(request.method!=='GET'&&request.method!=='HEAD') return new Response('Method Not Allowed',{status:405,headers:{allow:'GET, HEAD'}});
    if(url.pathname==='/health') return json({ok:true,app:'subsonic-calm',version:'4',speaker:'Polk PSW10',profile:'low-salience-research',source:'github-pages',diagnostic_80hz:true});
    if(url.pathname==='/'||url.pathname==='/index.html') return Response.redirect(APP_URL,302);
    return new Response('Not Found',{status:404});
  }
};

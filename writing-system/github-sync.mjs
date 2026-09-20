// GitHub Contents API: existing text files only. Credentials stay in memory.
export function githubAdapter(config,{token='',fetchImpl=globalThis.fetch,timeoutMs=15000}={}) {
  const {repository,branch,prefix}=config;
  if(!/^[\w.-]+\/[\w.-]+$/.test(repository??'')||!branch||branch==='develop')throw Error('invalid repository or protected branch');
  const safe=p=>typeof p==='string'&&!/[\\:%?#\x00-\x1f]/.test(p)&&p.split('/').every(s=>s&&s!=='.'&&s!=='..');
  if(typeof prefix!=='string'||!prefix.endsWith('/')||!safe(prefix.slice(0,-1)))throw Error('dedicated prefix required');
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>60000)throw Error('invalid timeout');
  function targetPath(target){if(!safe(target)||!target.startsWith(prefix))throw Error('target outside configured prefix');return target.split('/').map(encodeURIComponent).join('/');}
  async function api(target,method,body){
    const encoded=targetPath(target);
    const headers={Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
    if(token)headers.Authorization='Bearer '+token;
    if(body)headers['Content-Type']='application/json';
    try {
      const response=await fetchImpl('https://api.github.com/repos/'+repository+'/contents/'+encoded+(method==='GET'?'?ref='+encodeURIComponent(branch):''),
        {method,headers,body:body?JSON.stringify(body):undefined,redirect:'error',signal:AbortSignal.timeout(timeoutMs)});
      if(!response.ok)throw Error('GitHub HTTP '+response.status);
      return await response.json();
    }catch(e){
      // Do not expose request headers or provider response bodies in journals/errors.
      if(/^GitHub HTTP \d+$/.test(e?.message))throw e;
      throw Error('GitHub transport failed or timed out');
    }
  }
  return {destination:'github',destination_config:structuredClone(config),conditional_update:true,idempotent_create:false,
    async read(target){
      const data=await api(target,'GET');
      if(data.type!=='file'||data.encoding!=='base64'||typeof data.content!=='string'||!/^([a-f0-9]{40}|[a-f0-9]{64})$/.test(data.sha??''))throw Error('unsupported GitHub content');
      return {content:new TextDecoder('utf-8',{fatal:true}).decode(Buffer.from(data.content,'base64')),version:data.sha};
    },
    async write({target,expected_version,content,operation_id}){
      if(!token)throw Error('GitHub credential required');
      if(typeof content!=='string'||!/^([a-f0-9]{40}|[a-f0-9]{64})$/.test(expected_version??'')||!target)throw Error('existing target and blob version required');
      if(!/^[a-f0-9-]{36}$/.test(operation_id??''))throw Error('invalid operation id');
      await api(target,'PUT',{message:'Writing system sync '+operation_id,content:Buffer.from(content,'utf8').toString('base64'),sha:expected_version,branch});
      return {target};
    }
  };
}

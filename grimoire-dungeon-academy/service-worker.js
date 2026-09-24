/* Build replaces the cache version and complete asset list. */
const CACHE='gda-__VERSION__';
const ASSETS=__PRECACHE__;
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{for(const name of await caches.keys())if(name.startsWith('gda-')&&name!==CACHE)await caches.delete(name);await self.clients.claim();})());});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
 event.respondWith((async()=>{const cache=await caches.open(CACHE);const cached=await cache.match(event.request,{ignoreSearch:event.request.mode==='navigate'});if(cached)return cached;
 try{return await fetch(event.request);}catch(error){if(event.request.mode==='navigate')return await cache.match('./index.html');throw error;}})());
});

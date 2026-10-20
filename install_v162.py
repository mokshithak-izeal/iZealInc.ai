from pathlib import Path
import re

project = Path.cwd()
index = project / 'templates' / 'index.html'
if not index.exists():
    raise SystemExit(f'ERROR: {index} not found. Run from the JobAgent project root.')

s = index.read_text(encoding='utf-8')
# Remove all previous v16 addon references. v1.6.2 uses a direct inline UI patch so cache/path issues cannot hide it.
s = re.sub(r'\s*<script[^>]+v16_addon\.js[^>]*></script>\s*', '\n', s, flags=re.I)

patch = r'''
<!-- JOBAGENT_V162_UI_PATCH -->
<script>
(function(){
  async function api(url, options){
    const r=await fetch(url, options); let d={}; try{d=await r.json()}catch(e){}
    if(!r.ok) throw new Error(d.detail || (r.status+' '+r.statusText)); return d;
  }
  function findPage(kind){
    return document.getElementById(kind) || document.getElementById(kind+'Page') || document.getElementById(kind+'-page') || document.querySelector('.page[data-page="'+kind+'"]') || document.querySelector('[data-section-content="'+kind+'"]');
  }
  function candidatePage(){
    let p=findPage('candidate'); if(p) return p;
    const h=[...document.querySelectorAll('h1')].find(x=>x.textContent.trim()==='Candidate Profile');
    return h ? (h.closest('.page') || h.parentElement.parentElement || h.parentElement) : null;
  }
  async function injectPreferences(){
    if(document.getElementById('v162Preferences')) return;
    const page=candidatePage(); if(!page) { console.error('v1.6.2: Candidate page not found'); return; }
    const panel=document.createElement('div'); panel.id='v162Preferences'; panel.className='panel'; panel.style.marginTop='20px';
    panel.innerHTML='<h2>Job Preferences</h2><p>Saved locally and used for job matching.</p><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px"><label><strong>Preferred Role</strong><input id="preferredRole" type="text" placeholder="Python Backend Developer" style="width:100%;margin-top:6px"></label><label><strong>Preferred Location</strong><input id="preferredLocation" type="text" placeholder="Bengaluru" style="width:100%;margin-top:6px"></label><label><strong>Minimum Match (%)</strong><input id="minimumMatch" type="number" min="0" max="100" value="80" style="width:100%;margin-top:6px"></label></div><p id="v162PrefStatus" class="status"></p>';
    page.appendChild(panel);
    try{
      const p=await api('/api/preferences');
      preferredRole.value=p.preferred_role||''; preferredLocation.value=Array.isArray(p.preferred_locations)?(p.preferred_locations[0]||''):''; minimumMatch.value=p.minimum_match==null?80:p.minimum_match;
    }catch(e){v162PrefStatus.textContent='Preferences API error: '+e.message;}
    async function save(){
      try{await api('/api/preferences',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({preferred_role:preferredRole.value||'',preferred_locations:(preferredLocation.value||'').split(',').map(x=>x.trim()).filter(Boolean),work_modes:[],minimum_match:Number(minimumMatch.value||80),excluded_companies:[]})});v162PrefStatus.textContent='Preferences saved.';}catch(e){v162PrefStatus.textContent='Save failed: '+e.message;}
    }
    [preferredRole,preferredLocation,minimumMatch].forEach(x=>x.addEventListener('change',save));
  }
  async function dashboard(){
    try{const d=await api('/api/jobs/dashboard'); const page=findPage('dashboard'); if(!page)return; let box=document.getElementById('v162Dash'); if(!box){box=document.createElement('div');box.id='v162Dash';box.className='panel';box.style.marginTop='18px';page.appendChild(box);} box.innerHTML='<h2>Job Pipeline</h2><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px"><div><strong>Analyzed</strong><br>'+d.jobs_analyzed+'</div><div><strong>Review</strong><br>'+d.review+'</div><div><strong>Applied</strong><br>'+d.applied+'</div><div><strong>Interviews</strong><br>'+d.interviews+'</div><div><strong>Offers</strong><br>'+d.offers+'</div><div><strong>Avg Match</strong><br>'+(d.average_score==null?'N/A':d.average_score+'%')+'</div></div>';}catch(e){console.error(e)}
  }
  async function queue(){
    const page=findPage('matches'); if(!page)return; let box=document.getElementById('v162Queue'); if(!box){box=document.createElement('div');box.id='v162Queue';box.className='panel';box.style.marginTop='18px';page.appendChild(box);} try{const rows=await api('/api/jobs/queue');box.innerHTML='<h2>Saved Job Review Queue</h2>'+(rows.length?rows.map(j=>'<div style="border-top:1px solid #ddd;padding:12px 0"><strong>'+String(j.title||'Job')+'</strong> <span style="float:right">'+(j.score==null?'N/A':j.score+'%')+'</span><br>'+String(j.company||'Company not specified')+' | <strong>'+String(j.status||'NEW')+'</strong></div>').join(''):'<p>No saved jobs yet.</p>');}catch(e){box.innerHTML='<h2>Saved Job Review Queue</h2><p>Queue API error: '+e.message+'</p>';}
  }
  function init(){ console.log('JOBAGENT v1.6.2 UI PATCH LOADED'); injectPreferences(); dashboard(); queue(); document.querySelectorAll('.nav-item').forEach(n=>n.addEventListener('click',()=>setTimeout(()=>{injectPreferences();dashboard();queue()},0))); }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
</script>
'''

pos = s.lower().rfind('</body>')
if pos == -1:
    s += patch
else:
    s = s[:pos] + patch + '\n' + s[pos:]
index.write_text(s, encoding='utf-8')
print('SUCCESS: v1.6.2 inline UI patch inserted into:', index)
print('VERIFY: Select-String -Path .\\templates\\index.html -Pattern JOBAGENT_V162_UI_PATCH')

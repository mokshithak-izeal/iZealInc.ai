let candidateProfile = null;
let lastMatch = null;

const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');

function showPage(name) {
  pages.forEach(p => p.classList.remove('active'));
  navItems.forEach(i => i.classList.remove('active'));
  const page = document.getElementById(name);
  const nav = document.querySelector(`[data-section="${name}"]`);
  if (page) page.classList.add('active');
  if (nav) nav.classList.add('active');
  if (name === 'applications') loadApplications();
  if (name === 'matches' && candidateProfile) loadJobQueue();
}
navItems.forEach(i => i.addEventListener('click', () => showPage(i.dataset.section)));
function openCandidatePage(){ showPage('candidate'); }
window.openCandidatePage = openCandidatePage;

function arr(v){ return Array.isArray(v) ? v : []; }
function obj(v){ return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }
function text(v, fallback='Not specified'){ return v === undefined || v === null || v === '' ? fallback : String(v); }

function renderSkills(skills){
  const box=document.getElementById('skillList'); if(!box) return;
  box.innerHTML='';
  arr(skills).forEach(skill=>{
    const data = typeof skill === 'string' ? {name:skill} : obj(skill);
    const span=document.createElement('span');
    span.textContent=text(data.name,'Unknown');
    if(data.evidence) span.title=`Confidence: ${Math.round(Number(data.confidence||0)*100)}% | ${data.evidence}`;
    span.style.cssText='background:#dbeafe;color:#1e40af;padding:7px 10px;border-radius:999px;font-size:13px;font-weight:600';
    box.appendChild(span);
  });
}

const analyzeButton=document.getElementById('analyzeButton');
if(analyzeButton){
  analyzeButton.addEventListener('click',async()=>{
    const input=document.getElementById('resumeInput'), pastedText=document.getElementById('resumeText')?.value.trim(), status=document.getElementById('resumeStatus');
    const hasFile=Boolean(input?.files.length), hasText=Boolean(pastedText);
    if(hasFile===hasText){ if(status)status.textContent=hasFile?'Choose a file or paste text, not both.':'Choose a PDF or DOCX file, or paste resume text.'; return; }
    analyzeButton.disabled=true; analyzeButton.textContent='Analyzing with Gemini...';
    try{
      const fd=new FormData();
      if(hasFile) fd.append('file',input.files[0]);
      else fd.append('text',pastedText);
      const r=await fetch(hasFile?'/api/resumes/analyze':'/api/resumes/analyze-text',{method:'POST',body:fd});
      const d=await r.json(); if(!r.ok) throw new Error(d.detail||'Resume analysis failed.');
      candidateProfile=d;
      document.getElementById('candidateName').value=text(d.candidate_name,'');
      document.getElementById('candidateExperience').value=text(d.experience,'');
      renderSkills(d.technical_skills);
      document.getElementById('candidateProfile').classList.remove('hidden');
      document.getElementById('candidateCount').textContent='1';
      if(status) status.textContent=`AI analyzed ${text(d.file_name,'resume')}. Found ${arr(d.technical_skills).length} contextual technical skills.`;
      setupJobMatcher();
    }catch(e){ if(status)status.textContent=`Error: ${e.message}`; }
    finally{ analyzeButton.disabled=false; analyzeButton.textContent='Analyze Resume'; }
  });
}

function setupJobMatcher(){
  const page=document.getElementById('matches'); if(!page)return;
  page.innerHTML=`<div class="page-header"><div><h1>LinkedIn Job Matcher</h1><p>Paste a LinkedIn job URL and the complete job description.</p></div></div>
  <div class="panel"><label>LinkedIn Job URL<input id="jobUrl" type="url" placeholder="https://www.linkedin.com/jobs/view/..."></label><br>
  <label>Job Description<textarea id="jobDescription" rows="14" style="width:100%;margin-top:8px;padding:12px;border:1px solid #d1d5db;border-radius:8px"></textarea></label><br>
  <button id="matchJobButton" class="primary-button">Analyze & Match Job</button><p id="jobStatus" class="status"></p></div>
  <div id="parsedJob" class="panel hidden"></div><div id="matchResult" class="panel hidden"></div>`;
  document.getElementById('matchJobButton').addEventListener('click',matchJob);
}

function badge(s,color){ return `<span style="display:inline-block;background:${color};padding:5px 9px;border-radius:12px;margin:3px">${text(s,'Unknown')}</span>`; }
function badges(values,color='#eef2ff'){
  const a=arr(values); if(!a.length)return '<span class="muted">None</span>';
  let html=''; for(const value of a) html += badge(value,color); return html;
}
function bullets(values){
  const a=arr(values); if(!a.length)return '<span class="muted">None</span>';
  let html='<ul>'; for(const value of a) html += `<li>${text(value,'')}</li>`; return html+'</ul>';
}
function breakdown(value){
  const o=obj(value), keys=Object.keys(o); if(!keys.length)return 'Not available';
  let html=''; for(let i=0;i<keys.length;i++){ if(i)html+=' | '; html += `${keys[i]}: ${o[keys[i]]}`; } return html;
}
function skillTable(values){
  const a=arr(values); if(!a.length)return '<span class="muted">None</span>';
  let html='';
  for(const raw of a){
    const x=obj(raw), state=text(x.status,'missing');
    const color=state==='exact'?'#dcfce7':state==='related'?'#fef3c7':'#fee2e2';
    const label=state==='exact'?'MATCH':state==='related'?`RELATED (${text(x.matched_with,'related skill')})`:'MISSING';
    html += `<div style="padding:7px 9px;margin:5px 0;background:${color};border-radius:7px"><strong>${text(x.job_skill,'Unknown skill')}</strong> - ${label}</div>`;
  }
  return html;
}

async function matchJob(){
  const status=document.getElementById('jobStatus');
  try{
    if(!candidateProfile) throw new Error('Analyze a resume first.');
    const description=(document.getElementById('jobDescription')?.value||'').trim();
    if(!description) throw new Error('Paste the complete job description first.');
    if(status) status.textContent='Gemini is parsing the job and the matcher is scoring normalized skills...';
    const payload={job_description:description,candidate_profile:candidateProfile,preferred_location:document.getElementById('preferredLocation')?.value||'',threshold:Number(document.getElementById('minimumMatch')?.value||80),job_url:document.getElementById('jobUrl')?.value||''};
    const r=await fetch('/api/jobs/analyze-match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json(); if(!r.ok) throw new Error(d.detail||`Request failed (${r.status})`);
    console.log('Job match API response:',d);
    lastMatch=d; renderJob(obj(d.job),obj(d.match)); loadJobQueue();
    if(status) status.textContent='Job analysis and matching completed.';
  }catch(e){ console.error('Job matching UI error:',e); if(status) status.textContent=`Error: ${e.message}`; }
}

function renderJob(j,m){
  const parsed=document.getElementById('parsedJob'), result=document.getElementById('matchResult'); if(!parsed||!result)return;
  parsed.classList.remove('hidden');
  parsed.innerHTML=`<h2>Parsed LinkedIn Job</h2><p><strong>Title:</strong> ${text(j.title)}</p><p><strong>Company:</strong> ${text(j.company)}</p><p><strong>Location:</strong> ${text(j.location)} ${j.work_mode?' | '+j.work_mode:''}</p><p><strong>Experience:</strong> ${text(j.minimum_experience_years)}${j.maximum_experience_years!==undefined&&j.maximum_experience_years!==null?' - '+j.maximum_experience_years:''} years</p><p><strong>Required skills:</strong><br>${badges(j.required_skills,'#dcfce7')}</p><p><strong>Preferred skills:</strong><br>${badges(j.preferred_skills,'#fef3c7')}</p><p><strong>Responsibilities:</strong>${bullets(j.responsibilities)}</p>`;
  result.classList.remove('hidden');
  if(m.score===undefined || m.score===null){ result.innerHTML=`<h2>Match not calculated</h2><p><strong>Decision:</strong> ${text(m.decision,'INSUFFICIENT_JOB_DATA')}</p><p>${text(m.reason,'Not enough comparable data.')}</p>`; return; }
  result.innerHTML=`<h2>Match Analysis</h2><h1>${m.score}%</h1><p><strong>Decision:</strong> ${text(m.decision)}</p><h3>Required skills</h3>${skillTable(m.required_skill_matches)}<h3>Preferred skills</h3>${skillTable(m.preferred_skill_matches)}<p><strong>Experience:</strong> ${m.experience_pass===null||m.experience_pass===undefined?'Not specified':m.experience_pass?'PASS':'FAIL'}</p><p><strong>Score breakdown:</strong> ${breakdown(m.score_breakdown)}</p><p><strong>Effective weights:</strong> ${breakdown(m.weights_used)}</p><p><small>Green = canonical/exact. Yellow = related evidence with partial credit. Red = missing.</small></p>${j.job_url?`<button id="openLinkedInButton" class="secondary-button">Open on LinkedIn</button> `:''}<button id="markAppliedButton" class="primary-button">Mark as Applied</button>`;
  const open=document.getElementById('openLinkedInButton'); if(open)open.onclick=()=>window.open(j.job_url,'_blank','noopener');
  const applied=document.getElementById('markAppliedButton'); if(applied)applied.onclick=markApplied;
}

async function markApplied(){
  if(!lastMatch)return; const j=obj(lastMatch.job),m=obj(lastMatch.match);
  try{const r=await fetch('/api/jobs/mark-applied',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:text(j.title,''),company:text(j.company,''),job_url:text(j.job_url,''),score:m.score??null,status:'APPLIED'})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not save application.');alert('Application saved to history.');loadApplications();}catch(e){alert(e.message)}
}
async function loadApplications(){
  const page=document.getElementById('applications'); if(!page)return;
  try{const r=await fetch('/api/jobs/applications'),data=await r.json(),rows=arr(data);document.getElementById('applicationCount').textContent=String(rows.length);let html='<div class="page-header"><div><h1>Applications</h1><p>Jobs you manually marked as applied.</p></div></div><div class="panel">';if(!rows.length)html+='<div class="empty-state"><h3>No applications yet</h3></div>';for(const raw of rows){const x=obj(raw);html+=`<div style="padding:14px 0;border-bottom:1px solid #e5e7eb"><strong>${text(x.title,'Job')}</strong>${x.company?' - '+x.company:''}<br>Match: ${x.score==null?'Not calculated':x.score+'%'} | Status: ${text(x.status,'APPLIED')}<br><small>${text(x.applied_at,'')}</small></div>`;}page.innerHTML=html+'</div>';}catch(e){console.error(e)}
}

async function loadJobQueue(){
  const page=document.getElementById('matches'); if(!page)return;
  let queue=document.getElementById('jobQueue');
  if(!queue){queue=document.createElement('div');queue.id='jobQueue';queue.className='panel';page.appendChild(queue);}
  try{
    const r=await fetch('/api/jobs/queue'), data=await r.json(), jobs=arr(data);
    let html='<h2>Saved Job Review Queue</h2><p>Every analyzed job is saved here. Use the status buttons to triage the queue.</p>';
    if(!jobs.length){queue.innerHTML=html+'<p class="muted">No analyzed jobs saved yet.</p>';return;}
    for(const raw of jobs){const j=obj(raw); const score=j.score==null?'Not calculated':j.score+'%';
      html+=`<div style="border-top:1px solid #e5e7eb;padding:16px 0"><h3 style="margin:0">${text(j.title,'Job')}</h3><p>${text(j.company,'Company not specified')} | ${text(j.location,'Location not specified')}</p><p><strong>${score}</strong> | ${text(j.decision,'')} | Status: <strong>${text(j.status,'NEW')}</strong></p><p>Missing required: ${arr(j.required_skill_matches).filter(x=>obj(x).status==='missing').map(x=>text(obj(x).job_skill,'')).filter(Boolean).slice(0,8).join(', ')||'None'}</p>${j.job_url?`<button class="secondary-button" onclick="window.open('${String(j.job_url).replace(/'/g,'')}','_blank','noopener')">Open LinkedIn</button> `:''}<button class="secondary-button" onclick="setJobStatus('${j.id}','REVIEW')">Review</button> <button class="secondary-button" onclick="setJobStatus('${j.id}','SKIPPED')">Skip</button> <button class="primary-button" onclick="setJobStatus('${j.id}','APPLIED')">Applied</button></div>`;
    }
    queue.innerHTML=html;
  }catch(e){queue.innerHTML=`<h2>Saved Job Review Queue</h2><p>Error loading queue: ${e.message}</p>`;}
}
async function setJobStatus(id,status){
  try{const r=await fetch(`/api/jobs/queue/${id}/status`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not update status.');loadJobQueue();}catch(e){alert(e.message)}
}
window.setJobStatus=setJobStatus;

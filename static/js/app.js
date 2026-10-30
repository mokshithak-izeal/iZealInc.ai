const _fetch = window.fetch;
window.fetch = async (...args) => {
  const r = await _fetch(...args);
  if (r.status === 401) location = '/login';
  return r;
};

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
  if (name === 'matches') {
    loadPairOptions();
    loadJobQueue();
  }
}
navItems.forEach(i => i.addEventListener('click', () => showPage(i.dataset.section)));
function openCandidatePage(){ showPage('candidate'); }
window.openCandidatePage = openCandidatePage;

function arr(v){ return Array.isArray(v) ? v : []; }
function obj(v){ return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }
function text(v, fallback='Not specified'){ return v === undefined || v === null || v === '' ? fallback : String(v); }

function addCandidatePreview(data, source){
  const panel=document.getElementById('candidateProfile');
  const previews=document.getElementById('candidatePreviews');
  if(!panel||!previews)return;
  panel.classList.remove('hidden');
  const card=document.createElement('article');
  card.className='candidate-card';
  const heading=document.createElement('h3');
  heading.textContent=text(data.candidate_name,'Unknown candidate');
  const summary=document.createElement('p');
  summary.textContent=`${text(data.current_role,'Role not specified')} | ${text(data.experience,'Experience not specified')} | ${text(data.file_name,'Resume')}`;
  const skills=document.createElement('p');
  skills.textContent=`Skills: ${arr(data.skills).join(', ')||'None identified'}`;
  card.append(heading,summary,skills);
  if(data.duplicate){
    const note=document.createElement('p');
    note.className='status';
    note.textContent='This resume already exists in candidates.';
    card.append(note);
  }else{
    const button=document.createElement('button');
    button.type='button';
    button.className='primary-button';
    button.textContent='Save Candidate';
    const status=document.createElement('p');
    status.className='status';
    status.setAttribute('aria-live','polite');
    button.addEventListener('click',()=>saveCandidate(button,status,data,source));
    card.append(button,status);
  }
  previews.prepend(card);
}

async function saveCandidate(button,status,data,source){
  button.disabled=true;
  status.textContent='Saving candidate...';
  const form=new FormData();
  form.append('profile',JSON.stringify(data));
  if(source.file)form.append('file',source.file);
  else form.append('text',source.text);
  try{
    const response=await fetch('/api/resumes/save',{method:'POST',body:form});
    const result=await response.json();
    if(!response.ok)throw new Error(result.detail||'Could not save candidate.');
    status.textContent=result.duplicate
      ?'This candidate already exists; no duplicate was saved.'
      :'Candidate saved successfully.';
    button.textContent=result.duplicate?'Already Saved':'Saved';
    button.disabled=true;
    try{await refreshCandidateCount();}
    catch(error){console.error('Candidate saved, but count could not be refreshed:',error);}
    await loadPairOptions();
  }catch(error){
    status.textContent=`Save failed: ${error.message}`;
    button.disabled=false;
  }
}

async function refreshCandidateCount(){
  const count=document.getElementById('candidateCount');
  if(!count)return;
  const response=await fetch('/api/resumes');
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'Could not refresh candidate count.');
  count.textContent=String(arr(data).length);
}

const analyzeButton=document.getElementById('analyzeButton');
if(analyzeButton){
  analyzeButton.addEventListener('click',async()=>{
    const input=document.getElementById('resumeInput'), files=Array.from(input?.files||[]), pastedText=document.getElementById('resumeText')?.value.trim(), status=document.getElementById('resumeStatus');
    if(files.length&&pastedText){ if(status)status.textContent='Choose files or paste text, not both.'; return; }
    if(!files.length&&!pastedText){ if(status)status.textContent='Select one or more resumes, or paste resume text.'; return; }
    analyzeButton.disabled=true;
    let analyzed=0, duplicates=0, failures=[];
    try{
      const items=files.length?files:[null];
      for(let index=0;index<items.length;index++){
        const file=items[index], fd=new FormData();
        if(file) fd.append('file',file); else fd.append('text',pastedText);
        if(status)status.textContent=`Analyzing resume ${index+1} of ${items.length}${file?`: ${file.name}`:''}...`;
        try{
          const r=await fetch(file?'/api/resumes/analyze':'/api/resumes/analyze-text',{method:'POST',body:fd});
          const d=await r.json(); if(!r.ok) throw new Error(d.detail||'Resume analysis failed.');
          if(d.duplicate)duplicates++;else analyzed++;
          addCandidatePreview(d,{file,text:pastedText});
          if(status)status.textContent=d.duplicate
            ?`Already exists: ${d.candidate_name||file?.name||'This candidate'}; skipped duplicate.`
            :`Analyzed ${analyzed} of ${items.length} resume(s). Save it from the profile preview when ready.`;
        }catch(error){ failures.push(`${file?.name||'Pasted resume'}: ${error.message}`); }
      }
      if(status)status.textContent=`Analyzed ${analyzed} new resume(s); found ${duplicates} existing candidate(s). Save each new profile from the candidate preview.${failures.length?` Failed: ${failures.join(' | ')}`:''}`;
    }finally{ analyzeButton.disabled=false; }
  });
}

let pairCandidates=[];
let pairDescriptions=[];

function setupJobMatcher(){
  const target=document.getElementById('pairMatcher'); if(!target)return;
  target.innerHTML=`<div class="panel"><h2>Select a candidate and a job description</h2><div class="form-grid"><label>Candidate<select id="candidateSelect"></select></label><label>Job description<select id="descriptionSelect"></select></label></div><div class="form-grid"><div id="candidateSummary" class="muted summary-box"></div><div id="descriptionSummary" class="muted summary-box description-preview"></div></div><label>Preferred location<input id="matchPreferredLocation" type="text" placeholder="Optional"></label><div class="form-actions"><button id="matchJobButton" class="primary-button">Match selected pair</button></div><p id="jobStatus" class="status" aria-live="polite"></p></div><div id="pairResultSummary" class="panel hidden"></div><div id="parsedJob" class="panel hidden"></div><div id="matchResult" class="panel hidden"></div>`;
  document.getElementById('matchJobButton').addEventListener('click',matchJob);
  document.getElementById('candidateSelect').addEventListener('change',renderPairSummaries);
  document.getElementById('descriptionSelect').addEventListener('change',renderPairSummaries);
}

async function loadPairOptions(){
  if(!document.getElementById('candidateSelect'))return;
  const candidateSelect=document.getElementById('candidateSelect'), descriptionSelect=document.getElementById('descriptionSelect');
  const oldCandidate=candidateSelect.value, oldDescription=descriptionSelect.value;
  try{
    const [candidateResponse,descriptionResponse]=await Promise.all([fetch('/api/resumes'),fetch('/api/jobs/descriptions')]);
    const [candidates,descriptions]=await Promise.all([candidateResponse.json(),descriptionResponse.json()]);
    if(!candidateResponse.ok)throw new Error(candidates.detail||'Could not load candidates.');
    if(!descriptionResponse.ok)throw new Error(descriptions.detail||'Could not load job descriptions.');
    pairCandidates=arr(candidates); pairDescriptions=arr(descriptions);
    candidateSelect.replaceChildren(new Option('Select a candidate',''));
    pairCandidates.forEach(candidate=>{
      const years=candidate.experience==null?'Experience not specified':`${candidate.experience} years`;
      const option=new Option(`${candidate.name} — ${candidate.file} — ${years}`,candidate.id);
      candidateSelect.add(option);
    });
    descriptionSelect.replaceChildren(new Option('Select a job description',''));
    pairDescriptions.forEach(description=>{
      const exp=description.experience||'Experience not specified';
      descriptionSelect.add(new Option(`${description.title} — ${exp}`,description.id));
    });
    if(pairCandidates.some(x=>x.id===oldCandidate))candidateSelect.value=oldCandidate;
    if(pairDescriptions.some(x=>x.id===oldDescription))descriptionSelect.value=oldDescription;
    const count=document.getElementById('candidateCount'); if(count)count.textContent=String(pairCandidates.length);
    const jobsCount=document.getElementById('jobCount'); if(jobsCount)jobsCount.textContent=String(pairDescriptions.length);
    renderPairSummaries();
    renderSavedDescriptions();
  }catch(error){
    const status=document.getElementById('jobStatus');
    if(status)status.textContent=`Could not load candidate/job choices: ${error.message}`;
  }
}

function renderPairSummaries(){
  const candidate=pairCandidates.find(x=>x.id===document.getElementById('candidateSelect')?.value);
  const description=pairDescriptions.find(x=>x.id===document.getElementById('descriptionSelect')?.value);
  const candidateBox=document.getElementById('candidateSummary');
  const descriptionBox=document.getElementById('descriptionSummary');
  if(candidateBox)candidateBox.textContent=candidate?`${candidate.name} | ${candidate.current_role||'Role not specified'} | ${candidate.experience==null?'Experience not specified':candidate.experience+' years'} | ${candidate.file}`:'Select a saved candidate to see their profile.';
  if(descriptionBox)descriptionBox.textContent=description?`${description.title} | Experience: ${description.experience||'Not specified'} | ${description.file||'Manually entered'}\n\n${description.description}`:'Select a saved job description to review it.';
}

function renderSavedDescriptions(){
  const list=document.getElementById('savedDescriptionList'); if(!list)return;
  list.replaceChildren();
  if(!pairDescriptions.length){list.textContent='No descriptions saved yet.';return;}
  pairDescriptions.forEach(description=>{
    const card=document.createElement('article');
    card.className='description-card';
    const title=document.createElement('strong');title.textContent=description.title;
    const meta=document.createElement('p');meta.className='muted';meta.textContent=`Experience: ${description.experience||'Not specified'} | ${description.file||'Manually entered'}`;
    const body=document.createElement('details');
    const summary=document.createElement('summary');summary.textContent='View job description';
    const content=document.createElement('p');content.style.whiteSpace='pre-wrap';content.textContent=description.description;
    body.append(summary,content);card.append(title,meta,body);list.appendChild(card);
  });
}

async function setupDescriptionControls(){
  const uploadButton=document.getElementById('uploadDescriptionsButton');
  const saveButton=document.getElementById('saveDescriptionButton');
  const status=document.getElementById('descriptionStatus');
  if(!uploadButton||!saveButton)return;
  uploadButton.addEventListener('click',async()=>{
    const files=Array.from(document.getElementById('jobDescriptionFiles').files||[]);
    if(!files.length){status.textContent='Select one or more TXT, PDF, or DOCX files.';return;}
    const form=new FormData();files.forEach(file=>form.append('files',file));
    uploadButton.disabled=true;status.textContent=`Uploading ${files.length} job description(s)...`;
    try{
      const response=await fetch('/api/jobs/descriptions/upload',{method:'POST',body:form}),data=await response.json();
      if(!response.ok)throw new Error(data.detail||'Description upload failed.');
      const items=arr(data.items),succeeded=items.filter(item=>item.ok&&!item.duplicate).length;
      const duplicates=items.filter(item=>item.ok&&item.duplicate).length;
      const failures=items.filter(item=>!item.ok).map(item=>`${item.file}: ${item.error}`);
      status.textContent=`Saved ${succeeded} new description(s); skipped ${duplicates} duplicate(s).${failures.length?' Failed: '+failures.join(' | '):''}`;
      document.getElementById('jobDescriptionFiles').value='';
      await loadPairOptions();
    }catch(error){status.textContent=`Upload failed: ${error.message}`;}
    finally{uploadButton.disabled=false;}
  });
  saveButton.addEventListener('click',async()=>{
    saveButton.disabled=true;
    try{
      const response=await fetch('/api/jobs/descriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        title:document.getElementById('newJobTitle').value,
        experience:document.getElementById('newJobExperience').value,
        description:document.getElementById('newJobDescription').value
      })});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'Could not save description.');
      status.textContent=data.duplicate?`That job description already exists as "${data.title}".`:`Saved "${data.title}".`;
      if(data.duplicate){await loadPairOptions();return;}
      document.getElementById('newJobTitle').value='';
      document.getElementById('newJobExperience').value='';
      document.getElementById('newJobDescription').value='';
      await loadPairOptions();
    }catch(error){status.textContent=`Save failed: ${error.message}`;}
    finally{saveButton.disabled=false;}
  });
}

function badge(s, colorClass){
  return `<span class="badge badge-${colorClass}">${text(s,'Unknown')}</span>`;
}
function badges(values, colorClass='blue'){
  const a=arr(values); if(!a.length)return '<span class="muted">None</span>';
  let html=''; for(const value of a) html += badge(value,colorClass); return html;
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
  let html='<div class="skill-list">';
  for(const raw of a){
    const x=obj(raw), state=text(x.status,'missing');
    const label=state==='exact'?'MATCH':state==='related'?`RELATED (${text(x.matched_with,'related skill')})`:'MISSING';
    html += `<div class="skill-item skill-${state}"><strong>${text(x.job_skill,'Unknown skill')}</strong> — ${label}</div>`;
  }
  return html + '</div>';
}

async function matchJob(){
  const status=document.getElementById('jobStatus');
  try{
    const candidateId=document.getElementById('candidateSelect')?.value;
    const descriptionId=document.getElementById('descriptionSelect')?.value;
    if(!candidateId)throw new Error('Select a candidate first.');
    if(!descriptionId)throw new Error('Select a job description first.');
    const candidate=pairCandidates.find(x=>x.id===candidateId);
    const description=pairDescriptions.find(x=>x.id===descriptionId);
    if(status) status.textContent='Gemini is parsing the job and the matcher is scoring normalized skills...';
    const r=await fetch('/api/jobs/match-saved',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      candidate_id:candidateId,job_description_id:descriptionId,
      preferred_location:document.getElementById('matchPreferredLocation').value,
      threshold:Number(document.getElementById('minimumMatch')?.value||80)
    })});
    const d=await r.json(); if(!r.ok) throw new Error(d.detail||`Request failed (${r.status})`);
    console.log('Job match API response:',d);
    lastMatch=d;
    const summary=document.getElementById('pairResultSummary');
    summary.classList.remove('hidden');
    summary.textContent=`Matching ${d.candidate.name} (${d.candidate.experience==null?'experience not specified':d.candidate.experience+' years'}) with ${d.selected_job_description.title} (required experience: ${d.selected_job_description.experience||'not specified'}).`;
    renderJob(obj(d.job),obj(d.match)); loadJobQueue();
    if(status) status.textContent='Job analysis and matching completed.';
  }catch(e){ console.error('Job matching UI error:',e); if(status) status.textContent=`Error: ${e.message}`; }
}

function renderJob(j,m){
  const parsed=document.getElementById('parsedJob'), result=document.getElementById('matchResult'); if(!parsed||!result)return;
  parsed.classList.remove('hidden');
  parsed.innerHTML=`<h2>Parsed LinkedIn Job</h2><p><strong>Title:</strong> ${text(j.title)}</p><p><strong>Company:</strong> ${text(j.company)}</p><p><strong>Location:</strong> ${text(j.location)} ${j.work_mode?' | '+j.work_mode:''}</p><p><strong>Experience:</strong> ${text(j.minimum_experience_years)}${j.maximum_experience_years!==undefined&&j.maximum_experience_years!==null?' - '+j.maximum_experience_years:''} years</p><p><strong>Required skills:</strong></p><div class="badge-list">${badges(j.required_skills,'green')}</div><p><strong>Preferred skills:</strong></p><div class="badge-list">${badges(j.preferred_skills,'amber')}</div><p><strong>Responsibilities:</strong>${bullets(j.responsibilities)}</p>`;
  result.classList.remove('hidden');
  if(m.score===undefined || m.score===null){ result.innerHTML=`<h2>Match not calculated</h2><p><strong>Decision:</strong> ${text(m.decision,'INSUFFICIENT_JOB_DATA')}</p><p>${text(m.reason,'Not enough comparable data.')}</p>`; return; }
  result.innerHTML=`<h2>Match Analysis</h2><div class="score-display">${m.score}%</div><p><strong>Decision:</strong> ${text(m.decision)}</p><h3>Required skills</h3>${skillTable(m.required_skill_matches)}<h3>Preferred skills</h3>${skillTable(m.preferred_skill_matches)}<p><strong>Experience:</strong> ${m.experience_pass===null||m.experience_pass===undefined?'Not specified':m.experience_pass?'PASS':'FAIL'}</p><p><strong>Score breakdown:</strong> ${breakdown(m.score_breakdown)}</p><p><strong>Effective weights:</strong> ${breakdown(m.weights_used)}</p><p><small>Green = canonical/exact. Yellow = related evidence with partial credit. Red = missing.</small></p><div class="form-actions">${j.job_url?`<button id="openLinkedInButton" class="secondary-button">Open on LinkedIn</button>`:''}<button id="markAppliedButton" class="primary-button">Mark as Applied</button></div>`;
  const open=document.getElementById('openLinkedInButton'); if(open)open.onclick=()=>window.open(j.job_url,'_blank','noopener');
  const applied=document.getElementById('markAppliedButton'); if(applied)applied.onclick=markApplied;
}

async function markApplied(){
  if(!lastMatch)return; const j=obj(lastMatch.job),m=obj(lastMatch.match);
  try{const r=await fetch('/api/jobs/mark-applied',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:text(j.title,''),company:text(j.company,''),job_url:text(j.job_url,''),score:m.score??null,status:'APPLIED'})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not save application.');alert('Application saved to history.');loadApplications();}catch(e){alert(e.message)}
}
async function loadApplications(){
  const page=document.getElementById('applications'); if(!page)return;
  try{const r=await fetch('/api/jobs/applications'),data=await r.json(),rows=arr(data);document.getElementById('applicationCount').textContent=String(rows.length);let html='<div class="page-header"><div><h1>Applications</h1><p>Jobs you manually marked as applied.</p></div></div><div class="panel">';if(!rows.length)html+='<div class="empty-state"><h3>No applications yet</h3></div>';for(const raw of rows){const x=obj(raw);html+=`<div class="application-card"><div class="application-title">${text(x.title,'Job')}${x.company?' — '+x.company:''}</div><div class="application-meta">Match: <span class="application-score">${x.score==null?'Not calculated':x.score+'%'}</span> | Status: ${text(x.status,'APPLIED')}</div><div class="application-meta">${text(x.applied_at,'')}</div></div>`;}page.innerHTML=html+'</div>';}catch(e){console.error(e)}
}

async function loadJobQueue(){
  const page=document.getElementById('matches'); if(!page)return;
  let queue=document.getElementById('jobQueue');
  if(!queue){queue=document.createElement('div');queue.id='jobQueue';queue.className='panel';page.appendChild(queue);}
  try{
    const r=await fetch('/api/jobs/queue'), data=await r.json(), jobs=arr(data);
    let html='<h2>Saved Job Review Queue</h2><p class="muted">Every analyzed job is saved here. Use the status buttons to triage the queue.</p>';
    if(!jobs.length){queue.innerHTML=html+'<p class="muted">No analyzed jobs saved yet.</p>';return;}
    for(const raw of jobs){const j=obj(raw); const score=j.score==null?'Not calculated':j.score+'%';
      const missing=arr(j.required_skill_matches).filter(x=>obj(x).status==='missing').map(x=>text(obj(x).job_skill,'')).filter(Boolean).slice(0,8).join(', ')||'None';
      html+=`<div class="queue-card"><div class="queue-header"><div><h3>${text(j.title,'Job')}</h3><div class="queue-meta">${text(j.company,'Company not specified')} | ${text(j.location,'Location not specified')}</div><div class="queue-meta"><span class="queue-score">${score}</span> | ${text(j.decision,'')} | Status: <strong>${text(j.status,'NEW')}</strong></div><div class="queue-meta">Missing required: ${missing}</div></div></div><div class="queue-actions">${j.job_url?`<button class="secondary-button" onclick="window.open('${String(j.job_url).replace(/'/g,'')}','_blank','noopener')">Open LinkedIn</button>`:''}<button class="secondary-button" onclick="setJobStatus('${j.id}','REVIEW')">Review</button><button class="secondary-button" onclick="setJobStatus('${j.id}','SKIPPED')">Skip</button><button class="primary-button" onclick="setJobStatus('${j.id}','APPLIED')">Applied</button></div></div>`;
    }
    queue.innerHTML=html;
  }catch(e){queue.innerHTML=`<h2>Saved Job Review Queue</h2><p>Error loading queue: ${e.message}</p>`;}
}
async function setJobStatus(id,status){
  try{const r=await fetch(`/api/jobs/queue/${id}/status`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Could not update status.');loadJobQueue();}catch(e){alert(e.message)}
}
window.setJobStatus=setJobStatus;

setupJobMatcher();
setupDescriptionControls();
loadPairOptions();
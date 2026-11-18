const request = async (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(path, {
    ...options,
    headers,
  });
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error('Your session has expired. Please sign in again.');
  }
  if (response.status === 204) return null;
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.detail || `Request failed (${response.status}).`);
  }
  return result;
};
const api = (path, options = {}) => request(`/api/recruiter${path}`, options);

const $ = (selector) => document.querySelector(selector);
const content = $('#content');
const pageTitles = {
  dashboard: ['Recruiter Dashboard', 'Live recruiting metrics from your database'],
  jobs: ['Job Search & Requirements', 'Create and manage job requirements'],
  candidates: ['Candidates', 'Manage your candidate directory'],
  matching: ['Candidate Matching Results', 'Review jobs and filter candidates by match quality'],
  submissions: ['Submission Workflow', 'Match, review, record consent, submit, and track candidates'],
  reports: ['Reports', 'Review recruiting activity and submission outcomes'],
  admin: ['Admin', 'Manage users and access helpful resources'],
  integrations: ['Integrations', 'Manage connected job sources and services'],
  help: ['Support and Help', 'Guidance for using the recruiting workspace'],
  releases: ['Release Notes', 'What is available in this release'],
  settings: ['Settings', 'Manage matching preferences'],
};
let toastTimer;
let jobs = [];
let candidates = [];
let candidateQuery = '';
let candidateSearchTimer;
let matchingResults = [];
let selectedMatchJobId = null;
let activeMatchTab = 'all';
let matchingIsLoading = false;
let submissionWizard = {
  step: 0,
  jobId: '',
  candidateId: '',
  match: null,
  consentShare: false,
  consentContact: false,
  vendor: '',
  notes: '',
  loadingMatch: false,
  saving: false,
};

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => element.classList.remove('show'), 2800);
}

function handleAction(action) {
  return (event) => {
    Promise.resolve(action(event)).catch((error) => toast(error.message));
  };
}

function statCard(label, value, icon) {
  return `<div class="card stat"><span class="stat-icon">${icon}</span><div><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></div></div>`;
}

function jobOptions(selectedId = '') {
  return jobs.map((job) => (
    `<option value="${escapeHtml(job.id)}" ${job.id === selectedId ? 'selected' : ''}>${escapeHtml(job.title)} · ${escapeHtml(job.company)}</option>`
  )).join('');
}

function candidateOptions(selectedId = '') {
  return candidates.map((candidate) => (
    `<option value="${escapeHtml(candidate.id)}" ${candidate.id === selectedId ? 'selected' : ''}>${escapeHtml(candidate.name)} · ${escapeHtml(candidate.email)}</option>`
  )).join('');
}

async function setPage(page) {
  if (!Object.prototype.hasOwnProperty.call(pageTitles, page)) page = 'dashboard';
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.page === page);
  });
  $('#page-title').textContent = pageTitles[page][0];
  $('#page-subtitle').textContent = pageTitles[page][1];
  content.innerHTML = '<div class="card empty">Loading…</div>';
  try {
    await views[page]();
  } catch (error) {
    content.innerHTML = `<div class="card empty error">${escapeHtml(error.message)}</div>`;
  }
  $('.sidebar').classList.remove('open');
}

const views = {
   dashboard: async () => {
    const [data, dashboardCandidates] = await Promise.all([
      api('/dashboard'),
      api('/candidates'),
    ]);
    const skillCounts = new Map();
    dashboardCandidates.forEach((candidate) => {
      candidate.skills.forEach((skill) => {
        const normalized = skill.trim();
        if (normalized) {
          const key = normalized.toLocaleLowerCase();
          const existing = skillCounts.get(key);
          skillCounts.set(key, {
            name: existing ? existing.name : normalized,
            count: (existing ? existing.count : 0) + 1,
          });
        }
      });
    });
    const topSkills = [...skillCounts.values()]
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
      .slice(0, 6);
    const maxSkillCount = Math.max(1, ...topSkills.map((skill) => skill.count));

    content.innerHTML = `
      <div class="grid stats">
        ${statCard('Active Jobs', data.active_jobs, '▣')}
        ${statCard('Total Candidates', data.total_candidates, '◎')}
        ${statCard('Matches Found', data.matches_found, '✦')}
        ${statCard('Submissions', data.submissions, '⇢')}
      </div>
      <div class="grid dashboard-panels">
        <section class="card">
          <div class="card-head">
            <div>
              <h2>Quick actions</h2>
              <span class="card-sub">Jump straight into your workflow</span>
            </div>
          </div>
          <div class="quick-actions">
            <button type="button" class="quick-action" data-quick-action="search-jobs">
              <span class="qa-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.4-3.4"/></svg>
              </span>
              <span class="qa-text">
                <strong>Search jobs</strong>
                <small>Find and filter job openings</small>
              </span>
              <span class="qa-arrow" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </span>
            </button>
            <button type="button" class="quick-action" data-quick-action="create-job">
              <span class="qa-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
              </span>
              <span class="qa-text">
                <strong>Create job</strong>
                <small>Add a new job requirement</small>
              </span>
              <span class="qa-arrow" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </span>
            </button>
            <button type="button" class="quick-action" data-quick-action="upload-resume">
              <span class="qa-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></svg>
              </span>
              <span class="qa-text">
                <strong>Upload resume</strong>
                <small>Analyze a resume and add a candidate</small>
              </span>
              <span class="qa-arrow" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </span>
            </button>
          </div>
        </section>
        <section class="card">
          <div class="card-head">
            <div>
              <h2>Top skills</h2>
              <span class="card-sub">Most common candidate skills</span>
            </div>
            <span class="card-badge">${topSkills.length} tracked</span>
          </div>
          ${topSkills.length ? `
            <ol class="skill-rank">
              ${topSkills.map((skill, index) => {
                const pct = Math.round((skill.count / maxSkillCount) * 100);
                return `
                <li class="skill-rank-item" style="--bar:${pct}%;--delay:${index * 60}ms">
                  <span class="skill-rank-num">${index + 1}</span>
                  <span class="skill-rank-body">
                    <span class="skill-rank-top">
                      <span class="skill-rank-name">${escapeHtml(skill.name)}</span>
                      <span class="skill-rank-count">${skill.count}</span>
                    </span>
                    <span class="skill-bar">
                      <span class="skill-bar-fill"></span>
                    </span>
                  </span>
                </li>`;
              }).join('')}
            </ol>` : '<div class="empty compact">Add candidates to see top skills.</div>'}
        </section>
      </div>
      <section class="card">
        <h2>Recent jobs</h2>
        ${data.recent_jobs.length ? `
          <div class="table-wrap"><table>
            <thead><tr><th>Title</th><th>Company</th><th>Location</th><th>Status</th></tr></thead>
            <tbody>${data.recent_jobs.map((job) => `
              <tr><td>${escapeHtml(job.title)}</td><td>${escapeHtml(job.company)}</td>
              <td>${escapeHtml(job.location || '—')}</td><td><span class="badge">${escapeHtml(job.status)}</span></td></tr>
            `).join('')}</tbody>
          </table></div>` : '<div class="empty">No jobs yet. Add one under Jobs.</div>'}
      </section>`;
    content.querySelector('[data-quick-action="search-jobs"]').addEventListener('click', handleAction(async () => {
      await setPage('jobs');
      $('#job-query').focus();
    }));
    content.querySelector('[data-quick-action="create-job"]').addEventListener('click', handleAction(async () => {
      await setPage('jobs');
      $('#job-title').focus();
    }));
    content.querySelector('[data-quick-action="upload-resume"]').addEventListener('click', handleAction(async () => {
      await setPage('candidates');
      $('#resume-file').focus();
    }));
  },

  jobs: async () => {
    jobs = await api('/jobs');
    content.innerHTML = `
      <section class="card">
        <form id="job-search-form" class="jobs-search-form">
          <div class="field jobs-search-field">
            <label for="job-query">Search jobs</label>
            <input id="job-query" type="search" placeholder="Search by title, company, location, or skill">
          </div>
          <button class="btn primary jobs-search-button" type="submit">Search</button>
        </form>
      </section>
      <section class="card import-jobs-card">
        <div class="card-head">
          <div>
            <h2>Import jobs</h2>
            <span class="card-sub">Connect a source to bring job openings into your workspace</span>
          </div>
        </div>
        <div class="job-import-actions">
          <button type="button" class="job-import-button" disabled aria-describedby="import-coming-soon">
            <span class="job-import-icon dice" aria-hidden="true">D</span>
            <span><strong>Dice</strong><small>Import from Dice</small></span>
            <span class="coming-soon">Coming soon</span>
          </button>
          <button type="button" class="job-import-button" disabled aria-describedby="import-coming-soon">
            <span class="job-import-icon careers" aria-hidden="true">↗</span>
            <span><strong>Company career sites</strong><small>Import from company websites</small></span>
            <span class="coming-soon">Coming soon</span>
          </button>
          <button type="button" class="job-import-button" disabled aria-describedby="import-coming-soon">
            <span class="job-import-icon email" aria-hidden="true">✉</span>
            <span><strong>Email</strong><small>Import jobs from your inbox</small></span>
            <span class="coming-soon">Coming soon</span>
          </button>
        </div>
        <span id="import-coming-soon" class="sr-only">Job import integrations are not available yet.</span>
      </section>
      <section class="card job-analyzer-card">
        <div class="card-head">
          <div>
            <h2>Analyze a job description</h2>
            <span class="card-sub">Paste the full description and Gemini will extract the job details for you</span>
          </div>
          <span class="ai-badge"><span aria-hidden="true">✦</span> Gemini AI</span>
        </div>
        <form id="job-analysis-form">
          <div class="field">
            <label for="job-description-input">Job description</label>
            <textarea id="job-description-input" rows="7" maxlength="100000" placeholder="Paste the job description here, including qualifications, responsibilities, location, and experience requirements…" required></textarea>
          </div>
          <div class="job-analysis-footer">
            <small>Extracted details will be added to the editable job form below.</small>
            <button id="analyze-job" class="btn primary" type="submit"><span aria-hidden="true">✦</span> Analyze description</button>
          </div>
        </form>
        <div id="job-analysis-result" class="job-analysis-result" hidden aria-live="polite"></div>
      </section>
      <section class="card">
        <div class="card-head">
          <div>
            <h2>Create a job requirement</h2>
            <span class="card-sub">Review or enter details, then save the job</span>
          </div>
        </div>
        <form id="job-form" class="grid three">
          <div class="field"><label for="job-title">Title</label><input id="job-title" name="title" required maxlength="255"></div>
          <div class="field"><label for="job-company">Company</label><input id="job-company" name="company" required maxlength="255"></div>
          <div class="field"><label for="job-location">Location</label><input id="job-location" name="location" value="Remote"></div>
          <div class="field"><label for="job-employment-type">Employment type</label><select id="job-employment-type" name="employment_type"><option>Full Time</option><option>Part Time</option><option>Contract</option><option>Temporary</option><option>Internship</option></select></div>
          <div class="field"><label for="job-skills">Required skills, comma separated</label><input id="job-skills" name="required_skills" placeholder="Python, FastAPI, Azure SQL"></div>
          <div class="field"><label for="job-experience">Minimum experience (years)</label><input id="job-experience" name="minimum_experience_years" type="number" min="0" step="0.5"></div>
          <div class="field"><label for="job-source">Source</label><select id="job-source" name="source"><option>Manual</option><option>Email</option><option>API</option><option>Career Site</option></select></div>
          <div class="field"><label for="job-description">Description</label><textarea id="job-description" name="description" rows="5"></textarea></div>
          <button class="btn primary" type="submit">Create job</button>
        </form>
      </section>
      <div id="jobs-table"></div>`;
    renderJobs(jobs);
    $('#job-form').addEventListener('submit', handleAction(createJob));
    $('#job-search-form').addEventListener('submit', (event) => {
      event.preventDefault();
      handleAction(searchJobs)(event);
    });
    $('#job-query').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        handleAction(searchJobs)(event);
      }
    });
    $('#job-analysis-form').addEventListener('submit', handleAction(analyzeJobDescription));
  },

  candidates: async () => {
    candidates = await api(`/candidates?q=${encodeURIComponent(candidateQuery)}`);
    content.innerHTML = `
      <section class="card candidate-upload-card">
        <div class="card-head">
          <div><h2>Upload and analyze a resume</h2><span class="card-sub">Start with a PDF or DOCX. The parsed profile will be ready to save below.</span></div>
          <span class="ai-badge"><span aria-hidden="true">✦</span> Resume parsing</span>
        </div>
        <form id="resume-analyze-form" class="resume-upload-form">
          <div class="field"><label for="resume-file">Resume (PDF or DOCX, up to 5 MB)</label><input id="resume-file" name="file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required></div>
          <button class="btn primary" type="submit">Analyze resume</button>
        </form>
        <div id="resume-analysis-result" class="resume-analysis-result" hidden aria-live="polite"></div>
        <form id="resume-candidate-form" class="grid three resume-review" hidden>
          <div class="field"><label for="resume-candidate-name">Candidate name</label><input id="resume-candidate-name" name="name" required maxlength="200"></div>
          <div class="field"><label for="resume-candidate-email">Email</label><input id="resume-candidate-email" name="email" type="email" required maxlength="255"></div>
          <div class="field"><label for="resume-candidate-location">Location</label><input id="resume-candidate-location" name="location"></div>
          <div class="field"><label for="resume-candidate-skills">Skills</label><input id="resume-candidate-skills" name="skills"></div>
          <div class="field"><label for="resume-candidate-role">Current role</label><input id="resume-candidate-role" name="current_role" maxlength="255"></div>
          <div class="field"><label for="resume-candidate-years">Years experience</label><input id="resume-candidate-years" name="years_experience" type="number" min="0" max="80" step="0.5"></div>
          <div class="field"><label for="resume-candidate-authorization">Work authorization</label><input id="resume-candidate-authorization" name="work_authorization" maxlength="120" placeholder="Not specified"></div>
          <div class="field"><label for="resume-candidate-notes">Recruiter notes</label><textarea id="resume-candidate-notes" name="notes" rows="2"></textarea></div>
          <button class="btn primary candidate-save-button" type="submit">Save candidate and resume</button>
        </form>
      </section>`;
    content.insertAdjacentHTML('beforeend', `
      <section class="card candidate-manual-card">
        <div class="card-head">
          <div><h2>Add candidate manually</h2><span class="card-sub">Create a profile without uploading a resume</span></div>
        </div>
        <form id="candidate-form" class="grid three">
          <div class="field"><label for="candidate-name">Name</label><input id="candidate-name" name="name" required maxlength="200"></div>
          <div class="field"><label for="candidate-email">Email</label><input id="candidate-email" name="email" type="email" required maxlength="255"></div>
          <div class="field"><label for="candidate-location">Location</label><input id="candidate-location" name="location"></div>
          <div class="field"><label for="candidate-skills">Skills</label><input id="candidate-skills" name="skills" placeholder="Python, FastAPI, SQL"></div>
          <div class="field"><label for="candidate-role">Current role</label><input id="candidate-role" name="current_role" maxlength="255"></div>
          <div class="field"><label for="candidate-years">Years experience</label><input id="candidate-years" name="years_experience" type="number" min="0" max="80" step="0.5" value="0"></div>
          <div class="field"><label for="candidate-availability">Availability</label><input id="candidate-availability" name="availability" value="Available"></div>
          <div class="field"><label for="candidate-authorization">Work authorization</label><input id="candidate-authorization" name="work_authorization" maxlength="120"></div>
          <div class="field"><label for="candidate-notes">Recruiter notes</label><textarea id="candidate-notes" name="notes" rows="2"></textarea></div>
          <button class="btn primary candidate-save-button" type="submit">Add candidate</button>
        </form>
      </section>
      <section class="card candidate-directory-card">
        <div class="card-head">
          <div><h2>Candidate directory</h2><span class="card-sub"><span id="candidate-count">${candidates.length}</span> candidates · Select a profile to see full details</span></div>
        </div>
        <form id="candidate-search-form" class="candidate-search-form">
          <label class="sr-only" for="candidate-query">Search candidates</label>
          <input id="candidate-query" type="search" value="${escapeHtml(candidateQuery)}" placeholder="Search by name, email, role, location, or skill">
          <button class="btn primary" type="submit">Search</button>
        </form>
        <div id="candidate-list" class="candidate-list">${renderCandidates(candidates)}</div>
      </section>`);
    $('#candidate-form').addEventListener('submit', handleAction(createCandidate));
    $('#resume-analyze-form').addEventListener('submit', handleAction(analyzeResume));
    $('#resume-candidate-form').addEventListener('submit', handleAction(saveResumeCandidate));
    $('#candidate-search-form').addEventListener('submit', (event) => {
      event.preventDefault();
      handleAction(searchCandidates)();
    });
    $('#candidate-query').addEventListener('input', () => {
      window.clearTimeout(candidateSearchTimer);
      candidateSearchTimer = window.setTimeout(
        handleAction(searchCandidates),
        250,
      );
    });
    content.querySelectorAll('.candidate-open').forEach((button) => {
      button.addEventListener('click', handleAction(() => showCandidateProfile(button.dataset.id)));
    });
  },

  matching: async () => {
    jobs = await api('/jobs');
    matchingResults = [];
    selectedMatchJobId = null;
    activeMatchTab = 'all';
    matchingIsLoading = false;
    renderMatchingScreen();
  },

  submissions: async () => {
    [jobs, candidates] = await Promise.all([api('/jobs'), api('/candidates')]);
    const submissions = await api('/submissions');
    const selectedJob = jobs.find((job) => String(job.id) === String(submissionWizard.jobId));
    const selectedCandidate = candidates.find(
      (candidate) => String(candidate.id) === String(submissionWizard.candidateId),
    );
    if (!selectedJob || !selectedCandidate
      || (submissionWizard.match
        && String(submissionWizard.match.candidate.id) !== String(submissionWizard.candidateId))) {
      submissionWizard = {
        step: 0,
        jobId: '',
        candidateId: '',
        match: null,
        consentShare: false,
        consentContact: false,
        vendor: '',
        notes: '',
        loadingMatch: false,
        saving: false,
      };
    }
    renderSubmissionWorkflow(submissions);
    bindSubmissionWorkflow(submissions);
  },

  reports: async () => {
    const [data, reportJobs, submissions] = await Promise.all([
      api('/dashboard'),
      api('/jobs'),
      api('/submissions'),
    ]);
    const jobStatuses = reportJobs.reduce((counts, job) => {
      const status = (job.status || 'unknown').toLowerCase();
      counts[status] = (counts[status] || 0) + 1;
      return counts;
    }, {});
    const submissionStatuses = data.submission_status || [];
    const totalSubmissions = submissionStatuses.reduce((total, item) => total + Number(item.count || 0), 0);
    const totalJobs = Object.values(jobStatuses).reduce((total, count) => total + count, 0);
    content.innerHTML = `
      <section class="reports-intro">
        <div><span class="candidate-eyebrow">RECRUITING OVERVIEW</span>
          <h2>Reports at a glance</h2>
          <p>Explore your jobs, candidate matches, and submission outcomes.</p>
        </div>
        <span class="reports-period">Live data</span>
      </section>
      <div class="grid stats reports-stats">
        ${reportStatCard('Active jobs', data.active_jobs, '▣', 'Open recruiting opportunities', 'blue')}
        ${reportStatCard('Candidates', data.total_candidates, '◎', 'Profiles in your directory', 'green')}
        ${reportStatCard('Matches found', data.matches_found, '✦', 'Candidate-job pairings', 'purple')}
        ${reportStatCard('Submissions', data.submissions, '⇢', 'Candidates sent to employers', 'amber')}
      </div>
      <div class="grid two reports-chart-grid">
        <section class="card report-chart-card">
          <div class="card-head"><div><h2>Submission outcomes</h2><span class="card-sub">Status breakdown across all submissions</span></div>
            <span class="card-badge">${totalSubmissions} total</span>
          </div>
          ${totalSubmissions ? renderReportDonut(submissionStatuses, totalSubmissions) : reportEmptyState('No submissions to chart yet.')}
        </section>
        <section class="card report-chart-card">
          <div class="card-head"><div><h2>Jobs by status</h2><span class="card-sub">Current distribution of job openings</span></div>
            <span class="card-badge">${totalJobs} total</span>
          </div>
          ${totalJobs ? renderReportBars(jobStatuses, totalJobs) : reportEmptyState('No jobs to chart yet.')}
        </section>
      </div>
      <section class="card report-recent-card">
        <div class="card-head"><div><h2>Recent submissions</h2><span class="card-sub">Latest candidate activity and status</span></div>
          <span class="card-badge">${submissions.length} records</span>
        </div>
        ${renderSubmissions(submissions)}
      </section>`;
    content.querySelectorAll('.submission-status').forEach((select) => {
      select.addEventListener('change', handleAction(() => updateStatus(select)));
    });
  },

  admin: async () => {
    const isAdmin = window.IZEALINC_USER?.role === 'admin';
    content.innerHTML = `
      <section class="admin-links-intro">
        <span class="candidate-eyebrow">WORKSPACE RESOURCES</span>
        <h2>Admin quick links</h2>
        <p>Manage workspace access or find product and API guidance.</p>
      </section>
      <div class="grid admin-quick-links">
        ${isAdmin ? `
          <a class="card admin-quick-link" href="/admin/users">
            <span class="admin-quick-icon blue">♙</span>
            <span><strong>User management</strong><small>Manage user access and roles</small></span><b aria-hidden="true">→</b>
          </a>` : `
          <article class="card admin-quick-link restricted">
            <span class="admin-quick-icon blue">♙</span>
            <span><strong>User management</strong><small>Administrator access is required</small></span><b>Restricted</b>
          </article>`}
        <a class="card admin-quick-link" href="/api/docs">
          <span class="admin-quick-icon purple">{ }</span>
          <span><strong>API documentation</strong><small>Explore available API endpoints</small></span><b aria-hidden="true">→</b>
        </a>
        <button class="card admin-quick-link" type="button" data-page-link="help">
          <span class="admin-quick-icon green">?</span>
          <span><strong>Support and Help</strong><small>Find workflow guidance and support options</small></span><b aria-hidden="true">→</b>
        </button>
        <button class="card admin-quick-link" type="button" data-page-link="releases">
          <span class="admin-quick-icon amber">✦</span>
          <span><strong>Release Notes</strong><small>See features in the current release</small></span><b aria-hidden="true">→</b>
        </button>
      </div>`;
    content.querySelectorAll('[data-page-link]').forEach((link) => {
      link.addEventListener('click', () => setPage(link.dataset.pageLink));
    });
  },

  integrations: async () => {
    const settings = await api('/settings');
    content.innerHTML = `
      <section class="card integrations-panel">
        <div class="card-head">
          <div><h2>Job source integrations</h2><span class="card-sub">Connect or disconnect services used to bring jobs into your workspace.</span></div>
        </div>
        ${settings.integrations.map((integration) => `
          <div class="integration-row">
            <strong>${escapeHtml(integration.provider)}</strong>
            <span class="badge ${integration.enabled ? '' : 'amber'}">${integration.enabled ? 'Enabled' : 'Disabled'}</span>
            <button class="btn connect" type="button" data-provider="${escapeHtml(integration.provider)}" data-enabled="${!integration.enabled}">${integration.enabled ? 'Disable' : 'Enable'}</button>
          </div>
        `).join('') || '<div class="empty">No integrations are configured.</div>'}
      </section>`;
    content.querySelectorAll('.connect').forEach((button) => {
      button.addEventListener('click', handleAction(() => toggleIntegration(button)));
    });
  },

  help: async () => {
    content.innerHTML = `
      <div class="grid two resource-page-grid">
        <section class="card resource-card">
          <span class="admin-quick-icon blue">◎</span>
          <h2>Getting started</h2>
          <p>Use Jobs to create requirements, Candidates to manage profiles, and Matching to review candidate fit. The Submissions workflow guides you through review, consent, submission, and tracking.</p>
        </section>
        <section class="card resource-card">
          <span class="admin-quick-icon purple">↗</span>
          <h2>Need assistance?</h2>
          <p>Contact your workspace administrator for account access, integration setup, or help with your organization's recruiting workflow.</p>
          <a class="btn" href="/account/sessions">Review your sign-in sessions</a>
        </section>
      </div>`;
  },

  releases: async () => {
    content.innerHTML = `
      <section class="card release-note-card">
        <div class="release-note-version"><span class="admin-quick-icon blue">✦</span><div><span class="candidate-eyebrow">CURRENT RELEASE</span><h2>Version 2.0.0</h2></div></div>
        <p class="muted">The current workspace provides an end-to-end recruiting workflow:</p>
        <ul class="release-note-list">
          <li>Manage jobs and candidate profiles in one workspace.</li>
          <li>Review candidate-to-job matches with match scores and supporting details.</li>
          <li>Move candidates through review, consent, submission, and tracking.</li>
          <li>View recruiting metrics and visual summaries in Reports.</li>
          <li>Configure job source integrations and matching preferences.</li>
        </ul>
      </section>`;
  },

  settings: async () => {
    const settings = await api('/settings');
    content.innerHTML = `
      <section class="card settings-panel">
        <h2>AI settings</h2>
        <p class="muted">The model value is saved as a preference; provider credentials and runtime model are configured by the server.</p>
        <form id="settings-form">
          <div class="field"><label for="ai-model">Model</label><input id="ai-model" name="ai_model" value="${escapeHtml(settings.ai_model)}" required maxlength="120"></div>
          <div class="field"><label for="threshold">Match threshold <b id="threshold-label">${settings.match_threshold}%</b></label><input id="threshold" name="match_threshold" type="range" min="0" max="100" value="${settings.match_threshold}"></div>
          <button class="btn primary" type="submit">Save settings</button>
        </form>
      </section>`;
    $('#threshold').addEventListener('input', (event) => {
      $('#threshold-label').textContent = `${event.target.value}%`;
    });
    $('#settings-form').addEventListener('submit', handleAction(saveSettings));
  },
};

function renderJobs(rows) {
  const table = $('#jobs-table');
  table.innerHTML = `
    <section class="card">
      ${rows.length ? `
        <div class="table-wrap"><table>
          <thead><tr><th>Title</th><th>Company</th><th>Location</th><th>Skills</th><th></th></tr></thead>
          <tbody>${rows.map((job) => `
            <tr><td>${escapeHtml(job.title)}</td><td>${escapeHtml(job.company)}</td>
            <td>${escapeHtml(job.location || '—')}</td><td>${escapeHtml(job.required_skills.join(', ') || '—')}</td>
            <td><button class="btn delete-job" type="button" data-id="${escapeHtml(job.id)}">Delete</button></td></tr>
          `).join('')}</tbody>
        </table></div>` : '<div class="empty">No jobs found.</div>'}
    </section>`;
  table.querySelectorAll('.delete-job').forEach((button) => {
    button.addEventListener('click', handleAction(() => deleteJob(button.dataset.id)));
  });
}

function renderSubmissions(rows) {
  if (!rows.length) return '<div class="empty">No submissions yet.</div>';
  const statuses = ['submitted', 'interview', 'offer', 'rejected', 'withdrawn'];
  return `
    <div class="table-wrap"><table>
      <thead><tr><th>Candidate</th><th>Job</th><th>Vendor</th><th>Status</th></tr></thead>
      <tbody>${rows.map((submission) => `
        <tr><td>${escapeHtml(submission.candidate.name)}</td><td>${escapeHtml(submission.job.title)}</td>
        <td>${escapeHtml(submission.vendor)}</td><td><select class="submission-status" data-id="${escapeHtml(submission.id)}">
          ${statuses.map((status) => `<option value="${status}" ${status === submission.status ? 'selected' : ''}>${status}</option>`).join('')}
        </select></td></tr>
      `).join('')}</tbody>
    </table></div>`;
}

function submissionSelectionSummary(job, candidate, match = null) {
  if (!job || !candidate) {
    return '<div class="empty">Choose both a job and a candidate to see their details.</div>';
  }
  const score = match && match.score != null ? `${escapeHtml(match.score)}%` : 'Not calculated';
  return `
    <div class="submission-summary-grid">
      <article class="submission-detail-card">
        <span class="candidate-eyebrow">CANDIDATE</span>
        <h3>${escapeHtml(candidate.name)}</h3>
        <p>${escapeHtml(candidate.current_role || 'Role not specified')}</p>
        <dl>
          <div><dt>Email</dt><dd>${escapeHtml(candidate.email || 'Not provided')}</dd></div>
          <div><dt>Location</dt><dd>${escapeHtml(candidate.location || 'Not specified')}</dd></div>
          <div><dt>Experience</dt><dd>${candidate.years_experience == null ? 'Not specified' : `${escapeHtml(candidate.years_experience)} years`}</dd></div>
          <div><dt>Skills</dt><dd>${escapeHtml((candidate.skills || []).join(', ') || 'Not specified')}</dd></div>
        </dl>
      </article>
      <article class="submission-detail-card">
        <span class="candidate-eyebrow">JOB</span>
        <h3>${escapeHtml(job.title)}</h3>
        <p>${escapeHtml(job.company)}</p>
        <dl>
          <div><dt>Work mode</dt><dd>${escapeHtml(jobWorkMode(job.location))}</dd></div>
          <div><dt>Location</dt><dd>${escapeHtml(job.location || 'Not specified')}</dd></div>
          <div><dt>Employment</dt><dd>${escapeHtml(job.employment_type || 'Not specified')}</dd></div>
          <div><dt>Required skills</dt><dd>${escapeHtml((job.required_skills || []).join(', ') || 'Not specified')}</dd></div>
        </dl>
      </article>
      <article class="submission-match-card">
        <span class="candidate-eyebrow">MATCH SCORE</span>
        <strong>${score}</strong>
        <p>${escapeHtml(match ? (match.decision || 'Match calculated').replaceAll('_', ' ') : 'Calculate the match to continue.')}</p>
        ${match ? `<small>${escapeHtml(match.explanation || '')}</small>` : ''}
      </article>
    </div>`;
}

function renderSubmissionStepContent(submissions) {
  const job = jobs.find((item) => String(item.id) === String(submissionWizard.jobId));
  const candidate = candidates.find((item) => String(item.id) === String(submissionWizard.candidateId));
  const summary = submissionSelectionSummary(job, candidate, submissionWizard.match);

  if (submissionWizard.step === 0) {
    return `
      <section class="card submission-step-card">
        <h2>Match candidate to a job</h2>
        <p class="card-sub">Choose a candidate and an active job to calculate a match before starting the submission.</p>
        <div class="grid two submission-select-grid">
          <div class="field"><label for="submission-job">Job</label>
            <select id="submission-job"><option value="">Select a job</option>${jobs.map((jobItem) => `
              <option value="${escapeHtml(jobItem.id)}" ${String(jobItem.id) === String(submissionWizard.jobId) ? 'selected' : ''}>
                ${escapeHtml(jobItem.title)} · ${escapeHtml(jobItem.company)}
              </option>`).join('')}</select>
          </div>
          <div class="field"><label for="submission-candidate">Candidate</label>
            <select id="submission-candidate"><option value="">Select a candidate</option>${candidates.map((candidateItem) => `
              <option value="${escapeHtml(candidateItem.id)}" ${String(candidateItem.id) === String(submissionWizard.candidateId) ? 'selected' : ''}>
                ${escapeHtml(candidateItem.name)} · ${escapeHtml(candidateItem.email)}
              </option>`).join('')}</select>
          </div>
        </div>
        ${job && candidate ? summary : ''}
        <div class="submission-step-actions">
          <button class="btn primary" id="calculate-submission-match" type="button"
            ${!job || !candidate || submissionWizard.loadingMatch ? 'disabled' : ''}>
            ${submissionWizard.loadingMatch ? 'Calculating…' : 'Calculate match'}
          </button>
          ${submissionWizard.match ? '<button class="btn primary submission-next" type="button">Continue to review</button>' : ''}
        </div>
      </section>`;
  }

  if (submissionWizard.step === 1) {
    return `
      <section class="card submission-step-card">
        <h2>Review candidate and job</h2>
        <p class="card-sub">Confirm the candidate information and role requirements before requesting consent.</p>
        ${summary}
        <div class="submission-review-skills">
          <div><strong>Matched skills</strong><span>${escapeHtml(submissionWizard.match?.matched_skills || 'None identified')}</span></div>
          <div><strong>Skills to develop</strong><span>${escapeHtml(submissionWizard.match?.missing_skills || 'None identified')}</span></div>
          <div><strong>Experience check</strong><span>${submissionWizard.match?.experience_pass == null ? 'Not specified' : submissionWizard.match.experience_pass ? 'Requirement met' : 'Below job requirement'}</span></div>
        </div>
        <div class="submission-step-actions">
          <button class="btn submission-back" type="button">Back to match</button>
          <button class="btn primary submission-next" type="button">Continue to consent</button>
        </div>
      </section>`;
  }

  if (submissionWizard.step === 2) {
    return `
      <section class="card submission-step-card">
        <h2>Candidate consent</h2>
        <p class="card-sub">Record the candidate’s permission before any résumé or personal details are shared.</p>
        ${summary}
        <div class="submission-consent-list">
          <label class="submission-consent-option">
            <input id="consent-share" type="checkbox" ${submissionWizard.consentShare ? 'checked' : ''}>
            <span><strong>Consent to share résumé</strong><small>Candidate authorizes sharing their résumé and profile with the selected employer or vendor.</small></span>
          </label>
          <label class="submission-consent-option">
            <input id="consent-contact" type="checkbox" ${submissionWizard.consentContact ? 'checked' : ''}>
            <span><strong>Consent to direct contact</strong><small>Candidate authorizes the employer or vendor to contact them directly.</small></span>
          </label>
        </div>
        <div class="submission-step-actions">
          <button class="btn submission-back" type="button">Back to review</button>
          <button class="btn primary submission-next" type="button"
            ${!submissionWizard.consentShare || !submissionWizard.consentContact ? 'disabled' : ''}>
            Continue to submit
          </button>
        </div>
      </section>`;
  }

  if (submissionWizard.step === 3) {
    return `
      <section class="card submission-step-card">
        <h2>Submission summary</h2>
        <p class="card-sub">Confirm the details below. Both consent permissions are required to submit.</p>
        ${summary}
        <div class="submission-summary-consent">
          <span class="badge blue">Résumé sharing consent recorded</span>
          <span class="badge blue">Direct-contact consent recorded</span>
        </div>
        <form id="submission-form" class="submission-submit-form">
          <div class="field"><label for="submission-vendor">Submit to employer or vendor</label>
            <input id="submission-vendor" name="vendor" required maxlength="255" value="${escapeHtml(submissionWizard.vendor)}" placeholder="Company or staffing vendor">
          </div>
          <div class="field"><label for="submission-notes">Submission notes</label>
            <textarea id="submission-notes" name="notes" rows="3" maxlength="10000">${escapeHtml(submissionWizard.notes)}</textarea>
          </div>
          <div class="submission-step-actions">
            <button class="btn submission-back" type="button">Back to consent</button>
            <button class="btn primary" type="submit" ${submissionWizard.saving ? 'disabled' : ''}>
              ${submissionWizard.saving ? 'Submitting…' : 'Submit candidate'}
            </button>
          </div>
        </form>
      </section>`;
  }

  return `
    <section class="card submission-step-card">
      <div class="card-head"><div><h2>Submission tracking</h2><span class="card-sub">Review candidate, job, consent, recipient, and status for every submission.</span></div>
        <span class="card-badge">${submissions.length} submissions</span>
      </div>
      ${submissions.length ? `<div class="submission-tracking-list">${submissions.map((submission) => `
        <article class="submission-tracking-card">
          <div class="submission-tracking-heading">
            <div><span class="candidate-eyebrow">CANDIDATE</span><h3>${escapeHtml(submission.candidate.name)}</h3>
              <p>${escapeHtml(submission.candidate.current_role || submission.candidate.email || 'Role not specified')}</p></div>
            <span class="badge blue">${escapeHtml(submission.status)}</span>
          </div>
          <div class="submission-tracking-summary">
            <span><strong>Job</strong>${escapeHtml(submission.job.title)} · ${escapeHtml(submission.job.company)}</span>
            <span><strong>Work arrangement</strong>${escapeHtml(jobWorkMode(submission.job.location))} · ${escapeHtml(submission.job.employment_type || 'Employment not specified')}</span>
            <span><strong>Recipient</strong>${escapeHtml(submission.vendor)}</span>
            <span><strong>Submitted</strong>${escapeHtml(submission.created_at ? new Date(submission.created_at).toLocaleString() : 'Date not available')}</span>
          </div>
          <div class="submission-tracking-consent">
            <span class="badge ${submission.consent_share ? 'blue' : 'amber'}">Résumé sharing ${submission.consent_share ? 'consented' : 'not recorded'}</span>
            <span class="badge ${submission.consent_contact ? 'blue' : 'amber'}">Direct contact ${submission.consent_contact ? 'consented' : 'not recorded'}</span>
          </div>
          ${submission.notes ? `<p class="submission-tracking-notes"><strong>Notes</strong> ${escapeHtml(submission.notes)}</p>` : ''}
          <label class="submission-status-control">Update status
            <select class="submission-status" data-id="${escapeHtml(submission.id)}">
              ${['submitted', 'interview', 'offer', 'rejected', 'withdrawn'].map((status) => `
                <option value="${status}" ${status === submission.status ? 'selected' : ''}>${status}</option>`).join('')}
            </select>
          </label>
        </article>`).join('')}</div>` : '<div class="empty">No candidates have been submitted yet. Complete the Match, Review, Consent, and Submit steps to start tracking.</div>'}
    </section>`;
}

function renderSubmissionWorkflow(submissions) {
  const steps = ['Match', 'Review', 'Consent', 'Submit', 'Track'];
  content.innerHTML = `
    <section class="submission-workflow">
      <nav class="submission-stepper" aria-label="Submission steps">
        ${steps.map((label, index) => `
          <button type="button" class="submission-step ${submissionWizard.step === index ? 'active' : ''} ${submissionWizard.step > index ? 'complete' : ''}"
            data-submission-step="${index}" aria-current="${submissionWizard.step === index ? 'step' : 'false'}">
            <span>${submissionWizard.step > index ? '✓' : index + 1}</span><strong>${label}</strong>
          </button>`).join('')}
      </nav>
      <p class="submission-step-intro">${[
        'Select a candidate and job, then calculate their match.',
        'Review candidate details, job details, and match evidence.',
        'Record both candidate permissions before sharing.',
        'Confirm the recipient and submission summary.',
        'Track submission status, recipient, and consent.',
      ][submissionWizard.step]}</p>
      ${renderSubmissionStepContent(submissions)}
    </section>`;
}

function bindSubmissionWorkflow(submissions) {
  content.querySelectorAll('[data-submission-step]').forEach((button) => {
    button.addEventListener('click', () => {
      const step = Number(button.dataset.submissionStep);
      if (step === 4 || step <= submissionWizard.step) {
        submissionWizard.step = step;
        renderSubmissionWorkflow(submissions);
        bindSubmissionWorkflow(submissions);
      }
    });
  });
  const jobSelect = $('#submission-job');
  if (jobSelect) {
    jobSelect.addEventListener('change', () => {
      submissionWizard.jobId = jobSelect.value;
      submissionWizard.match = null;
      renderSubmissionWorkflow(submissions);
      bindSubmissionWorkflow(submissions);
    });
    $('#submission-candidate').addEventListener('change', (event) => {
      submissionWizard.candidateId = event.currentTarget.value;
      submissionWizard.match = null;
      renderSubmissionWorkflow(submissions);
      bindSubmissionWorkflow(submissions);
    });
  }
  $('#calculate-submission-match')?.addEventListener('click', handleAction(calculateSubmissionMatch));
  content.querySelectorAll('.submission-next').forEach((button) => {
    button.addEventListener('click', () => {
      if (submissionWizard.step <= 1
        && (!submissionWizard.jobId || !submissionWizard.candidateId || !submissionWizard.match)) return;
      if (submissionWizard.step === 2 && (!submissionWizard.consentShare || !submissionWizard.consentContact)) return;
      submissionWizard.step += 1;
      renderSubmissionWorkflow(submissions);
      bindSubmissionWorkflow(submissions);
    });
  });
  content.querySelectorAll('.submission-back').forEach((button) => {
    button.addEventListener('click', () => {
      submissionWizard.step = Math.max(0, submissionWizard.step - 1);
      renderSubmissionWorkflow(submissions);
      bindSubmissionWorkflow(submissions);
    });
  });
  $('#consent-share')?.addEventListener('change', (event) => {
    submissionWizard.consentShare = event.currentTarget.checked;
    const nextButton = $('.submission-next');
    if (nextButton) nextButton.disabled = !submissionWizard.consentShare || !submissionWizard.consentContact;
  });
  $('#consent-contact')?.addEventListener('change', (event) => {
    submissionWizard.consentContact = event.currentTarget.checked;
    const nextButton = $('.submission-next');
    if (nextButton) nextButton.disabled = !submissionWizard.consentShare || !submissionWizard.consentContact;
  });
  $('#submission-vendor')?.addEventListener('input', (event) => {
    submissionWizard.vendor = event.currentTarget.value;
  });
  $('#submission-notes')?.addEventListener('input', (event) => {
    submissionWizard.notes = event.currentTarget.value;
  });
  $('#submission-form')?.addEventListener('submit', handleAction(createSubmission));
  content.querySelectorAll('.submission-status').forEach((select) => {
    select.addEventListener('change', handleAction(() => updateStatus(select)));
  });
}

async function calculateSubmissionMatch() {
  if (!submissionWizard.jobId || !submissionWizard.candidateId) {
    throw new Error('Select both a job and a candidate first.');
  }
  submissionWizard.loadingMatch = true;
  let currentSubmissions = [];
  try {
    currentSubmissions = await api('/submissions');
    renderSubmissionWorkflow(currentSubmissions);
    bindSubmissionWorkflow(currentSubmissions);
    const matches = await api('/matches/run', {
      method: 'POST',
      body: JSON.stringify({ job_id: Number(submissionWizard.jobId) }),
    });
    submissionWizard.match = matches.find(
      (match) => String(match.candidate.id) === String(submissionWizard.candidateId),
    ) || null;
    if (!submissionWizard.match) {
      throw new Error('No match result was returned for the selected candidate.');
    }
  } finally {
    submissionWizard.loadingMatch = false;
    renderSubmissionWorkflow(currentSubmissions);
    bindSubmissionWorkflow(currentSubmissions);
  }
}

function reportStatCard(label, value, icon, caption, tone) {
  return `
    <article class="card report-stat-card ${tone}">
      <span class="report-stat-icon" aria-hidden="true">${icon}</span>
      <div class="report-stat-copy"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value ?? 0)}</strong><span>${escapeHtml(caption)}</span></div>
      <span class="report-stat-mark" aria-hidden="true">↗</span>
    </article>`;
}

function reportEmptyState(message) {
  return `<div class="report-empty-state"><span aria-hidden="true">◌</span><p>${escapeHtml(message)}</p></div>`;
}

function renderReportDonut(items, total) {
  const colors = ['#0878dd', '#18a36f', '#f6a722', '#8a6de9', '#e45b67', '#54b5c9'];
  let offset = 0;
  const segments = items.map((item, index) => {
    const count = Number(item.count || 0);
    const share = total ? (count / total) * 100 : 0;
    const start = offset;
    offset += share;
    return {
      label: item.status || 'Unknown',
      count,
      share,
      color: colors[index % colors.length],
      range: `${start}% ${offset}%`,
    };
  });
  const gradient = segments.map((segment) => `${segment.color} ${segment.range}`).join(', ');
  return `
    <div class="report-donut-layout">
      <div class="report-donut" role="img" aria-label="${escapeHtml(segments.map((item) => `${item.label}: ${item.count}`).join(', '))}"
        style="--donut-gradient: conic-gradient(${gradient})">
        <div><strong>${total}</strong><span>submissions</span></div>
      </div>
      <ul class="report-legend">
        ${segments.map((segment) => `
          <li><span class="report-legend-swatch" style="--legend-color:${segment.color}"></span>
            <span class="report-legend-label">${escapeHtml(segment.label)}</span>
            <strong>${segment.count}</strong><small>${Math.round(segment.share)}%</small>
          </li>`).join('')}
      </ul>
    </div>`;
}

function renderReportBars(statusCounts, total) {
  const colors = { active: '#18a36f', draft: '#0878dd', paused: '#f6a722', closed: '#8a6de9' };
  const entries = Object.entries(statusCounts).sort((left, right) => right[1] - left[1]);
  const maxCount = Math.max(1, ...entries.map(([, count]) => count));
  return `
    <div class="report-bars" role="img" aria-label="${entries.map(([status, count]) => `${status}: ${count}`).join(', ')}">
      ${entries.map(([status, count]) => {
        const width = Math.max(5, (count / maxCount) * 100);
        const percentage = total ? Math.round((count / total) * 100) : 0;
        const color = colors[status] || '#54b5c9';
        return `
          <div class="report-bar-row">
            <div class="report-bar-label"><span>${escapeHtml(status)}</span><strong>${count}</strong></div>
            <div class="report-bar-track"><span style="--bar-width:${width}%;--bar-color:${color}"></span></div>
            <small>${percentage}% of jobs</small>
          </div>`;
      }).join('')}
    </div>`;
}

function renderCandidates(rows) {
  if (!rows.length) {
    return `<div class="empty candidate-empty">${candidateQuery
      ? 'No candidates match your search.'
      : 'No candidates yet. Upload a resume or add a candidate manually above.'}</div>`;
  }
  return rows.map((candidate) => `
    <button class="candidate-row candidate-open" type="button" data-id="${escapeHtml(candidate.id)}">
      <span class="candidate-avatar">${escapeHtml((candidate.name || '?').trim().slice(0, 1).toUpperCase())}</span>
      <span class="candidate-row-main">
        <strong>${escapeHtml(candidate.name)}</strong>
        <small>${escapeHtml(candidate.current_role || candidate.email)}</small>
      </span>
      <span class="candidate-row-meta">
        <span>${escapeHtml(candidate.location || 'Location not set')}</span>
        <span>${candidate.years_experience ? `${escapeHtml(candidate.years_experience)} yrs experience` : 'Experience not set'}</span>
      </span>
      <span class="candidate-row-skills">${escapeHtml(candidate.skills.slice(0, 4).join(' · ') || 'No skills added')}</span>
      <span class="candidate-row-arrow" aria-hidden="true">›</span>
    </button>
  `).join('');
}

async function searchCandidates() {
  candidateQuery = $('#candidate-query').value.trim();
  candidates = await api(`/candidates?q=${encodeURIComponent(candidateQuery)}`);
  $('#candidate-count').textContent = candidates.length;
  $('#candidate-list').innerHTML = renderCandidates(candidates);
  content.querySelectorAll('.candidate-open').forEach((button) => {
    button.addEventListener('click', handleAction(() => showCandidateProfile(button.dataset.id)));
  });
}

function profileSkillName(skill) {
  return typeof skill === 'string' ? skill : skill && skill.name ? skill.name : '';
}

function renderCandidateProfile(candidate) {
  const profile = candidate.profile || {};
  const parsedSkills = profile.technical_skills || [];
  const skills = (parsedSkills.length ? parsedSkills : candidate.skills || [])
    .map((skill) => typeof skill === 'string' ? { name: skill } : skill)
    .filter((skill, index, list) => (
      skill && skill.name
      && list.findIndex((item) => item && item.name && item.name.trim().toLowerCase() === skill.name.trim().toLowerCase()) === index
    ));
  const roles = [...new Set((profile.roles || []).filter(Boolean))];
  const parsedHistory = (profile.work_history || []).map((entry) => (
    typeof entry === 'string' ? { title: entry } : entry
  ));
  const workHistory = parsedHistory.length
    ? parsedHistory
    : roles.map((role) => ({ title: role }));
  const experience = candidate.years_experience || profile.total_experience_years;
  const generatedSummary = [
    candidate.current_role,
    experience ? `${experience} years of experience` : '',
    candidate.location ? `based in ${candidate.location}` : '',
  ].filter(Boolean).join(', ');
  const summary = profile.professional_summary || generatedSummary || 'No summary available yet.';
  const education = [...new Set(profile.education || [])];
  const certifications = [...new Set(profile.certifications || [])];
  const historyText = workHistory.map((role) => [
    role.title || '',
    role.company || '',
    role.start_date || '',
    role.end_date || '',
    role.description || '',
  ].join(' | ')).join('\n');

  return `
    <div class="candidate-profile-toolbar">
      <button id="back-to-candidates" class="btn" type="button"><span aria-hidden="true">←</span> Candidate directory</button>
    </div>
    <div class="candidate-profile-layout">
      <div class="candidate-profile-main">
        <section class="card candidate-overview-card">
          <div class="candidate-profile-heading">
            <span class="candidate-avatar large">${escapeHtml((candidate.name || '?').trim().slice(0, 1).toUpperCase())}</span>
            <div>
              <span class="candidate-eyebrow">CANDIDATE PROFILE</span>
              <h2>${escapeHtml(candidate.name)}</h2>
              <p>${escapeHtml(candidate.current_role || 'Role not specified')}</p>
            </div>
          </div>
          <div class="candidate-overview-grid">
            <div><small>Email</small><strong>${escapeHtml(candidate.email || 'Not provided')}</strong></div>
            <div><small>Location</small><strong>${escapeHtml(candidate.location || 'Not provided')}</strong></div>
            <div><small>Experience</small><strong>${experience ? `${escapeHtml(experience)} years` : 'Not specified'}</strong></div>
            <div><small>Availability</small><strong>${escapeHtml(candidate.availability || 'Not specified')}</strong></div>
          </div>
          <div class="candidate-summary-block">
            <h3>Overview</h3>
            <p>${escapeHtml(summary)}</p>
          </div>
          <div class="candidate-edit-toolbar">
            <button id="toggle-candidate-edit" class="btn" type="button" aria-expanded="false">Edit profile</button>
          </div>
          <form id="candidate-edit-form" class="candidate-edit-form" data-id="${escapeHtml(candidate.id)}" hidden>
            <div class="grid two">
              <div class="field"><label for="profile-name">Name</label><input id="profile-name" name="name" required maxlength="200" value="${escapeHtml(candidate.name || '')}"></div>
              <div class="field"><label for="profile-email">Email</label><input id="profile-email" name="email" type="email" required maxlength="255" value="${escapeHtml(candidate.email || '')}"></div>
              <div class="field"><label for="profile-role">Current role</label><input id="profile-role" name="current_role" maxlength="255" value="${escapeHtml(candidate.current_role || '')}"></div>
              <div class="field"><label for="profile-location">Location</label><input id="profile-location" name="location" value="${escapeHtml(candidate.location || '')}"></div>
              <div class="field"><label for="profile-years">Years experience</label><input id="profile-years" name="years_experience" type="number" min="0" max="80" step="0.5" value="${candidate.years_experience ?? ''}"></div>
              <div class="field"><label for="profile-availability">Availability</label><input id="profile-availability" name="availability" maxlength="50" value="${escapeHtml(candidate.availability || '')}"></div>
              <div class="field"><label for="profile-authorization">Work authorization</label><input id="profile-authorization" name="work_authorization" maxlength="120" value="${escapeHtml(candidate.work_authorization || profile.work_authorization || '')}"></div>
              <div class="field"><label for="profile-skills">Skills (comma separated)</label><input id="profile-skills" name="skills" value="${escapeHtml(skills.map((skill) => skill.name).join(', '))}"></div>
            </div>
            <div class="field"><label for="profile-summary">Professional summary</label><textarea id="profile-summary" name="professional_summary" rows="3">${escapeHtml(profile.professional_summary || '')}</textarea></div>
            <div class="field"><label for="profile-history">Work history</label><textarea id="profile-history" name="work_history" rows="5" placeholder="Title | Company | Start date | End date | Description">${escapeHtml(historyText)}</textarea><small>One role per line: title | company | start date | end date | description</small></div>
            <div class="grid two">
              <div class="field"><label for="profile-education">Education (one item per line)</label><textarea id="profile-education" name="education" rows="3">${escapeHtml(education.join('\n'))}</textarea></div>
              <div class="field"><label for="profile-certifications">Certifications (one item per line)</label><textarea id="profile-certifications" name="certifications" rows="3">${escapeHtml(certifications.join('\n'))}</textarea></div>
            </div>
            <div class="field"><label for="profile-notes">Recruiter notes</label><textarea id="profile-notes" name="notes" rows="3">${escapeHtml(candidate.notes || '')}</textarea></div>
            <div class="candidate-edit-actions">
              <button class="btn primary" type="submit">Save profile</button>
              <button id="cancel-candidate-edit" class="btn" type="button">Cancel</button>
            </div>
          </form>
        </section>

        <section class="card candidate-section-card">
          <div class="card-head"><div><h2>Resume</h2><span class="card-sub">${escapeHtml(candidate.resume_file || 'No resume uploaded')}</span></div></div>
          ${candidate.resume_url
            ? `<a class="btn resume-view-link" href="${escapeHtml(candidate.resume_url)}" target="_blank" rel="noopener noreferrer">↗ View resume</a>`
            : '<p class="muted">Upload a resume to view the original document.</p>'}
        </section>

        <section class="card candidate-section-card">
          <div class="card-head"><div><h2>Skills</h2><span class="card-sub">${skills.length} extracted skills</span></div></div>
          ${skills.length ? `
            <div class="candidate-skill-list">${skills.map((skill) => `
              <span class="candidate-skill-chip">${escapeHtml(skill.name)}${skill.experience_years != null ? `<small>${escapeHtml(skill.experience_years)} yrs</small>` : ''}</span>
            `).join('')}</div>
            ${skills.some((skill) => skill.evidence) ? `
              <details class="skill-evidence">
                <summary>View resume evidence</summary>
                <ul>${skills.filter((skill) => skill.evidence).map((skill) => `<li><strong>${escapeHtml(skill.name)}:</strong> ${escapeHtml(skill.evidence)}</li>`).join('')}</ul>
              </details>` : ''}` : '<p class="muted">No parsed skills are available.</p>'}
        </section>

        <section class="card candidate-section-card">
          <div class="card-head"><div><h2>Experience</h2><span class="card-sub">Career experience extracted from the resume</span></div></div>
          <div class="experience-highlight"><strong>${experience ? `${escapeHtml(experience)} years` : 'Not specified'}</strong><span>total experience</span></div>
          ${education.length ? `<h3 class="profile-subheading">Education</h3><ul class="profile-list">${education.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
          ${certifications.length ? `<h3 class="profile-subheading">Certifications</h3><ul class="profile-list">${certifications.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
        </section>

        <section class="card candidate-section-card">
          <div class="card-head"><div><h2>Work history</h2><span class="card-sub">Roles listed in the resume</span></div></div>
          ${workHistory.length ? `<ol class="work-history-list">${workHistory.map((role) => `
            <li><span class="work-history-dot"></span><div>
              <strong>${escapeHtml(role.title || 'Role')}</strong>
              ${role.company ? `<span>${escapeHtml(role.company)}</span>` : ''}
              ${role.start_date || role.end_date ? `<small>${escapeHtml([role.start_date, role.end_date || 'Present'].filter(Boolean).join(' – '))}</small>` : ''}
              ${role.description ? `<p>${escapeHtml(role.description)}</p>` : ''}
            </div></li>`).join('')}</ol>`
            : roles.length ? `<ol class="work-history-list">${roles.map((role) => `<li><span class="work-history-dot"></span><div><strong>${escapeHtml(role)}</strong></div></li>`).join('')}</ol>`
            : candidate.current_role
              ? `<ol class="work-history-list"><li><span class="work-history-dot"></span><div><strong>${escapeHtml(candidate.current_role)}</strong><small>Current role</small></div></li></ol>`
              : '<p class="muted">No work history was extracted.</p>'}
        </section>

        <section class="card candidate-section-card">
          <div class="card-head"><div><h2>Recruiter notes</h2><span class="card-sub">Private notes for this candidate</span></div></div>
          <p>${escapeHtml(candidate.notes || 'No recruiter notes yet.')}</p>
        </section>
      </div>

      <aside class="candidate-profile-aside">
        <section class="card profile-aside-card candidate-summary-card">
          <span class="aside-card-icon" aria-hidden="true">✦</span>
          <h3>Summary</h3>
          <p>${escapeHtml(summary)}</p>
          <div class="summary-metrics">
            <span><strong>${skills.length}</strong><small>skills</small></span>
            <span><strong>${roles.length || (candidate.current_role ? 1 : 0)}</strong><small>roles</small></span>
            <span><strong>${experience ? escapeHtml(experience) : '—'}</strong><small>years</small></span>
          </div>
        </section>
        <section class="card profile-aside-card">
          <h3>Resume parsing</h3>
          <div class="parsing-status"><span class="status-dot ${candidate.resume_candidate_id ? 'complete' : ''}"></span><strong>${candidate.resume_candidate_id ? 'Parsed' : 'Not parsed'}</strong></div>
          <p>${candidate.resume_candidate_id ? 'Structured information extracted from the uploaded resume.' : 'Upload and analyze a resume to populate profile details.'}</p>
          ${profile.extraction_method ? `<small class="muted">${escapeHtml(profile.extraction_method)}</small>` : ''}
        </section>
        <section class="card profile-aside-card">
          <h3>Work authorization</h3>
          <p>${escapeHtml(candidate.work_authorization || profile.work_authorization || 'Not specified')}</p>
        </section>
        <section class="card profile-aside-card">
          <h3>Profile status</h3>
          <div class="profile-status-row"><span>Added</span><strong>${escapeHtml(candidate.created_at ? new Date(candidate.created_at).toLocaleDateString() : '—')}</strong></div>
          <div class="profile-status-row"><span>Availability</span><strong>${escapeHtml(candidate.availability || 'Not specified')}</strong></div>
        </section>
      </aside>
    </div>`;
}

async function showCandidateProfile(candidateId) {
  const candidate = await api(`/candidates/${encodeURIComponent(candidateId)}`);
  content.innerHTML = renderCandidateProfile(candidate);
  $('#back-to-candidates').addEventListener('click', handleAction(async () => {
    await views.candidates();
  }));
  const editForm = $('#candidate-edit-form');
  $('#toggle-candidate-edit').addEventListener('click', () => {
    editForm.hidden = !editForm.hidden;
    $('#toggle-candidate-edit').setAttribute('aria-expanded', String(!editForm.hidden));
    if (!editForm.hidden) $('#profile-name').focus();
  });
  $('#cancel-candidate-edit').addEventListener('click', () => {
    editForm.hidden = true;
    $('#toggle-candidate-edit').setAttribute('aria-expanded', 'false');
  });
  editForm.addEventListener('submit', handleAction(updateCandidateProfile));
}

async function updateCandidateProfile(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  const oldProfile = (await api(`/candidates/${encodeURIComponent(form.dataset.id)}`)).profile || {};
  const oldSkills = oldProfile.technical_skills || [];
  const skillsByName = new Map(oldSkills.map((skill) => [
    (typeof skill === 'string' ? skill : skill.name || '').trim().toLowerCase(),
    skill,
  ]));
  const skills = [...new Set(values.skills.split(',').map((skill) => skill.trim()).filter(Boolean))];
  const workHistory = values.work_history.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [title = '', company = '', start_date = '', end_date = '', ...description] = line.split('|').map((part) => part.trim());
    return { title, company, start_date, end_date, description: description.join(' | ') };
  });
  values.years_experience = values.years_experience === '' ? 0 : Number(values.years_experience);
  values.profile = {
    ...oldProfile,
    current_role: values.current_role,
    location: values.location,
    total_experience_years: values.years_experience || null,
    professional_summary: values.professional_summary.trim(),
    technical_skills: skills.map((skill) => skillsByName.get(skill.toLowerCase()) || { name: skill }),
    work_history: workHistory,
    roles: workHistory.map((role) => role.title).filter(Boolean),
    education: values.education.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    certifications: values.certifications.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    work_authorization: values.work_authorization.trim(),
  };
  values.skills = skills;
  delete values.professional_summary;
  delete values.work_history;
  delete values.education;
  delete values.certifications;
  await api(`/candidates/${encodeURIComponent(form.dataset.id)}`, {
    method: 'PATCH',
    body: JSON.stringify(values),
  });
  toast('Candidate profile updated.');
  await showCandidateProfile(form.dataset.id);
}

async function searchJobs() {
  jobs = await api(`/jobs?q=${encodeURIComponent($('#job-query').value)}`);
  renderJobs(jobs);
}

function analysisDetail(label, values) {
  const items = (Array.isArray(values) ? values : [values])
    .map((value) => String(value || '').trim())
    .filter(Boolean);
  if (!items.length) return '';
  return `
    <div class="analysis-detail">
      <strong>${escapeHtml(label)}</strong>
      <span>${items.map(escapeHtml).join(', ')}</span>
    </div>`;
}

function renderJobAnalysis(profile) {
  const details = [
    analysisDetail('Preferred skills', profile.preferred_skills),
    analysisDetail('Experience range', [
      profile.minimum_experience_years != null
        ? `${profile.minimum_experience_years}+ years minimum`
        : '',
      profile.maximum_experience_years != null
        ? `${profile.maximum_experience_years} years maximum`
        : '',
    ]),
    analysisDetail('Work mode', profile.work_mode),
    analysisDetail('Responsibilities', profile.responsibilities),
    analysisDetail('Education', profile.education),
    analysisDetail('Certifications', profile.certifications),
    analysisDetail('Domains', profile.domains),
    analysisDetail('Notes', profile.extraction_notes),
  ].filter(Boolean);
  return `
    <div class="analysis-result-heading">
      <span class="analysis-success-icon" aria-hidden="true">✓</span>
      <div><strong>Analysis complete</strong><small>Check the extracted details and edit them as needed before saving.</small></div>
    </div>
    ${details.length ? `<div class="analysis-details">${details.join('')}</div>` : ''}`;
}

async function analyzeJobDescription(event) {
  event.preventDefault();
  const description = $('#job-description-input').value.trim();
  if (!description) throw new Error('Paste a job description before analyzing.');

  const button = $('#analyze-job');
  const previousLabel = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '<span class="loading-spinner" aria-hidden="true"></span> Analyzing…';
  try {
    const profile = await api('/jobs/analyze', {
      method: 'POST',
      body: JSON.stringify({ description }),
    });
    $('#job-title').value = profile.title || '';
    $('#job-company').value = profile.company || '';
    $('#job-location').value = profile.location || '';
    $('#job-skills').value = (profile.required_skills || []).join(', ');
    $('#job-experience').value = profile.minimum_experience_years ?? '';
    $('#job-description').value = description;
    if (profile.employment_type) {
      const employmentType = profile.employment_type.toLowerCase().replace(/[-_]/g, ' ');
      const matchingOption = [...$('#job-employment-type').options].find(
        (option) => option.textContent.toLowerCase() === employmentType,
      );
      if (matchingOption) $('#job-employment-type').value = matchingOption.value;
    }

    const result = $('#job-analysis-result');
    result.innerHTML = renderJobAnalysis(profile);
    result.hidden = false;
    toast('Job details extracted. Review the job form before saving.');
  } finally {
    button.disabled = false;
    button.innerHTML = previousLabel;
  }
}

async function createJob(event) {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  values.minimum_experience_years = values.minimum_experience_years === ''
    ? null
    : Number(values.minimum_experience_years);
  await api('/jobs', { method: 'POST', body: JSON.stringify(values) });
  toast('Job created.');
  await setPage('jobs');
}

async function deleteJob(jobId) {
  if (!window.confirm('Delete this job and its matches and submissions?')) return;
  await api(`/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
  toast('Job deleted.');
  await setPage('jobs');
}

async function runMatch() {
  const jobId = selectedMatchJobId;
  if (jobId == null) return;
  matchingIsLoading = true;
  renderMatchingScreen();
  try {
    matchingResults = await api('/matches/run', {
      method: 'POST',
      body: JSON.stringify({ job_id: jobId }),
    });
  } finally {
    matchingIsLoading = false;
    renderMatchingScreen();
  }
}

function jobWorkMode(location) {
  const normalized = (location || '').toLowerCase();
  if (normalized.includes('remote')) return 'Remote';
  if (normalized.includes('hybrid')) return 'Hybrid';
  return location ? 'On-site (in office)' : 'Not specified';
}

function renderMatchJob(job) {
  const selected = String(job.id) === String(selectedMatchJobId);
  return `
    <article class="match-job-card ${selected ? 'selected' : ''}">
      <div class="match-job-heading">
        <div><h3>${escapeHtml(job.title)}</h3><p>${escapeHtml(job.company)}</p></div>
        ${selected ? '<span class="badge blue">Selected</span>' : ''}
      </div>
      <div class="match-job-details">
        <span><strong>Work mode</strong>${escapeHtml(jobWorkMode(job.location))}</span>
        <span><strong>Location</strong>${escapeHtml(job.location || 'Not specified')}</span>
        <span><strong>Employment</strong>${escapeHtml(job.employment_type || 'Not specified')}</span>
      </div>
      <button class="btn primary match-job-run" type="button" data-job-id="${escapeHtml(job.id)}">
        ${selected && matchingResults.length ? 'Refresh matches' : 'View matches'}
      </button>
    </article>`;
}

function matchTabRows() {
  const shortlisted = matchingResults.filter((match) => match.shortlisted);
  const topMatches = matchingResults.filter((match) => match.decision === 'REVIEW');
  const notMatches = matchingResults.filter((match) => (
    match.score != null && match.decision !== 'REVIEW'
  ));
  return {
    all: matchingResults,
    top: topMatches,
    shortlisted,
    not: notMatches,
  };
}

function renderMatchCandidate(match) {
  const candidate = match.candidate || {};
  const experience = candidate.years_experience == null
    ? 'Experience not specified'
    : `${escapeHtml(candidate.years_experience)} years experience`;
  const score = match.score == null ? 'No score' : `${escapeHtml(match.score)}%`;
  const decision = match.decision || 'Not assessed';
  return `
    <article class="match-candidate-card">
      <div class="match-candidate-heading">
        <div class="match-candidate-identity">
          <span class="candidate-avatar">${escapeHtml((candidate.name || '?').trim().slice(0, 1).toUpperCase())}</span>
          <div><h3>${escapeHtml(candidate.name || 'Unknown candidate')}</h3>
            <p>${escapeHtml(candidate.current_role || candidate.email || 'Role not specified')}</p></div>
        </div>
        <div class="match-score-block">
          <strong>${score}</strong><span>match score</span>
        </div>
      </div>
      <div class="match-candidate-meta">
        <span>${escapeHtml(candidate.location || 'Location not specified')}</span>
        <span>${experience}</span>
        <span class="badge ${decision === 'REVIEW' ? 'blue' : 'amber'}">${escapeHtml(decision.replaceAll('_', ' '))}</span>
      </div>
      ${match.explanation ? `<p class="match-explanation">${escapeHtml(match.explanation)}</p>` : ''}
      <div class="match-skills">
        <div><strong>Matched skills</strong><span>${escapeHtml(match.matched_skills || 'None identified')}</span></div>
        <div><strong>Skills to develop</strong><span>${escapeHtml(match.missing_skills || 'None identified')}</span></div>
      </div>
      <div class="match-candidate-footer">
        <span>Experience requirement: ${match.experience_pass == null ? 'Not specified' : match.experience_pass ? 'Met' : 'Not met'}</span>
        <button class="btn shortlist" type="button" data-id="${escapeHtml(match.id)}">
          ${match.shortlisted ? 'Remove shortlist' : 'Shortlist'}
        </button>
      </div>
    </article>`;
}

function renderMatchingScreen() {
  const selectedJob = jobs.find((job) => String(job.id) === String(selectedMatchJobId));
  const tabs = matchTabRows();
  const activeMatches = tabs[activeMatchTab] || tabs.all;
  const tabDefinitions = [
    ['all', 'All candidates'],
    ['top', 'Top matches'],
    ['shortlisted', 'Shortlisted'],
    ['not', 'Not a match'],
  ];

  content.innerHTML = `
    <section class="card match-jobs-section">
      <div class="card-head"><div><h2>Jobs</h2><span class="card-sub">Select a job to review candidate match scores</span></div>
        <span class="card-badge">${jobs.length} jobs</span>
      </div>
      ${jobs.length
        ? `<div class="match-job-list">${jobs.map(renderMatchJob).join('')}</div>`
        : '<div class="empty">No jobs yet. Add a job under Jobs to start matching.</div>'}
    </section>
    ${selectedJob ? `
      <section class="card match-results-section">
        <div class="match-results-heading">
          <div><span class="candidate-eyebrow">MATCH RESULTS FOR</span>
            <h2>${escapeHtml(selectedJob.title)}</h2><p>${escapeHtml(selectedJob.company)}</p>
          </div>
          <div class="match-selected-job-meta">
            <span class="badge blue">${escapeHtml(jobWorkMode(selectedJob.location))}</span>
            <span class="badge">${escapeHtml(selectedJob.employment_type || 'Employment type not specified')}</span>
            <span class="muted">${escapeHtml(selectedJob.location || 'Location not specified')}</span>
          </div>
        </div>
        <div class="match-tabs" role="tablist" aria-label="Filter candidate matches">
          ${tabDefinitions.map(([id, label]) => `
            <button type="button" role="tab" class="match-tab ${activeMatchTab === id ? 'active' : ''}"
              aria-selected="${activeMatchTab === id}" data-tab="${id}">
              ${label}<span>${tabs[id].length}</span>
            </button>`).join('')}
        </div>
        ${matchingIsLoading
          ? '<div class="empty">Calculating candidate matches…</div>'
          : activeMatches.length
            ? `<div class="match-candidate-list">${activeMatches.map(renderMatchCandidate).join('')}</div>`
            : `<div class="empty">${matchingResults.length
              ? `No candidates in ${escapeHtml(tabDefinitions.find(([id]) => id === activeMatchTab)[1].toLowerCase())}.`
              : 'No candidates yet. Add candidates under Candidates to generate matches.'}</div>`}
      </section>` : ''}
  `;

  content.querySelectorAll('.match-job-run').forEach((button) => {
    button.addEventListener('click', handleAction(async () => {
      const newJobId = button.dataset.jobId;
      if (String(newJobId) !== String(selectedMatchJobId)) {
        selectedMatchJobId = newJobId;
        matchingResults = [];
        activeMatchTab = 'all';
      }
      await runMatch();
    }));
  });
  content.querySelectorAll('.match-tab').forEach((button) => {
    button.addEventListener('click', () => {
      activeMatchTab = button.dataset.tab;
      renderMatchingScreen();
    });
  });
  content.querySelectorAll('.shortlist').forEach((button) => {
    button.addEventListener('click', handleAction(
      () => toggleShortlist(button.dataset.id, selectedMatchJobId),
    ));
  });
}

async function toggleShortlist(matchId, jobId) {
  await api(`/matches/${encodeURIComponent(matchId)}/shortlist`, { method: 'PATCH' });
  await runMatchFor(jobId);
}

async function runMatchFor(jobId) {
  selectedMatchJobId = jobId;
  await runMatch();
}

async function createCandidate(event) {
  event.preventDefault();
  const form = event.currentTarget || document.querySelector('#candidate-form');
  if (!form) {
    throw new Error('Candidate form is unavailable.');
  }
  const values = Object.fromEntries(new FormData(form));
  values.years_experience = Number(values.years_experience);
  await api('/candidates', { method: 'POST', body: JSON.stringify(values) });
  toast('Candidate saved.');
  candidateQuery = '';
  await setPage('candidates');
}

let analyzedResume = null;
let resumeFile = null;

async function analyzeResume(event) {
  event.preventDefault();
  const file = $('#resume-file').files[0];
  if (!file) throw new Error('Choose a PDF or DOCX resume to upload.');

  analyzedResume = null;
  resumeFile = null;
  $('#resume-candidate-form').hidden = true;
  $('#resume-candidate-form').classList.remove('visible');
  const button = event.currentTarget.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const upload = new FormData();
    upload.append('file', file);
    analyzedResume = await request('/api/resumes/analyze', { method: 'POST', body: upload });
    resumeFile = file;
    const profile = analyzedResume;
    const linkedCandidate = profile.duplicate
      ? (await api('/candidates')).find((candidate) => candidate.resume_candidate_id === profile.candidate_id)
      : null;
    $('#resume-candidate-name').value = profile.candidate_name || '';
    $('#resume-candidate-email').value = profile.email || '';
    $('#resume-candidate-location').value = profile.location || '';
    $('#resume-candidate-skills').value = (profile.technical_skills || [])
      .map((skill) => typeof skill === 'string' ? skill : skill.name)
      .filter(Boolean)
      .join(', ');
    $('#resume-candidate-role').value = profile.current_role || '';
    $('#resume-candidate-years').value = profile.total_experience_years ?? '';
    $('#resume-candidate-authorization').value = profile.work_authorization || '';
    $('#resume-candidate-notes').value = '';
    $('#resume-analysis-result').innerHTML = `
      <div class="analysis-result-heading">
        <span class="analysis-success-icon" aria-hidden="true">${profile.duplicate ? '!' : '✓'}</span>
        <div><strong>${profile.duplicate ? 'Duplicate resume detected' : 'Resume analyzed'}</strong><small>${escapeHtml(profile.file_name || file.name)}${profile.duplicate ? ' · This resume was uploaded previously.' : ` · ${profile.technical_skills.length} skills detected`}</small></div>
      </div>
      ${profile.duplicate && linkedCandidate
        ? `<p>This resume is already linked to ${escapeHtml(linkedCandidate.name)}.</p><button id="open-duplicate-candidate" class="btn" type="button">View existing candidate</button>`
        : profile.duplicate
          ? '<p>This resume is already stored. You can link it to a candidate without uploading another copy.</p>'
          : profile.professional_summary ? `<p>${escapeHtml(profile.professional_summary)}</p>` : ''}`;
    $('#resume-analysis-result').hidden = false;
    $('#resume-candidate-form').hidden = Boolean(linkedCandidate);
    $('#resume-candidate-form').classList.toggle('visible', !linkedCandidate);
    if (linkedCandidate) {
      analyzedResume = null;
      resumeFile = null;
      $('#open-duplicate-candidate').addEventListener('click', handleAction(async () => {
        await showCandidateProfile(linkedCandidate.id);
      }));
      toast('This resume is already linked to a candidate.');
    } else {
      toast(profile.duplicate
        ? 'Duplicate resume detected. The existing resume will be reused.'
        : 'Resume analyzed. Review the candidate details, then save the candidate.');
      $('#resume-candidate-name').focus();
    }
  } finally {
    button.disabled = false;
  }
}

async function saveResumeCandidate(event) {
  event.preventDefault();
  if (!analyzedResume || !resumeFile) {
    throw new Error('Analyze a resume before saving the candidate.');
  }

  const form = event.currentTarget || document.querySelector('#resume-candidate-form');
  if (!form) {
    throw new Error('Resume candidate form is unavailable.');
  }

  const values = Object.fromEntries(new FormData(form));
  values.name = String(values.name || '').trim();
  values.email = String(values.email || '').trim();
  if (!values.name || !values.email) {
    throw new Error('Candidate name and email are required.');
  }
  const normalizedEmail = values.email.toLowerCase();
  const exactMatches = await api(`/candidates?q=${encodeURIComponent(values.email)}`);
  if (exactMatches.some((candidate) => {
    const existingEmail = typeof candidate.email === 'string' ? candidate.email.trim().toLowerCase() : '';
    return existingEmail && existingEmail === normalizedEmail;
  })) {
    throw new Error('A candidate with this email already exists.');
  }
  values.years_experience = values.years_experience === '' ? 0 : Number(values.years_experience);
  const resumeProfile = {
    ...analyzedResume,
    candidate_name: values.name,
    email: values.email,
    location: values.location,
    total_experience_years: values.years_experience || null,
    current_role: values.current_role,
    technical_skills: analyzedResume.technical_skills || [],
    roles: analyzedResume.roles || [],
    education: analyzedResume.education || [],
    certifications: analyzedResume.certifications || [],
    domains: analyzedResume.domains || [],
    professional_summary: analyzedResume.professional_summary || '',
    work_authorization: values.work_authorization || '',
  };
  const resumeData = new FormData();
  resumeData.append('profile', JSON.stringify(resumeProfile));
  resumeData.append('file', resumeFile);
  const button = form.querySelector('button[type="submit"]');
  if (button) button.disabled = true;
  try {
    const savedResume = await request('/api/resumes/save', { method: 'POST', body: resumeData });
    if (savedResume.duplicate) {
      const existingCandidate = (await api('/candidates')).find(
        (candidate) => candidate.resume_candidate_id === savedResume.candidate_id,
      );
      if (existingCandidate) {
        analyzedResume = null;
        resumeFile = null;
        toast('This resume is already linked to a candidate.');
        await setPage('candidates');
        await showCandidateProfile(existingCandidate.id);
        return;
      }
    }
    const candidate = await api('/candidates', {
      method: 'POST',
      body: JSON.stringify({
        ...values,
        resume_candidate_id: savedResume.candidate_id,
        profile: resumeProfile,
      }),
    });
    analyzedResume = null;
    resumeFile = null;
    candidateQuery = '';
    toast('Resume uploaded and candidate profile saved.');
    await setPage('candidates');
    await showCandidateProfile(candidate.id);
  } finally {
    if (button) button.disabled = false;
  }
}

async function createSubmission(event) {
  event.preventDefault();
  if (!submissionWizard.match || !submissionWizard.consentShare || !submissionWizard.consentContact) {
    throw new Error('Calculate the match and record both candidate consents before submitting.');
  }
  const form = event.currentTarget || $('#submission-form');
  if (!form) throw new Error('Submission form is unavailable.');
  const values = Object.fromEntries(new FormData(form));
  submissionWizard.vendor = String(values.vendor || '').trim();
  submissionWizard.notes = String(values.notes || '').trim();
  values.job_id = Number(submissionWizard.jobId);
  values.candidate_id = Number(submissionWizard.candidateId);
  values.vendor = submissionWizard.vendor;
  values.notes = submissionWizard.notes;
  values.consent_share = submissionWizard.consentShare;
  values.consent_contact = submissionWizard.consentContact;
  if (!values.vendor) throw new Error('Enter the employer or vendor receiving this submission.');

  submissionWizard.saving = true;
  const button = form.querySelector('button[type="submit"]');
  if (button) button.disabled = true;
  try {
    await api('/submissions', { method: 'POST', body: JSON.stringify(values) });
    submissionWizard.step = 4;
    const submissions = await api('/submissions');
    renderSubmissionWorkflow(submissions);
    bindSubmissionWorkflow(submissions);
    toast('Candidate submitted and added to tracking.');
  } finally {
    submissionWizard.saving = false;
    if (button) button.disabled = false;
  }
}

async function updateStatus(select) {
  const id = encodeURIComponent(select.dataset.id);
  const status = select.value;
  select.disabled = true;
  try {
    await api(`/submissions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    toast('Status updated.');
  } catch (error) {
    toast(error.message);
    await setPage('submissions');
  } finally {
    select.disabled = false;
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  values.match_threshold = Number(values.match_threshold);
  await api('/settings', { method: 'PUT', body: JSON.stringify(values) });
  toast('Settings saved.');
}

async function toggleIntegration(button) {
  await api('/integrations', {
    method: 'PUT',
    body: JSON.stringify({
      provider: button.dataset.provider,
      enabled: button.dataset.enabled === 'true',
      config_json: '{}',
    }),
  });
  toast('Integration updated.');
  await setPage('settings');
}

document.querySelectorAll('.nav-item').forEach((button) => {
  button.addEventListener('click', () => setPage(button.dataset.page));
});
$('#menu-btn').addEventListener('click', () => $('.sidebar').classList.toggle('open'));
$('#sign-out').addEventListener('click', handleAction(async () => {
  const response = await fetch('/api/auth/logout', { method: 'POST' });
  if (!response.ok) {
    toast('Could not sign out. Please try again.');
    return;
  }
  window.location.assign('/login');
}));

const requestedPage = new URLSearchParams(window.location.search).get('page');
setPage(Object.prototype.hasOwnProperty.call(pageTitles, requestedPage) ? requestedPage : 'dashboard');

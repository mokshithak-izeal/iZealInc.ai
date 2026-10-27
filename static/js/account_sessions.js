(function () {
  const list = document.getElementById('sessionList');
  const message = document.getElementById('msg');
  const revokeOthers = document.getElementById('revokeOthers');

  function flash(text, kind) {
    message.textContent = text;
    message.className = 'msg ' + kind;
    message.hidden = false;
  }

  function date(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Unknown' : parsed.toLocaleString();
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async function api(url, options) {
    const response = await fetch(url, options);
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
      location.href = '/login';
      throw new Error('Please sign in again.');
    }
    if (!response.ok) throw new Error(data.detail || 'The request failed.');
    return data;
  }

  function render(sessions) {
    list.replaceChildren();
    revokeOthers.disabled = sessions.length < 2;
    if (!sessions.length) {
      list.appendChild(element('p', 'No active sessions were found.', 'sub'));
      return;
    }

    sessions.forEach(session => {
      const card = element('article', '', 'session-card');
      const details = document.createElement('div');
      details.appendChild(element('h2', session.user_agent || 'Unknown device'));
      details.appendChild(element('p', 'IP address: ' + (session.ip_address || 'Unavailable')));
      details.appendChild(element('p', 'Last active: ' + date(session.last_seen_at)));
      details.appendChild(element('p', 'Signed in: ' + date(session.created_at)));
      details.appendChild(element('p', 'Expires: ' + date(session.expires_at)));

      const actions = element('div', '', 'session-actions');
      if (session.is_current) {
        actions.appendChild(element('span', 'This device', 'current-chip'));
      }
      const button = element('button', session.is_current ? 'Sign out' : 'Revoke', 'danger-btn');
      button.type = 'button';
      button.addEventListener('click', async () => {
        if (!window.confirm(session.is_current ? 'Sign out this device?' : 'Revoke this session?')) return;
        button.disabled = true;
        try {
          const result = await api('/api/auth/sessions/' + encodeURIComponent(session.id), { method: 'DELETE' });
          if (result.current) {
            location.href = '/login';
            return;
          }
          flash('Session revoked.', 'success');
          await load();
        } catch (error) {
          flash(error.message, 'error');
          button.disabled = false;
        }
      });
      actions.appendChild(button);
      card.append(details, actions);
      list.appendChild(card);
    });
  }

  async function load() {
    try {
      const result = await api('/api/auth/sessions');
      render(result.sessions);
    } catch (error) {
      flash(error.message, 'error');
    }
  }

  revokeOthers.addEventListener('click', async () => {
    if (!window.confirm('Sign out all other devices?')) return;
    revokeOthers.disabled = true;
    try {
      const result = await api('/api/auth/sessions/revoke-others', { method: 'POST' });
      flash(result.revoked + ' other session(s) signed out.', 'success');
      await load();
    } catch (error) {
      flash(error.message, 'error');
      revokeOthers.disabled = false;
    }
  });

  load();
})();

(function () {
  const rows = document.getElementById('rows');
  const summary = document.getElementById('summary');
  const msg = document.getElementById('msg');
  let me = null;

  function flash(text, kind) {
    msg.textContent = text;
    msg.className = 'msg ' + kind;
    msg.hidden = false;
  }

  async function api(url, options) {
    const response = await fetch(url, options);
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) { location.href = '/login'; throw new Error('Please sign in.'); }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed.');
    return data;
  }

  async function act(path, payload) {
    try {
      await api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload ? JSON.stringify(payload) : undefined
      });
      await load();
      flash('Saved.', 'success');
    } catch (error) {
      flash(error.message, 'error');
      await load();
    }
  }

  function cell(text) {
    const td = document.createElement('td');
    td.textContent = text;
    return td;
  }

  function render(users) {
    rows.replaceChildren();
    users.sort((a, b) => (a.is_active - b.is_active) || a.name.localeCompare(b.name));
    const disabled = users.filter(u => !u.is_active).length;
    summary.textContent = disabled
      ? disabled + (disabled === 1 ? ' account is' : ' accounts are') + ' disabled. Enable them below.'
      : 'Everyone listed here can sign in.';

    if (!users.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 6;
      td.className = 'empty';
      td.textContent = 'No users yet.';
      tr.appendChild(td);
      rows.appendChild(tr);
      return;
    }

    users.forEach(u => {
      const isMe = me && u.id === me.id;
      const tr = document.createElement('tr');
      tr.appendChild(cell(u.name + (isMe ? ' (you)' : '')));
      tr.appendChild(cell(u.email));

      const roleTd = document.createElement('td');
      if (isMe) {
        roleTd.textContent = 'Admin';
      } else {
        const select = document.createElement('select');
        select.setAttribute('aria-label', 'Role for ' + u.name);
        [['recruiter', 'Recruiter'], ['admin', 'Admin']].forEach(([value, label]) => {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = label;
          option.selected = u.role === value;
          select.appendChild(option);
        });
        select.addEventListener('change', () => act('/api/users/' + u.id + '/role', { role: select.value }));
        roleTd.appendChild(select);
      }
      tr.appendChild(roleTd);

      tr.appendChild(cell(new Date(u.created_at).toLocaleDateString()));

      const statusTd = document.createElement('td');
      const chip = document.createElement('span');
      chip.className = 'chip ' + (u.is_active ? 'active' : 'inactive');
      chip.textContent = u.is_active ? 'Active' : 'Not active';
      statusTd.appendChild(chip);
      tr.appendChild(statusTd);

      const actionTd = document.createElement('td');
      if (!u.is_active) {
        const enable = document.createElement('button');
        enable.className = 'small-btn primary';
        enable.textContent = 'Enable';
        enable.addEventListener('click', () => act('/api/users/' + u.id + '/enable'));
        actionTd.appendChild(enable);
      } else if (!isMe) {
        const disable = document.createElement('button');
        disable.className = 'small-btn';
        disable.textContent = 'Disable';
        disable.addEventListener('click', () => {
          if (confirm('Disable ' + u.name + "? They won't be able to sign in.")) act('/api/users/' + u.id + '/disable');
        });
        actionTd.appendChild(disable);
      }
      tr.appendChild(actionTd);
      rows.appendChild(tr);
    });
  }

  async function load() {
    try {
      const [who, users] = await Promise.all([api('/api/auth/me'), api('/api/users')]);
      me = who;
      render(users);
    } catch (error) {
      flash(error.message, 'error');
    }
  }

  load();
})();

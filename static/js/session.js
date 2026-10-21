// Adds the signed-in user, a Sign out button and (for admins) a Manage users link
// to the sidebar, and sends people to the sign-in page when their session ends.
(function () {
  const realFetch = window.fetch.bind(window);
  window.fetch = async function () {
    const response = await realFetch.apply(null, arguments);
    if (response.status === 401) location.href = '/login';
    return response;
  };

  const style = document.createElement('style');
  style.textContent =
    '.account{margin-top:32px;padding-top:16px;border-top:1px solid #1f2937;font-size:13px}' +
    '.account strong{display:block;color:#fff;font-size:14px;overflow-wrap:anywhere}' +
    '.account span{display:block;color:#9ca3af;margin-bottom:12px;overflow-wrap:anywhere}' +
    '.account a,.account button{display:block;width:calc(100% + 20px);text-align:left;padding:9px 10px;margin:4px -10px 0;border:0;border-radius:8px;background:transparent;color:#d1d5db;font:inherit;cursor:pointer;text-decoration:none}' +
    '.account a:hover,.account button:hover{background:#1f2937;color:#fff}';
  document.head.appendChild(style);

  function mount(user) {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    const box = document.createElement('div');
    box.className = 'account';
    const name = document.createElement('strong');
    name.textContent = user.name || user.email;
    const email = document.createElement('span');
    email.textContent = user.email;
    box.append(name, email);
    if (user.role === 'admin') {
      const link = document.createElement('a');
      link.href = '/admin/users';
      link.textContent = 'Manage users';
      box.appendChild(link);
    }
    const out = document.createElement('button');
    out.type = 'button';
    out.textContent = 'Sign out';
    out.addEventListener('click', async () => {
      await realFetch('/api/auth/logout', { method: 'POST' });
      location.href = '/login';
    });
    box.appendChild(out);
    sidebar.appendChild(box);
  }

  realFetch('/api/auth/me')
    .then(r => (r.ok ? r.json() : null))
    .then(user => {
      if (!user) { location.href = '/login'; return; }
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount(user));
      else mount(user);
    })
    .catch(() => {});
})();

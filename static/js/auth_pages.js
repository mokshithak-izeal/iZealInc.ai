(function () {
  const form = document.getElementById('form');
  const msg = document.getElementById('msg');
  const submit = document.getElementById('submit');
  const mode = form.dataset.mode;
  const val = id => (document.getElementById(id) || {}).value || '';

  function show(text, kind) {
    msg.textContent = text;
    msg.className = 'msg ' + (kind || 'error');
    msg.hidden = false;
  }

  document.querySelectorAll('.pw-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const input = toggle.previousElementSibling;
      const revealing = input.type === 'password';
      input.type = revealing ? 'text' : 'password';
      toggle.textContent = revealing ? 'Hide' : 'Show';
      toggle.setAttribute('aria-pressed', String(revealing));
      toggle.setAttribute('aria-label', revealing ? 'Hide password' : 'Show password');
    });
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    msg.hidden = true;
    let url, body;
    if (mode === 'login') {
      if (!val('email').trim() || !val('password')) return show('Enter your email and password.');
      url = '/api/auth/login';
      body = { email: val('email'), password: val('password') };
    } else {
      if (!val('name').trim()) return show('Enter your full name.');
      if (!val('email').trim()) return show('Enter your work email.');
      if (val('password').length < 10) return show('Use at least 10 characters for your password.');
      if (val('password') !== val('confirm')) return show('The two passwords do not match.');
      url = '/api/auth/signup';
      body = { name: val('name'), email: val('email'), password: val('password') };
    }

    const label = submit.textContent;
    submit.disabled = true;
    submit.textContent = mode === 'login' ? 'Signing in...' : 'Creating account...';
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if (!response.ok) {
        show(typeof data.detail === 'string' ? data.detail : 'Something went wrong. Try again.');
        return;
      }
      if (mode === 'login') {
        location.href = '/';
        return;
      }
      const heading = document.createElement('h1');
      heading.textContent = 'Account created';
      const text = document.createElement('p');
      text.className = 'sub';
      text.textContent = data.message;
      const link = document.createElement('a');
      link.className = 'btn';
      link.href = '/login';
      link.textContent = 'Go to sign in';
      form.replaceChildren(heading, text, link);
    } catch (_) {
      show('Could not reach the server. Check your connection and try again.');
    } finally {
      submit.disabled = false;
      submit.textContent = label;
    }
  });
})();

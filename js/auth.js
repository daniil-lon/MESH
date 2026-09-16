const Auth = {
  submitLogin(event) {
    event.preventDefault();

    const login = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    const btn = document.getElementById('btn-login-submit');

    if (!login || !password) {
      if (errorEl) errorEl.textContent = 'Введите логин и пароль';
      return false;
    }

    if (errorEl) errorEl.textContent = '';
    if (btn) btn.disabled = true;

    API.login(login, password)
      .then(data => {
        if (data && data.access_token) {
          localStorage.setItem('mesh_token', data.access_token);
          localStorage.setItem('mesh_user', JSON.stringify({
            name: data.name,
            group: data.group,
            role: data.role || 'student'
          }));
          App.showMain();
          App.loadProfile();
          App.loadPrefs();
          App.saveAccount();
        } else {
          if (errorEl) errorEl.textContent = 'Неверный логин или пароль';
        }
      })
      .catch(err => {
        if (errorEl) {
          const msg = err && err.message ? err.message : '';
          if (/fetched|NetworkError|load failed/i.test(msg) || (err && err.name === 'TypeError')) {
            errorEl.textContent = 'Нет связи с сервером. Откройте приложение по адресу http://127.0.0.1:8000 (не открывайте index.html напрямую).';
          } else {
            errorEl.textContent = msg || 'Неверный логин или пароль';
          }
        }
      })
      .finally(() => {
        if (btn) btn.disabled = false;
      });

    return false;
  },

  logout() {
    localStorage.removeItem('mesh_token');
    localStorage.removeItem('mesh_demo');
    localStorage.removeItem('mesh_user');
    App.showLogin();
  },

  getToken() {
    return localStorage.getItem('mesh_token');
  },

  isDemo() {
    return localStorage.getItem('mesh_demo') === 'true';
  },

  isAuthenticated() {
    return !!this.getToken();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  const share = params.get('share');
  if (share) {
    API.getShare(share).then(res => {
      window.history.replaceState({}, '', window.location.pathname);
      App.showLogin();
      if (res && res.ok && res.data) {
        document.getElementById('login-error').textContent = '';
        App.openShareReport(res.data);
      } else {
        const details = res && res.data && res.data.detail;
        document.getElementById('login-error').textContent = details || 'Ссылка недействительна или истекла';
      }
    });
    return;
  }
  if (token) {
    localStorage.setItem('mesh_token', token);
    window.history.replaceState({}, '', window.location.pathname);
    App.showMain();
    App.loadProfile();
  }
});
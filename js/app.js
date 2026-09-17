const App = {
  currentScreen: 'login',
  currentDay: null,
  currentStream: null,
  currentMode: 'week',
  pushEnabled: false,

  init() {
    if (window.addEventListener) {
      window.addEventListener('error', e => API.logError(e.message, e.error && e.error.stack));
      window.addEventListener('unhandledrejection', e => API.logError(e.reason && e.reason.message, e.reason && e.reason.stack));
    }
    this.registerSW();
    this.setInitialDay();
    this.attachSwipe();
    this.setupOffline();
    this.setupPullToRefresh();
    this.trackStreak();
    this.applyTheme();
    this.startThemeAuto();
    this.updateNotifUI();
    this.startReminders();
    this.startDigest();
    this.makePinPad();
    this.setupInstall();
    this.checkAuth();
    this.setupSearch();
    window.addEventListener('click', e => {
      const t = e.target.closest && e.target.closest('button, .nav-item, .quick-item');
      if (t && 'vibrate' in navigator && navigator.vibrate) navigator.vibrate(10);
      const sw = e.target.closest && e.target.closest('.accent-swatch');
      if (sw) this.setAccent(sw.dataset.accent);
    });
    this.autoRefreshSession();
    setInterval(() => this.autoRefreshSession(), 15 * 60 * 1000);
  },

  setupSearch() {
    if (!window.addEventListener) return;
    window.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && String(e.key).toLowerCase() === 'k') {
        e.preventDefault();
        this.showSearch();
      }
      if (e.key === 'Escape') this.hideSearch();
    });
    const input = document.getElementById('search-input');
    if (input) {
      input.addEventListener('input', () => this.doSearch());
    }
  },

  showSearch() {
    const overlay = document.getElementById('search-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    const input = document.getElementById('search-input');
    if (input) {
      input.value = '';
      input.focus();
    }
    const results = document.getElementById('search-results');
    if (results) results.innerHTML = '<div class="sub-note">Введите запрос — например, «информатика», «долги», «неделя»…</div>';
  },

  hideSearch() {
    const overlay = document.getElementById('search-overlay');
    if (overlay) overlay.style.display = 'none';
  },

  doSearch() {
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');
    if (!input || !results) return;
    const q = input.value.trim().toLowerCase();
    if (q.length < 2) {
      results.innerHTML = '<div class="sub-note">Введите минимум 2 символа</div>';
      return;
    }
    Promise.all([API.getNews(), API.getMaterials(), API.getClubs(), API.getFaq(), API.getGrades(), API.getMyDebts(), API.getWeekSchedule(this.currentStream || 'alfa', this.getGroup())])
      .then(([news, mat, clubs, faq, grades, debts, week]) => {
        const out = [];
        const push = (icon, title, sub, action) => out.push(`<button class="search-hit" onclick="${action}">${icon}<span><b>${title}</b>${sub ? '<em>' + sub + '</em>' : ''}</span></button>`);

        const dayNames = { mon: 'Пн', tue: 'Вт', wed: 'Ср', thu: 'Чт', fri: 'Пт', sat: 'Сб' };
        const seenLessons = {};
        const seenTeachers = {};
        (week || []).forEach(({ day, lessons }) => {
          (lessons || []).forEach(l => {
            if (!l.subject || l.subject === 'Окно') return;
            const lk = day + '|' + l.subject + '|' + l.pair;
            if (!seenLessons[lk] && ((l.subject || '').toLowerCase().includes(q) || (l.room || '').toLowerCase().includes(q))) {
              seenLessons[lk] = 1;
              push('🗓', `${dayNames[day]} · ${l.subject}`, `${l.time_start} · ${l.room || ''}${l.teacher ? ' · ' + l.teacher : ''}`, `App.navigateTo('schedule')`);
            }
            const t = (l.teacher || '').trim();
            if (t && t.toLowerCase().includes(q) && !seenTeachers[t]) {
              seenTeachers[t] = 1;
              push('👩‍🏫', t, `преподаватель · ${l.subject}`, `App.navigateTo('schedule')`);
            }
          });
        });

        (news || []).filter(n => n && (n.title || '').toLowerCase().includes(q) || (n.body || '').toLowerCase().includes(q))
          .slice(0, 6).forEach(n => push('📰', n.title, n.date || '', `App.navigateTo('news')`));

        (mat && mat.materials || []).forEach(m => {
          (m.materials || []).filter(x => (x.title || '').toLowerCase().includes(q))
            .forEach(x => push('📚', `${m.subject} — ${x.title}`, x.type || '', `App.navigateTo('materials')`));
          (m.terms || []).filter(t => (t.term || '').toLowerCase().includes(q))
            .forEach(t => push('💡', t.term, t.def || '', `App.navigateTo('materials')`));
        });

        (clubs && clubs.clubs || []).filter(c => (c.name || '').toLowerCase().includes(q))
          .forEach(c => push('🏀', c.name, c.schedule || '', `App.navigateTo('extern')`));

        (faq && faq.faq || []).filter(f => (f.q || '').toLowerCase().includes(q))
          .forEach(f => push('❓', f.q, f.a || '', `navigator.clipboard && navigator.clipboard.writeText('${(f.a || '').replace(/'/g, "\\'")}');App.hideSearch()`));

        (grades && grades.subjects || []).filter(s => (s.name || '').toLowerCase().includes(q))
          .forEach(s => push('⭐', `Оценки: ${s.name}`, `средний ${s.average}`, `App.navigateTo('grades')`));

        (debts && debts.debts || []).filter(d => (d.subject || '').toLowerCase().includes(q))
          .forEach(d => push('🎯', `Долг: ${d.subject}`, `нужно ${d.need} к цели`, `App.navigateTo('today')`));

        const screens = [
          ['🗓', 'Расписание', 'App.navigateTo(\'schedule\')'],
          ['🔄', 'Замены', 'App.navigateTo(\'replacements\')'],
          ['📰', 'Новости', 'App.navigateTo(\'news\')'],
          ['⭐', 'Оценки', 'App.navigateTo(\'grades\')'],
          ['📝', 'Домашки', 'App.navigateTo(\'homework\')'],
          ['🏠', 'Мой день', 'App.navigateTo(\'today\')'],
          ['👤', 'Профиль', 'App.navigateTo(\'profile\')']
        ];
        screens.forEach(([icon, name, nav]) => {
          if (name.toLowerCase().includes(q)) push(icon, name, 'раздел', nav);
        });

        results.innerHTML = out.length
          ? out.join('')
          : '<div class="sub-note">Ничего не найдено</div>';
      });
  },

toggleSova() {
    const panel = document.getElementById('sova-panel');
    if (!panel) return;
    panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
    if (panel.style.display === 'flex') {
      setTimeout(() => document.getElementById('sova-input') && document.getElementById('sova-input').focus(), 120);
    }
  },

  toggleSovaMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const btn = document.getElementById('sova-mic');
    const input = document.getElementById('sova-input');
    if (!SR || !input) {
      alert('Голосовой ввод не поддерживается этим браузером');
      return;
    }
    if (this._sovaRec) {
      this._sovaRec.stop();
      this._sovaRec = null;
      if (btn) btn.classList.remove('recording');
      return;
    }
    const rec = new SR();
    rec.lang = 'ru-RU';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    this._sovaRec = rec;
    if (btn) btn.classList.add('recording');
    rec.onresult = e => {
      const text = e.results[0][0].transcript;
      input.value = text;
      if (btn) btn.classList.remove('recording');
      this._sovaRec = null;
      this.sovaAsk();
    };
    rec.onerror = () => {
      if (btn) btn.classList.remove('recording');
      this._sovaRec = null;
    };
    rec.onend = () => {
      if (btn) btn.classList.remove('recording');
      this._sovaRec = null;
    };
    try { rec.start(); } catch (e) {}
  },

  sovaAsk() {
    const input = document.getElementById('sova-input');
    const box = document.getElementById('sova-messages');
    if (!input || !box) return;
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    box.insertAdjacentHTML('beforeend', `<div class="sova-msg sova-user">${this.esc(q)}</div>`);
    this.sovaReply(q).then(answer => {
      box.insertAdjacentHTML('beforeend', `<div class="sova-msg">${answer}</div>`);
      box.scrollTop = box.scrollHeight;
    });
  },

  sovaReply(q) {
    const text = q.toLowerCase();
    return Promise.all([API.getGrades(), API.getMyDebts(), API.getNews(), API.getHomework(), API.getSchedule('mon', this.currentStream || 'alfa', this.getGroup())])
      .then(([g, debts, news, hw]) => {
        const avg = g && g.average ? g.average : null;
        if (/(долг|долги|ack)/.test(text) || (debts && debts.debts.length)) {
          const d = (debts && debts.debts) || [];
          return d.length
            ? 'У тебя есть долги: ' + d.map(x => `${x.subject} (средний ${x.average}, нужно ещё ${x.need})`).join('; ')
            : 'Долгов нет — молодец! Продолжай в том же духе.';
        }
        if (/(оценк|балл|успева)/.test(text)) {
          return avg !== null
            ? `Средний балл ${avg}. Держи планку! Целые тройки есть только в русском — подтяни до 4.`
            : 'Пока нет оценок. Загляни в раздел «Оценки».';
        }
        if (/(завтра|расписание|пар|пары|неделя)/.test(text)) {
          return 'Открой раздел «Расписание» — там неделя, звонки и замены. Советую заглянуть в «Мой день» для плана на сегодня.';
        }
        if (/(новости|событи)/.test(text)) {
          return (news && news[0]) ? `Свежак: «${news[0].title}» в разделе Новости.` : 'Свежих новостей пока нет.';
        }
        if (/(домашк|дз|задани)/.test(text)) {
          return (hw && hw.length) ? `На сегодня заданий: ${hw.slice(0, 3).map(h => h.subject + ' — ' + h.task).join('; ')}.` : 'Заданий нет. Отдыхай!';
        }
        if (/(столов|меню|еда|поесть)/.test(text)) {
          return 'Меню столовой смотри в «Мой день». Любимые блюда можно добавить звёздочкой.';
        }
        if (/(кружк|секци|спорт)/.test(text)) {
          return 'Кружки и секции — в разделе «Внеучебка».';
        }
        if (/(контакт|телефон|куратор)/.test(text)) {
          return 'Телефон куратора — на вкладке «Профиль».';
        }
        if (/(пин|пароль)/.test(text)) {
          return 'Пин-код и смену пароля меняй в «Настройки» в Профиле.';
        }
        if (/(справка|документ)/.test(text)) {
          return 'Справку об обучении и отчёт сформируй в «Профиль» → «Справка/Отчёт».';
        }
        if (/(привет|здравств|сова|угу|ок)/.test(text)) {
          return 'Привет! Я Сова 🦉. Спроси про оценки, долги, расписание или кружки.';
        }
        return 'Интересно. Попробуй спросить: «мои долги», «что по оценкам», «что завтра», «где кружки».';
      });
  },

  esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  },

  speak(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(String(text || ''));
    u.lang = 'ru-RU';
    u.rate = 1.0;
    window.speechSynthesis.speak(u);
  },

  haptic(pattern) {
    try {
      if ('vibrate' in navigator && navigator.vibrate) navigator.vibrate(pattern || 12);
    } catch (e) {}
  },

  startThemeAuto() {
    setInterval(() => {
      if (localStorage.getItem('mesh_theme') === 'auto') this.applyTheme();
    }, 30000);
  },

  applyTheme() {
    const themes = { light: 'Светлая', dark: 'Тёмная', blue: 'Синяя', auto: 'Авто' };
    let cur = localStorage.getItem('mesh_theme') || 'light';
    if (cur === 'auto') {
      const h = new Date().getHours();
      cur = (h >= 19 || h < 7) ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', cur);
    document.documentElement.setAttribute('data-theme-choice', localStorage.getItem('mesh_theme') || 'light');
    const accent = localStorage.getItem('mesh_accent') || 'indigo';
    document.documentElement.setAttribute('data-accent', accent);
    document.querySelectorAll('.accent-swatch').forEach(sw => {
      sw.classList.toggle('active', sw.dataset.accent === accent);
    });
    const el = document.getElementById('theme-text');
    if (el) el.textContent = themes[localStorage.getItem('mesh_theme') || 'light'] || 'Светлая';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      const colors = {
        indigo: '#4f46e5', blue: '#2563eb', emerald: '#10b981',
        amber: '#f59e0b', rose: '#f43f5e', violet: '#7c3aed'
      };
      meta.setAttribute('content', colors[accent] || '#4f46e5');
    }
  },

  setAccent(color) {
    localStorage.setItem('mesh_accent', color);
    this.applyTheme();
    this.haptic(8);
    this.markPrefsChanged();
  },

  cycleTheme() {
    const order = ['light', 'dark', 'blue', 'auto'];
    const cur = localStorage.getItem('mesh_theme') || 'light';
    const next = order[(order.indexOf(cur) + 1) % order.length];
    localStorage.setItem('mesh_theme', next);
    this.applyTheme();
    this.markPrefsChanged();
  },

  toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const isDark = cur !== 'dark';
    localStorage.setItem('mesh_theme', isDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    const el = document.getElementById('theme-text');
    if (el) el.textContent = isDark ? 'Тёмная' : 'Светлая';
    this.markPrefsChanged();
  },

  registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  },

  getStream() {
    const now = new Date();
    const diffToMonday = (now.getDay() + 6) % 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - diffToMonday);
    monday.setHours(0, 0, 0, 0);

    const anchor = new Date(2026, 8, 14);
    const daysDiff = Math.round((monday - anchor) / 86400000);
    const weeks = Math.floor(daysDiff / 7);
    return weeks % 2 === 0 ? 'alfa' : 'beta';
  },

  setInitialDay() {
    const days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
    const today = days[new Date().getDay()];
    this.currentDay = today;
    this.currentStream = this.getStream();
    this.updateStreamBadge();

    document.querySelectorAll('.schedule-nav-btn').forEach(btn => {
      if (btn.dataset.day === this.currentDay) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.schedule-nav-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.currentDay = e.target.dataset.day;
        this.loadSchedule();
      });
    });

    this.updateDateDisplay();
  },

  updateStreamBadge() {
    const el = document.getElementById('stream-text');
    if (!el) return;
    const isAlfa = this.currentStream === 'alfa';
    const badge = document.getElementById('stream-badge');
    el.textContent = isAlfa ? 'Альфа · Первый поток' : 'Бета · Второй поток';
    if (badge) {
      badge.classList.toggle('stream--alfa', isAlfa);
      badge.classList.toggle('stream--beta', !isAlfa);
    }
  },

  updateDateDisplay() {
    const now = new Date();
    const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    const weekdays = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
    const el = document.getElementById('current-date');
    if (el) {
      el.textContent = `${weekdays[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]}`;
    }
  },

  setupOffline() {
    const update = () => {
      const el = document.getElementById('offline-banner');
      if (el) el.style.display = navigator.onLine ? 'none' : 'flex';
      this.updateOfflinePending();
    };
    window.addEventListener('online', () => { update(); this.flushPrefsOnOnline(); this.flushOfflineQueue(); });
    window.addEventListener('offline', update);
    update();
  },

  updateOfflinePending() {
    const el = document.getElementById('offline-pending');
    if (!el) return;
    const n = API.pendingCount();
    if (n > 0) {
      el.textContent = `${n} ${n === 1 ? 'действие' : (n < 5 ? 'действия' : 'действий')} ждёт отправки`;
      el.style.display = 'inline';
    } else {
      el.style.display = 'none';
    }
  },

  trackStreak() {
    const fmt = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const today = fmt(new Date());
    const yest = fmt(new Date(Date.now() - 86400000));
    const last = localStorage.getItem('mesh_streak_last');
    if (last === today) return;
    const cur = parseInt(localStorage.getItem('mesh_streak') || '0', 10);
    const next = last === yest ? cur + 1 : 1;
    localStorage.setItem('mesh_streak', String(next));
    localStorage.setItem('mesh_streak_last', today);
    if (next > parseInt(localStorage.getItem('mesh_streak_best') || '0', 10)) {
      localStorage.setItem('mesh_streak_best', String(next));
    }
  },

  setupPullToRefresh() {
    const el = document.getElementById('ptr');
    let startY = 0, pulling = false, dist = 0;
    const atTop = () => window.pageYOffset <= 0;
    window.addEventListener('touchstart', e => {
      if (!atTop() || e.touches.length !== 1) return;
      startY = e.touches[0].clientY;
      pulling = true;
      dist = 0;
    }, { passive: true });
    window.addEventListener('touchmove', e => {
      if (!pulling) return;
      dist = Math.max(0, e.touches[0].clientY - startY);
      if (atTop() && el) {
        el.classList.add('visible');
        el.textContent = dist > 70 ? 'Отпустите для обновления' : 'Потяните для обновления';
      }
    }, { passive: true });
    window.addEventListener('touchend', () => {
      if (!pulling) return;
      pulling = false;
      if (el) el.classList.remove('visible');
      if (atTop() && dist >= 70) this.refreshData();
      dist = 0;
    });
  },

  refreshData() {
    const map = {
      schedule: 'loadSchedule',
      replacements: 'loadReplacements',
      news: 'loadNews',
      grades: 'loadGrades',
      homework: 'loadHomework',
      attendance: 'loadAttendance',
      today: 'loadToday',
      portfolio: 'loadPortfolio',
      materials: 'loadMaterials',
      extern: 'loadExtern',
      prep: 'loadPrep',
      teacher: 'loadTeacher',
      curator: 'loadCurator'
    };
    const fn = map[this.currentScreen];
    if (fn && this[fn]) this[fn]();
  },

  autoRefreshSession() {
    if (!Auth.isAuthenticated()) return;
    const token = Auth.getToken();
    if (!token) return;
    try {
      const parts = token.split('.');
      if (parts.length < 2) return;
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
      const exp = payload.exp;
      if (!exp) return;
      const secLeft = exp - Math.floor(Date.now() / 1000);
      if (secLeft > 0 && secLeft < 7 * 24 * 3600) API.refreshToken();
    } catch (e) {}
  },

  queueOffline(action, payload) {
    try {
      const q = JSON.parse(localStorage.getItem('mesh_offline_queue') || '[]');
      q.push({ action, payload, ts: Date.now() });
      localStorage.setItem('mesh_offline_queue', JSON.stringify(q));
      return true;
    } catch (e) { return false; }
  },

  flushOfflineQueue() {
    if (!navigator.onLine) return;
    let q = [];
    try { q = JSON.parse(localStorage.getItem('mesh_offline_queue') || '[]'); } catch (e) {}
    if (!q.length) { this.updateOfflinePending(); return; }
    const legacy = q.filter(i => i.action);
    const modern = q.filter(i => i.endpoint);
    const remain = [];
    let flushed = 0;
    legacy.forEach(item => {
      if (this.dispatchQueued(item)) flushed++;
      else remain.push(item);
    });
    localStorage.setItem('mesh_offline_queue', JSON.stringify(remain.concat(modern)));
    if (modern.length) {
      API.flushQueue().then(() => this.updateOfflinePending());
    } else {
      this.updateOfflinePending();
    }
    if (flushed) this.loadTickets();
  },

  dispatchQueued(item) {
    try {
      if (item.action === 'ticket') {
        const res = API.createTicket(item.payload.topic, item.payload.text);
        if (res && res.ok !== false) return true;
        return false;
      }
      if (item.action === 'chat') {
        API.postChat(item.payload.text);
        return true;
      }
    } catch (e) {}
    return false;
  },

  checkAuth() {
    const token = localStorage.getItem('mesh_token');
    if (token) {
      this.showMain();
      this.loadPrefs();
    }
  },

  showMain() {
    document.getElementById('screen-login').classList.remove('active');
    document.getElementById('bottom-nav').style.display = 'flex';
    this.navigateTo('schedule');
    this.showOnboardingIfNeeded();
    this.lockIfNeeded();
    this.ensurePushSubscription();
    requestAnimationFrame(() => this.slideNavIndicator());
    window.addEventListener('resize', () => this.slideNavIndicator());
    API.getNews().then(news => this.refreshNewsBadge(news)).catch(() => {});
  },

showLogin() {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-login').classList.add('active');
    document.getElementById('bottom-nav').style.display = 'none';
    this.renderSavedAccounts();
  },

  saveAccount() {
    try {
      const u = JSON.parse(localStorage.getItem('mesh_user') || '{}');
      const login = (document.getElementById('login-username') || {}).value;
      const pass = (document.getElementById('login-password') || {}).value;
      if (!login || !u.role) return;
      const accs = JSON.parse(localStorage.getItem('mesh_accounts') || '[]');
      const obj = { name: u.name || login, role: u.role || 'student', login: String(login).trim(), pass: String(pass) };
      const idx = accs.findIndex(a => a.login === obj.login);
      if (idx >= 0) accs[idx] = obj; else accs.push(obj);
      localStorage.setItem('mesh_accounts', JSON.stringify(accs.slice(-5)));
    } catch (e) {}
  },

  renderSavedAccounts() {
    const el = document.getElementById('saved-accounts');
    if (!el) return;
    let accs = [];
    try { accs = JSON.parse(localStorage.getItem('mesh_accounts') || '[]'); } catch (e) {}
    if (!accs.length) { el.innerHTML = ''; return; }
    el.innerHTML = `<div class="saved-acc-title">Быстрый вход</div>` +
      accs.map(a => `<div class="saved-acc">
        <button class="saved-acc-btn" onclick="App.useAccount('${(a.login || '').replace(/'/g, "\\'")}')">
          <span class="saved-acc-avatar">${(a.name || a.login || '?').slice(0, 1).toUpperCase()}</span>
          <span class="saved-acc-info"><b>${this.esc(a.name || a.login)}</b><em>${this.esc(a.role)} · ${this.esc(a.login)}</em></span>
        </button>
        <button class="saved-acc-del" onclick="App.removeAccount('${(a.login || '').replace(/'/g, "\\'")}')" title="Удалить">✕</button>
      </div>`).join('');
  },

  useAccount(login) {
    let accs = [];
    try { accs = JSON.parse(localStorage.getItem('mesh_accounts') || '[]'); } catch (e) {}
    const acc = accs.find(a => a.login === login);
    if (!acc) return;
    const u = document.getElementById('login-username');
    const p = document.getElementById('login-password');
    if (u) u.value = acc.login;
    if (p) p.value = acc.pass || '';
    Auth.submitLogin({ preventDefault() {} });
  },

  removeAccount(login) {
    let accs = [];
    try { accs = JSON.parse(localStorage.getItem('mesh_accounts') || '[]'); } catch (e) {}
    localStorage.setItem('mesh_accounts', JSON.stringify(accs.filter(a => a.login !== login)));
    this.renderSavedAccounts();
  },

  navigateTo(screen) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const target = document.getElementById('screen-' + screen);
    if (target) target.classList.add('active');
    this.currentScreen = screen;

    const items = document.querySelectorAll('.nav-item');
    items.forEach(item => {
      item.classList.toggle('active', item.dataset.screen === screen);
    });
    this.slideNavIndicator();

    if (screen === 'schedule') this.enterSchedule();
    if (screen === 'replacements') this.loadReplacements();
    if (screen === 'news') this.loadNews();
    if (screen === 'grades') this.loadGrades();
    if (screen === 'homework') this.loadHomework();
    if (screen === 'profile') this.loadProfile();
    if (screen === 'attendance') this.loadAttendance();
    if (screen === 'today') this.loadToday();
    if (screen === 'portfolio') this.loadPortfolio();
    if (screen === 'materials') this.loadMaterials();
    if (screen === 'extern') this.loadExtern();
    if (screen === 'extern') this.startChatPolling(); else this.stopChatPolling();
    if (screen === 'prep') this.loadPrep();
    if (screen === 'teacher') this.loadTeacher();
    if (screen === 'curator') this.loadCurator();
  },

  slideNavIndicator() {
    const nav = document.getElementById('bottom-nav');
    const ind = document.getElementById('nav-indicator');
    if (!nav || !ind || nav.style.display === 'none') return;
    const item = nav.querySelector('.nav-item.active');
    if (!item) return;
    const pad = 10;
    ind.style.width = Math.max(item.offsetWidth - pad * 2, 40) + 'px';
    ind.style.transform = `translateX(${item.offsetLeft + pad}px)`;
  },

  getRole() {
    try {
      const user = JSON.parse(localStorage.getItem('mesh_user') || '{}');
      return user.role || 'student';
    } catch (e) {
      return 'student';
    }
  },

  setScheduleMode(mode) {
    this.currentMode = mode;
    document.querySelectorAll('.mode-segment-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));

    const week = document.getElementById('week-mode');
    const session = document.getElementById('session-mode');
    const banner = document.getElementById('next-lesson-banner');
    const exportBtn = document.getElementById('btn-export-calendar');

    if (mode === 'week') {
      week.style.display = 'block';
      session.style.display = 'none';
      banner.style.display = 'block';
      exportBtn.style.display = 'flex';
      this.loadSchedule();
    } else {
      week.style.display = 'none';
      session.style.display = 'block';
      banner.style.display = 'none';
      exportBtn.style.display = 'none';
      this.loadExams();
    }
  },

  enterSchedule() {
    const session = document.getElementById('session-mode');
    const week = document.getElementById('week-mode');
    if (this.currentMode === 'session' && session) {
      week.style.display = 'none';
      session.style.display = 'block';
      this.loadExams();
    } else {
      this.currentMode = 'week';
      document.querySelectorAll('.mode-segment-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === 'week'));
      document.getElementById('btn-export-calendar').style.display = 'flex';
      this.loadSchedule();
    }
  },

  attachSwipe() {
    const el = document.getElementById('screen-schedule');
    if (!el || el.dataset.swipe) return;
    el.dataset.swipe = '1';
    let startX = 0;
    el.addEventListener('touchstart', e => { startX = e.touches[0].clientX; }, { passive: true });
    el.addEventListener('touchend', e => {
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) < 60) return;
      const order = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
      const idx = order.indexOf(this.currentDay);
      if (idx === -1) return;
      const next = idx + (dx < 0 ? 1 : -1);
      if (next < 0 || next >= order.length) return;
      const day = order[next];
      this.currentDay = day;
      document.querySelectorAll('.schedule-nav-btn').forEach(b => b.classList.toggle('active', b.dataset.day === day));
      this.loadSchedule();
    }, { passive: true });
  },

  copySchedule() {
    API.getSchedule(this.currentDay, this.currentStream, this.getGroup()).then(data => {
      if (!data || !data.lessons) return;
      const days = { mon: 'Понедельник', tue: 'Вторник', wed: 'Среда', thu: 'Четверг', fri: 'Пятница', sat: 'Суббота' };
      const lines = [`Расписание · ${days[this.currentDay] || this.currentDay}`];
      data.lessons.forEach(l => {
        if (l.subject === 'Окно') return;
        lines.push(`${l.pair} пара (${l.time_start}–${l.time_end}) — ${l.subject}, ${l.teacher}, ${l.room}`);
      });
      const text = lines.join('\n');
      navigator.clipboard.writeText(text).then(() => {
        if (!('vibrate' in navigator)) return;
        try { navigator.vibrate(30); } catch (e) {}
      }).catch(() => {});
    });
  },

  showSkeleton(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = '<div class="skeleton-block"></div><div class="skeleton-block"></div><div class="skeleton-block"></div>';
  },

  loadSchedule() {
    this.showSkeleton('schedule-content');
    API.getSchedule(this.currentDay, this.currentStream, this.getGroup()).then(data => {
      if (data && data.lessons) {
        this.renderSchedule(data.lessons);
        this.updateNextLesson(data.lessons);
      }
    });
  },

  getGroup() {
    try {
      const user = JSON.parse(localStorage.getItem('mesh_user') || '{}');
      return user.group || '';
    } catch (e) {
      return '';
    }
  },

  speakSchedule() {
    const dayNames = { mon: 'Понедельник', tue: 'Вторник', wed: 'Среда', thu: 'Четверг', fri: 'Пятница', sat: 'Суббота', sun: 'Воскресенье' };
    const container = document.getElementById('schedule-content');
    const lessons = container ? container.querySelectorAll('.lesson-card') : [];
    if (!lessons.length) { this.speak('В этот день занятий нет'); return; }
    let text = dayNames[this.currentDay] + ': ';
    lessons.forEach((card, i) => {
      const subj = card.querySelector('.lesson-subject');
      const time = card.querySelector('.time-start');
      const room = card.querySelector('.lesson-room');
      text += `пара ${i + 1} в ${time ? time.textContent : ''}, ${subj ? subj.textContent : ''}, ${room ? room.textContent : ''}. `;
    });
    window.speechSynthesis.cancel();
    this.speak(text);
  },

  renderSchedule(lessons) {
    const container = document.getElementById('schedule-content');
    const real = lessons.filter(l => l.subject !== 'Окно');
    this.updateScheduleHeader(real);

    if (!lessons.length) {
      container.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="4" width="18" height="18" rx="2"/>
            <path d="M16 2v4M8 2v4M3 10h18"/>
          </svg>
          <p>Нет занятий в этот день</p>
        </div>`;
      return;
    }

    container.innerHTML = lessons.map((l, i) => `
      <div class="lesson-card" style="animation-delay:${Math.min(i * 55, 330)}ms">
        <div class="lesson-pair">${l.pair} пара</div>
        <div class="lesson-time">
          <span class="time-start">${l.time_start}</span>
          <span class="time-separator">—</span>
          <span class="time-end">${l.time_end}</span>
        </div>
        <div class="lesson-info">
          <div class="lesson-subject">${l.subject}${/онлайн|дист|zoom|вебинар/i.test(l.room || '') ? ' <span class="online-badge">онлайн</span>' : ''}</div>
          <div class="lesson-teacher">${l.teacher}</div>
          <div class="lesson-room">${l.room}</div>
        </div>
        <div class="lesson-type lesson-type--${l.type}">${l.type === 'lection' ? 'Лекция' : 'Практика'}</div>
        <div class="lesson-transition">переход в ${l.transition}</div>
      </div>`).join('');

    container.classList.remove('day-anim');
    void container.offsetWidth;
    container.classList.add('day-anim');
  },

  updateScheduleHeader(real) {
    const el = document.getElementById('current-date');
    if (!el) return;
    const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    const weekdays = { mon: 'Понедельник', tue: 'Вторник', wed: 'Среда', thu: 'Четверг', fri: 'Пятница', sat: 'Суббота', sun: 'Воскресенье' };
    const now = new Date();
    const isToday = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][now.getDay()] === this.currentDay;
    const parts = [weekdays[this.currentDay] || ''];
    if (isToday) parts.push(`${now.getDate()} ${months[now.getMonth()]}`);
    if (real && real.length) {
      const n = real.length;
      const word = n === 1 ? 'пара' : (n >= 2 && n <= 4 ? 'пары' : 'пар');
      parts.push(`${n} ${word}`);
    } else {
      parts.push('занятий нет');
    }
    el.textContent = parts.join(' · ');
  },

  updateNextLesson(lessons) {
    const banner = document.getElementById('next-lesson-banner');
    if (!banner) return;

    const now = new Date();
    const todayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][now.getDay()];

    if (todayKey === 'sun') {
      banner.className = 'next-lesson-banner nl-ok';
      banner.innerHTML = `<div class="nl-subject">Выходной</div><div class="nl-meta">Следующие занятия — в понедельник</div>`;
      return;
    }

    if (todayKey !== this.currentDay) {
      banner.style.display = 'none';
      return;
    }
    banner.style.display = 'block';

    const nowMin = now.getHours() * 60 + now.getMinutes();
    let next = null;

    for (const l of lessons) {
      const [sh, sm] = l.time_start.split(':').map(Number);
      const [eh, em] = l.time_end.split(':').map(Number);
      const startMin = sh * 60 + sm;
      const endMin = eh * 60 + em;
      if (nowMin < startMin) { next = l; break; }
      if (nowMin >= startMin && nowMin < endMin) { next = l; next.inProgress = true; break; }
    }

    if (!next) {
      const nextDay = todayKey === 'sat' ? 'В понедельник' : 'завтра';
      banner.className = 'next-lesson-banner nl-ok';
      banner.innerHTML = `
        <div class="nl-time">Сегодня</div>
        <div class="nl-subject">Занятия на сегодня окончены</div>
        <div class="nl-meta">Следующая пара — ${nextDay}</div>`;
      return;
    }

    if (next.inProgress) {
      banner.className = 'next-lesson-banner nl-ok';
      banner.innerHTML = `
        <div class="nl-time">Сейчас идёт · ${next.time_start}–${next.time_end}</div>
        <div class="nl-subject">${next.pair} пара · ${next.subject}</div>
        <div class="nl-meta">${next.teacher} · ${next.room}</div>`;
      return;
    }

    const [nh, nm] = next.time_start.split(':').map(Number);
    const diffMin = (nh * 60 + nm) - nowMin;
    const timeLabel = diffMin < 60
      ? `через ${diffMin} мин`
      : `через ${Math.floor(diffMin / 60)} ч ${diffMin % 60} мин`;

    banner.className = 'next-lesson-banner';
    banner.innerHTML = `
      <div class="nl-time">Ближайшая пара · ${next.time_start}–${next.time_end}</div>
      <div class="nl-subject">${next.pair} пара · ${next.subject}</div>
      <div class="nl-meta">${next.teacher} · ${next.room} · ${next.transition ? 'переход в ' + next.transition : ''} · начало ${timeLabel}</div>`;
  },

  loadExams() {
    this.showSkeleton('exam-list');
    API.getExams().then(data => {
      if (data) this.renderExams(data);
    });
  },

  renderExams(data) {
    document.getElementById('session-title').textContent = data.session;
    document.getElementById('session-count').textContent = `${data.exams.length} экзаменов`;

    const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const container = document.getElementById('exam-list');
    container.innerHTML = data.exams.map(e => {
      const d = new Date(e.date);
      const daysLeft = Math.round((d - today) / 86400000);
      const soon = daysLeft <= 14;

      let label;
      if (daysLeft === 0) label = 'Сегодня';
      else if (daysLeft === 1) label = 'Завтра';
      else label = `через ${daysLeft} дн.`;

      return `
        <div class="exam-card">
          <div class="exam-date-box">
            <span class="exam-day">${d.getDate()}</span>
            <span class="exam-month">${months[d.getMonth()]}</span>
          </div>
          <div class="exam-info">
            <div class="exam-subject">${e.subject}</div>
            <div class="exam-form">${e.form} · ${e.time}</div>
            ${e.average ? `<div class="exam-avg">средний балл ${e.average}</div>` : ''}
          </div>
          <div class="exam-countdown${soon ? ' soon' : ''}">${label}</div>
        </div>`;
    }).join('');

    this.renderExamExtras(data);
  },

  renderExamExtras(data) {
    const el = document.getElementById('exam-extras');
    if (!el) return;
    let html = '';

    if (data.exams && data.exams.some(e => e.access)) {
      html += `<div class="exam-access-card">
        <div class="section-title">Допуск к сессии</div>`;
      data.exams.forEach(e => {
        const ok = e.access === 'Допущен';
        html += `<div class="exam-access-row">
          <span class="exam-access-subject">${e.subject}</span>
          <span class="exam-access-status ${ok ? 'access-ok' : 'access-bad'}">${e.access}</span>
        </div>`;
      });
      html += '</div>';
    }

    if (data.consultations && data.consultations.length) {
      html += `<div class="exam-access-card">
        <div class="section-title">Консультации</div>`;
      data.consultations.forEach(c => {
        html += `<div class="exam-consult-row"><b>${c.subject}</b><span>${c.date} · ${c.time} · ${c.room}</span></div>`;
      });
      html += '</div>';
    }

    if (data.retakes) {
      html += `<div class="exam-retake">${data.retakes}</div>`;
    }

    el.innerHTML = html;
  },

  loadReplacements() {
    this.showSkeleton('replacements-content');
    API.getReplacements().then(data => {
      if (data) this.renderReplacements(data);
    });
  },

  renderReplacements(data) {
    document.getElementById('replacements-date').textContent = data.date;
    const container = document.getElementById('replacements-content');

    if (!data.items.length) {
      container.innerHTML = `
        <div class="empty-state">
          <p>Замен пока нет</p>
        </div>`;
      return;
    }

    container.innerHTML = data.items.map(r => `
      <div class="replacement-card">
        <div class="replacement-header">
          <span class="replacement-day">${r.day}</span>
          <span class="replacement-pair">${r.pair} пара · ${r.time}</span>
        </div>
        <div class="replacement-subject">${r.subject}</div>
        <div class="replacement-people">
          <div class="replacement-person">${r.from_teacher} <span class="arrow">→</span> ${r.replacement_teacher}</div>
        </div>
        <div class="replacement-room">Аудитория: ${r.room}</div>
        ${r.note ? `<div class="replacement-note">${r.note}</div>` : ''}
      </div>`).join('');
  },

  loadNews(keep) {
    if (!keep) this.showSkeleton('news-content');
    Promise.all([API.getNews(), API.getNewsMeta()]).then(([news, meta]) => {
      this.newsMeta = meta || { likes: {}, comments: {} };
      if (news) {
        this.refreshNewsBadge(news);
        this.renderNews(news);
      }
    });
  },

  refreshNewsBadge(news) {
    const el = document.getElementById('news-badge');
    if (!el) return;
    if (!news || !news.length) { el.style.display = 'none'; return; }
    let seen = [];
    try { seen = JSON.parse(localStorage.getItem('mesh_news_seen') || '[]'); } catch (e) {}
    const unread = news.filter(n => seen.indexOf(String(n.id || n.title || '')) === -1).length;
    if (unread > 0) {
      el.textContent = unread > 9 ? '9+' : String(unread);
      el.style.display = 'flex';
    } else {
      el.style.display = 'none';
    }
  },

  markNewsSeen(data) {
    if (!data || !data.length) return;
    let seen = [];
    try { seen = JSON.parse(localStorage.getItem('mesh_news_seen') || '[]'); } catch (e) {}
    data.forEach(n => {
      const id = String(n.id || n.title || '');
      if (seen.indexOf(id) === -1) seen.push(id);
    });
    localStorage.setItem('mesh_news_seen', JSON.stringify(seen.slice(-200)));
    const el = document.getElementById('news-badge');
    if (el) el.style.display = 'none';
  },

  renderNews(data) {
    const container = document.getElementById('news-content');
    if (!container) return;

    if (!data || !data.length) {
      container.innerHTML = `
        <div class="empty-state">
          <p>Новостей пока нет</p>
        </div>`;
      return;
    }

    const meta = this.newsMeta || { likes: {}, comments: {} };
    const me = JSON.parse(localStorage.getItem('mesh_user') || '{}').name || '';
    const canLike = !!Auth.getToken() && this.getRole() === 'student';

    container.innerHTML = data.map(n => {
      const id = String(n.id || n.title || '');
      const speakText = String(n.title + '. ' + (n.body || '')).split('"').join('&quot;');
      const likes = (meta.likes && meta.likes[id]) || [];
      const comments = (meta.comments && meta.comments[id]) || [];
      const liked = Array.isArray(likes) && likes.indexOf(me) !== -1;
      return `
      <div class="news-card${n.important ? ' news-card--important' : ''}">
        <div class="news-card-header">
          <span class="news-category">${n.category || ''}</span>
          ${n.important ? '<span class="news-important">Важно</span>' : ''}
          <span class="news-date">${n.date || ''}</span>
        </div>
        <div class="news-title">${n.title}<button class="icon-btn news-voice" onclick="App.speak('${speakText}')" title="Озвучить новость">🔊</button></div>
        <div class="news-body">${n.body || n.text || n.summary || ''}</div>
        ${(meta.reads && meta.reads[id]) ? `<div class="news-reads">Прочитано: ${meta.reads[id].length}</div>` : ''}
        ${canLike ? `
        <div class="news-actions">
          <button class="news-like${liked ? ' liked' : ''}" onclick="App.toggleNewsLike('${id.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')">
            ♥ <span>${likes.length}</span>
          </button>
          <div class="news-comments">
            ${comments.map(c => `<div class="news-comment"><b>${c.name}</b> · ${c.text}<em>${c.ts}</em></div>`).join('')}
            <input class="text-field nc-input" id="nc-input-${encodeURIComponent(id)}" placeholder="Комментарий…" onkeydown="if(event.key==='Enter')App.addNewsComment('${id.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')">
            <button class="btn-secondary news-comment-btn" onclick="App.addNewsComment('${id.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')">Отправить</button>
          </div>
        </div>` : ''}
      </div>`;
    }).join('');
    this.autoMarkReads(data);
    this.markNewsSeen(data);
  },

  autoMarkReads(data) {
    if (!Auth.getToken()) return;
    const me = JSON.parse(localStorage.getItem('mesh_user') || '{}').name || '';
    const meta = this.newsMeta || { likes: {}, comments: {}, reads: {} };
    meta.reads = meta.reads || {};
    data.forEach(n => {
      if (!n.important) return;
      const id = String(n.id || n.title || '');
      const reads = meta.reads[id] || [];
      if (reads.indexOf(me) === -1) {
        API.newsRead(id).then(res => {
          if (res && (res.ok !== false)) {
            if (!this.newsMeta) this.newsMeta = {};
            this.newsMeta.reads = this.newsMeta.reads || {};
            this.newsMeta.reads[id] = (this.newsMeta.reads[id] || []).concat(me);
          }
        });
      }
    });
  },

  toggleBells() {
    const panel = document.getElementById('bells-panel');
    if (!panel) return;
    if (panel.style.display === 'block') {
      panel.style.display = 'none';
      return;
    }
    panel.style.display = 'block';
    this.loadBellsPanel();
  },

  loadBellsPanel() {
    API.getBells().then(data => {
      const panel = document.getElementById('bells-panel');
      if (!panel) return;
      if (!data) {
        panel.innerHTML = '<div class="bells-empty">Звонков нет</div>';
        return;
      }
      const shift = (title, pairs) => `
        <div class="bells-shift">
          <div class="bells-shift-title">${title}</div>
          <div class="bells-shift-pairs">${pairs.map(p => `
            <div class="bells-shift-pair">
              <span class="bells-shift-num">${p.pair} пара</span>
              <span class="bells-shift-time">${p.start}–${p.end}</span>
              <span class="bells-shift-transition">переход ${p.transition}</span>
            </div>`).join('')}
          </div>
        </div>`;
      let html = '<div class="bells-panel-title">Расписание звонков</div>';
      html += `<div class="bells-shift-row">${shift('1 смена', data.first)}</div>`;
      html += `<div class="bells-shift-row">${shift('2 смена', data.second)}</div>`;
      if (data.saturday && data.saturday.length) {
        html += `<div class="bells-shift-row">${shift('Суббота', data.saturday)}</div>`;
      }
      panel.innerHTML = html + `<button class="btn-secondary bells-rooms-btn" onclick="App.showFreeRooms()">Свободные аудитории сейчас</button>`;
    });
  },

  loadAttendance() {
    API.getAttendance().then(data => {
      if (data) this.renderAttendance(data);
    });
  },

  renderAttendance(data) {
    const groupEl = document.getElementById('attendance-group');
    if (groupEl) groupEl.textContent = data.group || '';

    const container = document.getElementById('attendance-content');
    if (!data.days || !data.days.length) {
      container.innerHTML = `<div class="empty-state"><p>Нет данных о посещаемости</p></div>`;
      return;
    }

    const badge = (status, subject) => {
      const cls = status === 'present' ? 'att-ok' : status === 'late' ? 'att-late' : 'att-bad';
      const label = status === 'present' ? 'Был' : status === 'late' ? 'Опоздал' : 'Нет';
      return `<div class="att-lesson"><span class="att-dot ${cls}"></span><span class="att-subject">${subject}</span><em>${label}</em></div>`;
    };

    let html = `
      <div class="attendance-summary">
        <div class="grade-stat">
          <div class="grade-stat-value">${data.attendance}%</div>
          <div class="grade-stat-label">Посещаемость за 2 недели</div>
        </div>
      </div>`;

    data.days.forEach(d => {
      html += `
        <div class="attendance-day">
          <div class="attendance-day-head">
            <span>${d.date} · ${d.weekday}</span>
            <span class="att-count">${d.present}/${d.total}</span>
          </div>
          <div class="attendance-day-lessons">
            ${d.lessons.map(l => badge(l.status, l.subject)).join('')}
          </div>
        </div>`;
    });

    container.innerHTML = html;
  },

  startBellCountdown(dayKey, bells) {
    if (this._bellTimer) { clearInterval(this._bellTimer); this._bellTimer = null; }
    const el = document.getElementById('today-countdown');
    if (!el || dayKey === 'sun') return;
    const slots = [...(bells.first || []), ...(bells.second || [])];
    const toMin = t => { const a = String(t || '0:0').split(':').map(Number); return a[0] * 60 + a[1]; };
    const pad = n => String(n).padStart(2, '0');
    const fmtLeft = sec => {
      if (sec < 0) sec = 0;
      const m = Math.floor(sec / 60), s = sec % 60;
      if (m >= 60) return `${Math.floor(m / 60)}ч ${pad(m % 60)}м`;
      return `${pad(m)}:${pad(s)}`;
    };
    const tick = () => {
      const now = new Date();
      const nowSec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
      const nowMin = nowSec / 60;
      let html = '';
      const active = slots.find(s => toMin(s.start) <= nowMin && nowMin < toMin(s.end));
      if (active) {
        const endSec = toMin(active.end) * 60;
        const startSec = toMin(active.start) * 60;
        const span = Math.max(1, endSec - startSec);
        const pct = Math.max(0, Math.min(100, Math.round((nowSec - startSec) / span * 100)));
        html = `
          <div class="bell-widget bell-widget--active">
            <div class="bell-widget-head">
              <span class="bell-widget-dot"></span>
              <span class="bell-widget-label">Идёт ${active.pair}-я пара</span>
            </div>
            <div class="bell-widget-time">${fmtLeft(endSec - nowSec)}</div>
            <div class="bell-widget-sub">до перемены · конец в ${active.end}</div>
            <div class="bell-widget-bar"><div class="bell-widget-fill" style="width:${pct}%"></div></div>
          </div>`;
      } else {
        const next = slots.find(s => toMin(s.start) > nowMin);
        if (next) {
          const startSec = toMin(next.start) * 60;
          html = `
            <div class="bell-widget">
              <div class="bell-widget-head">
                <span class="bell-widget-label">До ${next.pair}-й пары</span>
              </div>
              <div class="bell-widget-time">${fmtLeft(startSec - nowSec)}</div>
              <div class="bell-widget-sub">звонок в ${next.start} · переход ${next.transition}</div>
            </div>`;
        } else {
          html = `
            <div class="bell-widget bell-widget--done">
              <div class="bell-widget-head"><span class="bell-widget-label">Учебный день окончен</span></div>
              <div class="bell-widget-time">🎉</div>
              <div class="bell-widget-sub">Отдыхай — завтра новый день</div>
            </div>`;
        }
      }
      el.innerHTML = html;
    };
    tick();
    this._bellTimer = setInterval(tick, 1000);
  },

  loadToday() {
    const container = document.getElementById('today-content');
    if (container) this.showSkeleton('today-content');
    this.updateDateDisplay();
    document.getElementById('today-date').textContent = document.getElementById('current-date').textContent || '';
    const dayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][new Date().getDay()];
    const today = dayKey;
    const day = today === 'sun' ? 'mon' : today;

    Promise.all([
      API.getSchedule(day, this.currentStream || 'alfa', this.getGroup()),
      API.getAnnual(),
      API.getCanteen(),
      API.getNews(),
      API.getHomework(),
      API.getExams(),
      API.getBirthdays(),
      API.getBells(),
      API.getDuties(),
      API.getMyDebts(),
      API.getGrades(),
      API.getWeather()
    ]).then(([sched, annual, canteen, news, hw, exams, bday, bells, duties, debts, grades, weather]) => {
      this.renderToday({ sched, annual, canteen, news, hw, exams, dayKey, bday, bells, duties, debts, grades, weather });
      this.startBellCountdown(dayKey, bells);
    });
  },

  renderToday({ sched, annual, canteen, news, hw, exams, dayKey, bday, bells, duties, debts, grades, weather }) {
    const container = document.getElementById('today-content');
    if (!container) return;
    const days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
    let html = `<div class="today-card today-card--hero">
      <div class="today-card-title">${days[new Date().getDay()]}</div>`;

    const wName = {0:'Ясно',1:'В основном ясно',2:'Переменная облачность',3:'Пасмурно',45:'Туман',48:'Туман',51:'Морось',61:'Дождь',63:'Дождь',71:'Снег',73:'Снег',75:'Снег',80:'Ливень',81:'Ливень',95:'Гроза',96:'Гроза'};
    if (weather && weather.temp != null) {
      const wc = wName[weather.code] || 'Погода';
      html += `<div class="today-card today-card--weather">
        <div class="today-card-title">${wc}</div>
        <div class="weather-row">
          <div class="weather-temp">${Math.round(weather.temp)}°</div>
          <div class="weather-meta">
            <div>${weather.min != null ? 'днём ' + Math.round(weather.max) + '°' : ''}${weather.wind != null ? ' · ветер ' + Math.round(weather.wind) + ' м/с' : ''}</div>
            <div class="weather-note">В плохую погоду часть пар может быть онлайн — проверяйте замены</div>
          </div>
        </div>
      </div>`;
    }

    if (dayKey === 'sun') {
      html += `<div class="today-card-sub">Выходной — отдыхай!</div>`;
    } else {
      const lessons = (sched && sched.lessons) || [];
      const real = lessons.filter(l => l.subject !== 'Окно');
      if (real.length) {
        const first = real[0];
        html += `<div class="today-card-sub">Ближайшая пара: <b>${first.subject}</b>, ${first.time_start}, ${first.room}</div>`;
        html += `<div class="today-card-sub">Всего пар сегодня: ${real.length}</div>`;
        html += `<div class="today-countdown bell-wrap" id="today-countdown"></div>`;
      } else {
        html += `<div class="today-card-sub">Сегодня занятий нет</div>`;
      }
    }
    html += '</div>';

    if (grades && grades.subjects) {
      let sum = 0, n = 0;
      grades.subjects.forEach(s => (s.marks || []).forEach(m => { sum += Number(m.value || m || 0); n++; }));
      if (n > 0) {
        const target = parseFloat(localStorage.getItem('mesh_target') || '4.5');
        const avg = sum / n;
        const need = target * (n + 1) - sum;
        const msg = need <= 1
          ? 'Одна «5» поднимет средний балл до цели'
          : `Нужно ещё ≈${Math.ceil(need)} «пятёрок», чтобы средний балл стал ${target}`;
        html += `<div class="today-card today-card--grade">
          <div class="today-card-title">Цель по баллу</div>
          <div class="today-menu-row"><span>Средний балл: <b>${avg.toFixed(2)}</b></span><span class="today-price">к цели ${target}</span></div>
          <div class="today-goal-bar"><div class="today-goal-fill" style="width:${Math.min(100, Math.round(avg / 5 * 100))}%"></div></div>
          <div class="replacement-note">${msg}</div>
        </div>`;
      }
    }

    if (debts) {
      if (debts.count > 0) {
        html += `<div class="today-card today-card--debts">
          <div class="today-card-title">Мои долги (${debts.count})</div>`;
        debts.debts.forEach(d => {
          html += `<div class="today-menu-row"><span><b>${d.subject}</b> — средний ${d.average.toFixed ? d.average.toFixed(2) : d.average}</span><span class="today-price">нужно ещё ${d.need}</span></div>`;
        });
        html += '</div>';
      } else {
        html += `<div class="today-card today-card--ok"><div class="today-card-title">Мои долги</div>
          <div class="today-menu-row"><span>Нет долгов — отлично!</span><span class="today-price">✓</span></div></div>`;
      }
    }

    if (duties && duties.today && duties.today.names && duties.today.names.length) {
      html += `<div class="today-card">
        <div class="today-card-title">Дежурные сегодня</div>
        <div class="today-menu-row"><span>${duties.today.names.join(', ')}</span></div>
      </div>`;
    }

    if (annual && annual.next && annual.next.length) {
      html += `<div class="today-card">
        <div class="today-card-title">Учебный календарь</div>`;
      annual.next.forEach(e => {
        const t = { holiday: '🎉', exam: '📝', attestation: '📊', event: '📅' }[e.type] || '•';
        html += `<div class="today-event"><span>${e.date}</span><span>${t} ${e.title}</span></div>`;
      });
      html += '</div>';
    }

    if (canteen && Array.isArray(canteen.days)) {
      const weekdayNames = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
      const todayName = weekdayNames[dayKey === 'sun' ? 0 : new Date().getDay()];
      const todayMenu = canteen.days.find(d => todayName.includes(d.day)) || canteen.days[0] || null;
      if (todayMenu) {
        html += `<div class="today-card">
          <div class="today-card-title">Меню столовой · ${todayMenu.day}</div>`;
        todayMenu.meals.forEach(m => {
          const fav = this.favDishes().indexOf(m.name) !== -1;
          html += `<div class="today-menu-row"><span>${m.name}</span><span class="today-menu-right"><span class="today-fav${fav ? ' fav-on' : ''}" data-d="${encodeURIComponent(m.name)}" onclick="App.toggleFavDish(this.dataset.d)">★</span><span class="today-price">${m.price} ₽</span></span></div>`;
        });
        html += '</div>';
      }
    }

    if (hw && hw.length) {
      const urgent = hw.filter(h => h.urgent || h.soon).slice(0, 3);
      if (urgent.length) {
        html += `<div class="today-card">
          <div class="today-card-title">Срочные задания</div>`;
        urgent.forEach(h => {
          html += `<div class="today-menu-row"><span><b>${h.subject}</b> — ${h.task}</span><span class="today-price">${h.badge}</span></div>`;
        });
        html += '</div>';
      }
    }

    if (exams && exams.exams && exams.exams.length) {
      const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
      const soonExam = exams.exams
        .map(e => ({ ...e, d: new Date(e.date) }))
        .filter(e => !isNaN(e.d))
        .sort((a, b) => a.d - b.d)[0];
      if (soonExam) {
        html += `<div class="today-card">
          <div class="today-card-title">Ближайший экзамен</div>
          <div class="today-menu-row"><span><b>${soonExam.subject}</b> — ${soonExam.form}</span><span class="today-price">${soonExam.d.getDate()} ${months[soonExam.d.getMonth()]}</span></div>
        </div>`;
      }
    }

    if (news && news.length) {
      const n = news[0];
      html += `<div class="today-card today-card--news">
        <div class="today-card-title">${n.category || 'Новость'}</div>
        <div class="today-news-title">${n.title}</div>
      </div>`;
    }

    if (bday && bday.birthdays && bday.birthdays.length) {
      const now = new Date();
      const todayMm = String(now.getMonth() + 1).padStart(2, '0');
      const soonBirthdays = bday.birthdays.filter(b => b.date && b.date.startsWith(todayMm)).slice(0, 5);
      if (soonBirthdays.length) {
        html += `<div class="today-card">
          <div class="today-card-title">Дни рождения в этом месяце</div>`;
        soonBirthdays.forEach(b => {
          html += `<div class="today-menu-row"><span>🎂 ${b.name}</span><span class="today-price">${b.date}</span></div>`;
        });
        html += '</div>';
      }
    }

    container.innerHTML = html;
  },

  loadPortfolio() {
    this.showSkeleton('portfolio-practice');
    API.getPortfolio().then(data => {
      if (data) this.renderPortfolio(data);
    });
    this.loadTickets();
  },

  renderPortfolio(data) {
    this.portfolioData = data;
    const practice = document.getElementById('portfolio-practice');
    const course = document.getElementById('portfolio-coursework');
    const diploma = document.getElementById('portfolio-diploma');
    const ach = document.getElementById('portfolio-achievements');

    document.getElementById('portfolio-practice-count').textContent =
      `${(data.practice || []).length} вида(ов) практики`;
    practice.innerHTML = (data.practice || []).map(p => `
      <div class="replacement-card">
        <div class="replacement-subject">${p.type}</div>
        <div class="replacement-room">База: ${p.place} · Объём: ${p.hours}</div>
        <div class="replacement-note">Период: ${p.period}</div>
      </div>`).join('') || '<div class="sub-note">Практики пока нет</div>';

    const cw = data.coursework || {};
    course.innerHTML = cw.topic ? `
      <div class="replacement-card">
        <div class="replacement-subject">${cw.subject || 'Курсовой проект'}</div>
        <div class="replacement-room">Тема: ${cw.topic}</div>
        <div class="replacement-note">Руководитель: ${cw.curator || '—'} · Срок: ${cw.deadline || '—'}</div>
      </div>` : '<div class="sub-note">Курсовой не назначен</div>';

    const dm = data.diploma || {};
    diploma.innerHTML = dm.topic ? `
      <div class="replacement-card">
        <div class="replacement-subject">Дипломная работа · ${dm.year || ''}</div>
        <div class="replacement-room">Тема: ${dm.topic}</div>
        <div class="replacement-note">Руководитель: ${dm.curator || '—'}</div>
      </div>` : '<div class="sub-note">Тема диплома не назначена</div>';

    ach.innerHTML = (data.achievements || []).map(a => `
      <div class="replacement-card">
        <div class="replacement-subject">${a.title}</div>
        <div class="replacement-room">Уровень: ${a.level || '—'} · ${a.date || ''}</div>
      </div>`).join('') || '<div class="sub-note">Достижений пока нет</div>';
  },

  printPortfolio() {
    const d = this.portfolioData;
    const printArea = document.getElementById('print-area');
    if (!printArea) return;
    const bloc = (title, items, fn) => `<h2>${title}</h2>${(items || []).map(fn).join('') || '<p>—</p>'}`;
    printArea.innerHTML = `
      <div class="print-doc">
        <h1>Портфолио студента</h1>
        <p>${JSON.parse(localStorage.getItem('mesh_user') || '{}').name || ''} · ${JSON.parse(localStorage.getItem('mesh_user') || '{}').group || ''}</p>
        ${bloc('Практика', d && d.practice, p => `<p><b>${p.type || p.title || ''}</b> — ${p.place || ''}${p.dates ? ' · ' + p.dates : ''}</p>`)}
        ${bloc('Курсовой проект', d && d.coursework, c => `<p>${c.title || ''}${c.mark ? ' · Оценка: ' + c.mark : ''}</p>`)}
        ${bloc('Диплом', d && d.diploma, dm => `<p>«${dm.topic || ''}» · Руководитель: ${dm.curator || '—'}</p>`)}
        ${bloc('Достижения', d && d.achievements, a => `<p>${a.title || ''} (${a.level || ''}${a.date ? ', ' + a.date : ''})</p>`)}
        <p class="spravka-meta">Сформировано ${new Date().toLocaleDateString('ru-RU')}</p>
      </div>`;
    window.print();
  },

  loadTickets() {
    API.getTickets().then(data => {
      const container = document.getElementById('tickets-list');
      if (!container || !data) return;
      const tickets = data.tickets || [];
      if (!tickets.length) {
        container.innerHTML = '<div class="sub-note">Обращений ещё нет</div>';
        return;
      }
      const labels = { 'new': 'Новое', 'in-progress': 'В работе', 'done': 'Готово' };
      container.innerHTML = tickets.map(t => `
        <div class="ticket-item">
          <div class="ticket-item-head"><b>${t.topic}</b><span class="ticket-pill ticket-${t.status}">${labels[t.status] || t.status}</span></div>
          <div class="ticket-item-text">${t.text}</div>
          ${t.answer ? `<div class="ticket-answer">Ответ куратора: ${t.answer}${t.answer_ts ? ' · ' + t.answer_ts : ''}</div>` : ''}
          <div class="ticket-item-meta">${t.created} · ${t.group}</div>
        </div>`).join('');
    });
  },

  createTicket() {
    const topic = document.getElementById('ticket-topic').value.trim();
    const text = document.getElementById('ticket-text').value.trim();
    const status = document.getElementById('ticket-status');
    if (!topic) { status.textContent = 'Укажите тему обращения'; return; }
    if (!text) { status.textContent = 'Опишите вопрос'; return; }
    if (navigator.onLine === false) {
      this.queueOffline('ticket', { topic, text });
      document.getElementById('ticket-topic').value = '';
      document.getElementById('ticket-text').value = '';
      status.textContent = 'Нет сети — обращение уйдёт автоматически при подключении';
      const queued = JSON.parse(localStorage.getItem('mesh_offline_queue') || '[]')
        .filter(i => i.action === 'ticket')
        .map(i => ({ topic: i.payload.topic, text: i.payload.text + ' (в очереди)', created: '—', group: 'офлайн' }));
      this.loadTickets();
      const container = document.getElementById('tickets-list');
      if (container && queued.length) {
        container.innerHTML = queued.map(t => `
          <div class="ticket-item">
            <div class="ticket-item-head"><b>${t.topic}</b><span class="ticket-pill ticket-new">В очереди</span></div>
            <div class="ticket-item-text">${t.text}</div>
          </div>`).join('');
      }
      return;
    }
    API.createTicket(topic, text).then(res => {
      if (res && res.ok) {
        document.getElementById('ticket-topic').value = '';
        document.getElementById('ticket-text').value = '';
        status.textContent = 'Обращение отправлено в деканат';
        this.loadTickets();
      } else {
        status.textContent = (res && res.detail) || 'Ошибка отправки';
      }
    });
  },

  makePinPad() {
    const pad = document.getElementById('pin-pad');
    if (!pad) return;
    pad.innerHTML = [1, 2, 3, 4, 5, 6, 7, 8, 9, '', 0, '⌫']
      .map(n => `<button class="pin-key" data-n="${n}">${n}</button>`).join('');
    pad.querySelectorAll('.pin-key').forEach(btn => {
      btn.addEventListener('click', () => this.pressPinKey(btn.dataset.n));
    });
    this.pinBuffer = [];
    this.pinStage = 'unlock';
    this.pinFirst = '';
  },

  pressPinKey(key) {
    if (key === '') return;
    if (key === '⌫') {
      this.pinBuffer.pop();
      this.renderPinInputs();
      return;
    }
    if (this.pinBuffer.length >= 4) return;
    this.pinBuffer.push(String(key));
    this.renderPinInputs();
    if (this.pinBuffer.length === 4) this.pinDone();
  },

  renderPinInputs() {
    const box = document.getElementById('pin-inputs');
    if (!box) return;
    box.innerHTML = [0, 1, 2, 3].map(i =>
      `<span class="pin-dot ${i < this.pinBuffer.length ? 'fill' : ''}"></span>`).join('');
  },

  pinDone() {
    const code = this.pinBuffer.join('');
    const overlay = document.getElementById('pin-overlay');
    const err = document.getElementById('pin-error');
    if (err) err.textContent = '';

    if (this.pinStage === 'unlock') {
      if (code === localStorage.getItem('mesh_pin')) {
        overlay.style.display = 'none';
        this.pinBuffer = [];
        sessionStorage.setItem('mesh_unlocked', '1');
      } else {
        if (err) err.textContent = 'Неверный пин-код';
        this.pinBuffer = [];
        this.renderPinInputs();
      }
      return;
    }

    if (this.pinStage === 'set') {
      this.pinFirst = code;
      this.pinStage = 'confirm';
      this.pinBuffer = [];
      this.renderPinInputs();
      return;
    }

    if (this.pinStage === 'confirm') {
      if (code === this.pinFirst) {
        localStorage.setItem('mesh_pin', code);
        overlay.style.display = 'none';
        this.updatePinUI();
      } else {
        if (err) err.textContent = 'Пин-коды не совпадают, начните заново';
        this.pinStage = 'set';
        this.pinFirst = '';
      }
      this.pinBuffer = [];
      this.renderPinInputs();
    }
  },

  togglePinLock() {
    const has = localStorage.getItem('mesh_pin');
    if (has) {
      if (!confirm('Выключить пин-код? Введите текущий пин-код.')) return;
      localStorage.removeItem('mesh_pin');
      sessionStorage.removeItem('mesh_unlocked');
      this.updatePinUI();
      return;
    }
    this.pinStage = 'set';
    this.pinFirst = '';
    this.pinBuffer = [];
    this.renderPinInputs();
    document.getElementById('pin-overlay').style.display = 'flex';
  },

  updatePinUI() {
    const enabled = !!localStorage.getItem('mesh_pin');
    const el = document.getElementById('pin-text');
    if (el) el.textContent = enabled ? 'Выключить' : 'Включить';
    const btn = document.getElementById('btn-pin');
    if (btn) btn.classList.toggle('on', enabled);
  },

  lockIfNeeded() {
    if (localStorage.getItem('mesh_pin') && !sessionStorage.getItem('mesh_unlocked')) {
      this.pinStage = 'unlock';
      this.pinBuffer = [];
      this.renderPinInputs();
      document.getElementById('pin-overlay').style.display = 'flex';
    }
  },

  showOnboardingIfNeeded() {
    if (localStorage.getItem('mesh_onboard') === '1') return;
    document.getElementById('onboarding').style.display = 'flex';
    this.obStep = 0;
    this.renderOnboarding();
  },

  renderOnboarding() {
    const steps = [
      { title: 'Добро пожаловать!', text: 'IT Москва Колледж — расписание, оценки, замены и новости вашей группы.' },
      { title: 'Расписание', text: 'Листайте дни и сменяйте «Неделя/Сессия». Кнопка с домиком открывает экран «Мой день».' },
      { title: 'Оценки и напоминания', text: 'Включите напоминания — приложение предупредит за 10 минут до пары.' },
      { title: 'Готово!', text: 'Студенческий с QR-кодом, портфолио и обращения в деканат — в профиле.' }
    ];
    const s = steps[this.obStep];
    document.getElementById('ob-title').textContent = s.title;
    document.getElementById('ob-text').textContent = s.text;
    document.getElementById('ob-next').textContent = this.obStep === steps.length - 1 ? 'Начать' : 'Дальше';
    document.querySelectorAll('.ob-dot').forEach((d, i) => d.classList.toggle('active', i === this.obStep));
  },

  nextOnboarding() {
    if (this.obStep < 3) {
      this.obStep++;
      this.renderOnboarding();
    } else {
      localStorage.setItem('mesh_onboard', '1');
      document.getElementById('onboarding').style.display = 'none';
    }
  },

  setupInstall() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredInstall = e;
      const row = document.getElementById('install-row');
      if (row) row.style.display = 'flex';
    });
  },

  installApp() {
    if (!this.deferredInstall) return;
    this.deferredInstall.prompt();
    this.deferredInstall.userChoice.then(() => {
      const row = document.getElementById('install-row');
      if (row) row.style.display = 'none';
    });
  },

  showStudentCard() {
    const modal = document.getElementById('student-card-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.getElementById('sc-qr').innerHTML = '<p class="src-hint">Загрузка…</p>';

    API.getStudentCard().then(data => {
      if (!data || !data.svg) {
        document.getElementById('sc-qr').innerHTML = '<p class="src-hint">QR недоступен офлайн</p>';
        return;
      }
      document.getElementById('sc-name').textContent = data.fio;
      document.getElementById('sc-group').textContent = 'Группа: ' + data.group;
      document.getElementById('sc-speciality').textContent = data.speciality;
      document.getElementById('sc-qr').innerHTML = data.svg;
    });
  },

  closeStudentCard() {
    const modal = document.getElementById('student-card-modal');
    if (modal) modal.style.display = 'none';
  },

  loadGrades() {
    this.showSkeleton('grades-list');
    Promise.all([API.getGrades(), API.getRank()]).then(([data, rank]) => {
      if (data) this.renderGrades(data, rank);
    });
  },

  renderGrades(data, rank) {
    document.getElementById('avg-grade').textContent = data.average;
    document.getElementById('total-marks').textContent = data.total;
    this.renderGradesChart(data.subjects || []);
    const rankBanner = document.getElementById('grade-rank-banner');
    if (rankBanner) {
      if (rank && rank.place) {
        const top3 = rank.place <= 3;
        rankBanner.innerHTML = `<div class="rank-banner${top3 ? ' rank-top' : ''}">
          <span class="rank-icon">${top3 ? '🥇' : '🏅'}</span>
          <span>Место в группе: <b>${rank.place}</b> из ${rank.total}</span>
          <span class="rank-sub">Выше — ${rank.above} чел.</span>
        </div>`;
      } else {
        rankBanner.innerHTML = '';
      }
    }

    const container = document.getElementById('grades-list');
    this.renderTargetCalc(data.subjects || []);
    container.innerHTML = data.subjects.map(s => {
      const noteKey = 'mesh_note_' + encodeURIComponent(s.name);
      const note = localStorage.getItem(noteKey) || '';
      let hint = '', trend = '', forecast = '';
      if (s.marks && s.marks.length) {
        const vals = s.marks.map(m => m.value || m || 0);
        const sum = vals.reduce((a, b) => a + b, 0);
        const n = vals.length;
        const avg = sum / n;
        if (vals.length >= 3) {
          const recent = (vals.slice(-2).reduce((a, b) => a + b, 0)) / 2;
          const prev = vals.slice(0, -2).reduce((a, b) => a + b, 0) / (vals.length - 2 || 1);
          const diff = recent - prev;
          trend = Math.abs(diff) < 0.15
            ? 'Тренд: стабильно'
            : diff > 0 ? 'Тренд: балл растёт ↑' : 'Тренд: балл снижается ↓';
        }
        const totalN = Math.max(n, 10);
        const recentAvg = vals.length >= 2 ? (vals.slice(-2).reduce((a, b) => a + b, 0)) / 2 : avg;
        const projected = Math.min(5, (sum + recentAvg * (totalN - n)) / totalN);
        forecast = `Прогноз итоговой оценки: ≈${projected.toFixed(1)}`;
        if (avg >= 4.5) {
          hint = 'Отлично, оценка держится!';
        } else if (avg >= 4.0) {
          const need = Math.ceil(4.5 * (n + 1) - sum);
          hint = need <= 5 ? `Чтобы было 5 — получи ${Math.max(need, 1)} на следующей работе` : 'Для 5 нужно больше работ';
        } else {
          const need = Math.ceil(4.0 * (n + 1) - sum);
          hint = need <= 5 ? `Чтобы было 4 — получи ${Math.max(need, 1)}` : '4 с текущими результатами недостижима';
        }
      }
      let histo = '';
      if (s.marks && s.marks.length >= 3) {
        const vals = s.marks.map(m => Number(m.value || m || 0));
        const byMark = [0, 0, 0, 0, 0, 0];
        vals.forEach(v => { if (v >= 1 && v <= 5) byMark[v]++; });
        const mx = Math.max(...byMark.slice(1));
        if (mx) {
          histo = `<div class="grade-histogram">${[2, 3, 4, 5].map(m => `
            <div class="hist-col">
              <div class="hist-bar" style="height:${Math.round((byMark[m] / mx) * 100)}%"></div>
              <div class="hist-num">${byMark[m]}</div>
            </div>`).join('')}<div class="hist-label">2 3 4 5</div></div>`;
        }
      }
      return `
      <div class="grade-item">
        <div class="grade-subject">${s.name}</div>
        <div class="grade-marks">
          ${s.marks.map(m => `
            <div class="grade-mark-item">
              <span class="mark mark-${m.value || m}">${m.value || m}</span>
              <div class="grade-mark-meta">
                ${m.date ? `<span class="grade-mark-date">${m.date}</span>` : ''}
                ${m.comment ? `<span class="grade-mark-comment">${m.comment}</span>` : ''}
              </div>
            </div>`).join('')}
        </div>
        <div class="grade-avg">${s.average}</div>
        ${histo ? `<div class="histogram-wrap">${histo}</div>` : ''}
        ${trend ? `<div class="grade-trend">${trend}</div>` : ''}
        ${forecast ? `<div class="grade-forecast">${forecast}</div>` : ''}
        ${hint ? `<div class="grade-hint">${hint}</div>` : ''}
        <button class="note-toggle" onclick="App.toggleNote('${s.name.replace(/'/g, "\\'")}')">📝 Заметка по предмету</button>
        <textarea class="note-area" id="note-${encodeURIComponent(s.name)}" data-subject="${s.name.replace(/'/g, "\\'")}" style="${note ? 'display:block' : 'display:none'}" placeholder="Заметка по предмету…">${note}</textarea>
      </div>`;
    }).join('');
  },

  renderTargetCalc(subjects) {
    const wrap = document.getElementById('target-calc');
    if (!wrap) return;
    const total = subjects.reduce((acc, s) => acc + (s.marks ? s.marks.length : 0), 0);
    const target = localStorage.getItem('mesh_target') || '4.5';
    wrap.innerHTML = `
      <div class="today-card">
        <div class="today-card-title">Калькулятор целевой оценки</div>
        <div class="today-menu-row"><span>Куда стремлюсь:</span>
          <select class="goal-input" style="min-width:110px" onchange="App.updateTargetCalc(this.value)">
            ${['4.5', '4.0', '4.75', '3.6'].map(v => `<option value="${v}" ${v === target ? 'selected' : ''}>${v}</option>`).join('')}
          </select>
        </div>
        <div class="replacement-note" id="target-result"></div>
      </div>`;
    this.updateTargetCalc(target, subjects, total);
  },

  updateTargetCalc(value, subjects, total) {
    const res = document.getElementById('target-result');
    if (!res) return;
    const list = subjects || (this.gradesCache && this.gradesCache.subjects) || [];
    let sum = 0, n = 0;
    list.forEach(s => { (s.marks || []).forEach(m => { sum += Number(m.value || m || 0); n++; }); });
    const target = parseFloat(value);
    localStorage.setItem('mesh_target', value);
    this.markPrefsChanged();
    if (!n) { res.textContent = 'Нет оценок — добавьте их в деканате.'; return; }
    const need = target * (n + 1) - sum;
    res.textContent = need <= 1
      ? `Одна «5» поднимет средний балл до целевого (сейчас ${(sum / n).toFixed(2)}).`
      : `Нужно ещё ≈${Math.ceil(need)} пятёрок, чтобы средний балл стал ${target} (сейчас ${(sum / n).toFixed(2)}).`;
  },

  toggleNote(subject) {
    const key = 'note-' + encodeURIComponent(subject);
    const area = document.getElementById(key);
    if (!area) return;
    const willShow = area.style.display === 'none';
    area.style.display = willShow ? 'block' : 'none';
    if (!willShow) {
      localStorage.setItem('mesh_note_' + encodeURIComponent(subject), area.value.trim());
    }
  },

  saveNotes() {
    document.querySelectorAll('.note-area').forEach(a => {
      localStorage.setItem('mesh_note_' + encodeURIComponent(a.dataset.subject), a.value.trim());
    });
  },

  renderGradesChart(subjects) {
    const container = document.getElementById('grades-chart');
    if (!container) return;
    if (!subjects.length) {
      container.innerHTML = '<div class="sub-note">Оцены пока не загружены</div>';
      return;
    }

    const width = 340, height = 150, top = 14, bottom = 26;
    const n = subjects.length;
    const slot = width / n;
    const barW = Math.min(54, slot * 0.62);
    const shortName = name => name.length > 9 ? name.slice(0, 8) + '…' : name;

    let bars = '';
    subjects.forEach((s, i) => {
      const avg = parseFloat(s.average) || 0;
      const h = Math.max(5, (avg / 5) * (height - top - bottom));
      const x = i * slot + (slot - barW) / 2;
      const y = height - bottom - h;
      const color = avg >= 4.5 ? '#22c55e' : avg >= 3.5 ? '#f59e0b' : '#ef4444';
      bars += `<rect x="${x}" y="${y}" width="${barW}" height="${h}" rx="6" fill="${color}"/>`;
      bars += `<text x="${x + barW / 2}" y="${y - 6}" font-size="12" font-weight="700" text-anchor="middle" fill="currentColor">${avg.toFixed(1)}</text>`;
      bars += `<text x="${x + barW / 2}" y="${height - 8}" font-size="11" text-anchor="middle" fill="currentColor" opacity="0.75">${shortName(s.name)}</text>`;
    });

    const avgAll = subjects.reduce((a, s) => a + (parseFloat(s.average) || 0), 0) / n;
    const avgY = Math.round(height - bottom - (avgAll / 5) * (height - top - bottom));

    container.innerHTML =
      `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="Успеваемость по предметам">
        ${bars}
        <line x1="0" y1="${avgY}" x2="${width}" y2="${avgY}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.8"/>
        <text x="${width - 4}" y="${avgY - 5}" font-size="10" fill="#2563eb" text-anchor="end">ср. ${avgAll.toFixed(2)}</text>
      </svg>`;
  },

  loadHomework() {
    this.showSkeleton('homework-content');
    API.getHomework().then(data => {
      if (data) this.renderHomework(data);
    });
  },

  renderHomework(items) {
    document.getElementById('hw-count').textContent = `${items.length} заданий`;
    const container = document.getElementById('homework-content');
    const favHw = JSON.parse(localStorage.getItem('mesh_fav_hw') || '[]');
    container.innerHTML = items.map((h, i) => {
      const fav = favHw.indexOf(h.task) !== -1;
      return `<div class="homework-card${h.urgent ? ' homework-card--urgent' : h.soon ? ' homework-card--soon' : ''}">
        <div class="hw-badge">${h.badge}</div>
        <div class="hw-subject">${h.subject}</div>
        <div class="hw-task">${h.task}</div>
        <div class="hw-deadline">${h.deadline} <span class="today-fav${fav ? ' fav-on' : ''}" onclick="App.toggleFavHw('${encodeURIComponent(h.task).replace(/'/g, "%27")}',this)">★</span></div>
      </div>`;
    }).join('');
  },

  toggleFavHw(task, el) {
    const key = 'mesh_fav_hw';
    let arr = JSON.parse(localStorage.getItem(key) || '[]');
    const t = decodeURIComponent(task);
    if (arr.indexOf(t) !== -1) arr = arr.filter(x => x !== t);
    else arr.push(t);
    localStorage.setItem(key, JSON.stringify(arr));
    this.markPrefsChanged();
    if (el) el.classList.toggle('fav-on');
  },

  loadProfile() {
    API.getProfile().then(data => {
      if (data) this.renderProfile(data);
    });

    Promise.all([API.getProfile(), API.getGrades(), API.getAttendance()]).then(([p, g, a]) => {
      if (p && g) this.renderAchievements({ ...p, average: g.average, total: g.total, attendance: a && a.attendance });
      const attEl = document.getElementById('stat-attendance');
      if (attEl && a && typeof a.attendance === 'number') {
        attEl.textContent = a.attendance + '%';
      }
    });
  },

  toggleLogins() {
    const block = document.getElementById('logins-block');
    if (!block) return;
    block.style.display = block.style.display === 'none' ? 'block' : 'none';
    if (block.style.display === 'block') this.loadLogins();
  },

  loadLogins() {
    const el = document.getElementById('logins-list');
    if (!el) return;
    API.getMyLogins().then(data => {
      const items = (data && data.logins) || [];
      el.innerHTML = (items.length
        ? items.map(l => `<div class="sub-note">${l.ts}${l.ip ? ' · ' + l.ip : ''}</div>`).join('')
        : '<div class="sub-note">Входов пока нет</div>');
    });
  },

  renderProfile(data) {
    document.getElementById('profile-name').textContent = data.name;
    document.getElementById('profile-class').textContent = `${data.course}`;
    document.getElementById('profile-avatar').textContent = data.initials;
    document.getElementById('info-school').textContent = data.school;
    document.getElementById('info-speciality').textContent = data.speciality || '—';
    document.getElementById('info-group').textContent = data.group;
    document.getElementById('info-forma').textContent = data.forma || '—';
    document.getElementById('info-address').textContent = data.address || '—';
    document.getElementById('info-teacher').textContent = data.advisor || '—';
    const phoneEl = document.getElementById('info-teacher-phone');
    if (phoneEl) {
      phoneEl.textContent = data.advisorPhone ? data.advisorPhone.replace('+7', '+7 ') : '—';
      phoneEl.href = data.advisorPhone ? 'tel:' + data.advisorPhone.replace(/[\s\-]/g, '') : 'tel:';
    }
    document.getElementById('stat-attendance').textContent = (data.attendance || 0) + '%';
    document.getElementById('stat-homework').textContent = (data.homeworkPercent || 0) + '%';

    this.updatePushUI();
    this.updatePinUI();

    const role = data.role || this.getRole();
    const teacherBtn = document.getElementById('btn-teacher-panel');
    const curatorBtn = document.getElementById('btn-curator-panel');
    if (teacherBtn) teacherBtn.style.display = role === 'teacher' ? 'flex' : 'none';
    if (curatorBtn) curatorBtn.style.display = role === 'curator' ? 'flex' : 'none';
  },

  renderAchievements(data) {
    const avg = parseFloat(data.average || data.avg || '0');
    document.getElementById('ach-avg').textContent = avg ? avg.toFixed(1) : '—';

    const scholarshipEl = document.getElementById('ach-scholarship');
    if (avg >= 4.5) {
      scholarshipEl.textContent = 'Повышенная';
      scholarshipEl.classList.add('ach-ok');
    } else if (avg >= 4.0) {
      scholarshipEl.textContent = 'Базовая';
      scholarshipEl.classList.add('ach-ok');
    } else if (avg > 0) {
      scholarshipEl.textContent = 'Нет';
      scholarshipEl.classList.remove('ach-ok');
    } else {
      scholarshipEl.textContent = '—';
    }

    const course = String(data.course || '').match(/\d/);
    const group = data.group || '';
    const seed = (group + data.name).split('').reduce((a, c) => a + c.charCodeAt(0), 0);
    const place = 1 + (seed % 25);
    document.getElementById('ach-rating').textContent = `${place} из 30`;

    const badge = document.getElementById('ach-badge');
    if (badge) {
      const chips = [];
      if (avg >= 4.5) chips.push(['🏆', 'Отличник учёбы']);
      else if (avg >= 4.0) chips.push(['🥇', 'Хорошист']);
      else if (avg > 0) chips.push(['🎯', 'Есть к чему стремиться']);

      const attendance = parseFloat(data.attendance || 0);
      if (attendance >= 95) chips.push(['⭐', 'Регулярное посещение']);
      else if (attendance >= 85) chips.push(['📅', 'Стабильное посещение']);

      const total = parseFloat(data.total || 0);
      if (total >= 40) chips.push(['🔥', 'Активный ученик']);

      const streak = parseInt(localStorage.getItem('mesh_streak') || '0', 10);
      if (streak >= 7) chips.push(['⚡', `Серия ${streak} дней`]);
      else if (streak >= 3) chips.push(['⚡', `Серия ${streak} дня`]);

      if (!chips.length) chips.push(['🦉', 'Добро пожаловать!']);

      badge.innerHTML = chips.map(c => `<span class="badge-chip">${c[0]} ${c[1]}</span>`).join('');
    }
  },

  exportScheduleCsv() {
    const dayNames = { mon: 'Понедельник', tue: 'Вторник', wed: 'Среда', thu: 'Четверг', fri: 'Пятница', sat: 'Суббота' };
    const stream = this.currentStream || 'alfa';
    const group = this.getGroup();
    const rows = [];
    rows.push(['День', 'Пара', 'Время', 'Предмет', 'Преподаватель', 'Аудитория']);
    let pending = 0;
    const finish = () => {
      if (pending > 0) return;
      let csv = '\ufeff' + rows.map(r => r.map(c => `"${String(c == null ? '' : c).replace(/"/g, '""')}"`).join(';')).join('\r\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `schedule_${group || 'student'}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
    };
    for (const day of ['mon', 'tue', 'wed', 'thu', 'fri', 'sat']) {
      pending++;
      API.getSchedule(day, stream, group).then(data => {
        const lessons = (data && data.lessons) || [];
        if (lessons.length) {
          rows.push([dayNames[day], '', '', '', '', '']);
          lessons.forEach(l => {
            rows.push([dayNames[day], l.pair || '', `${l.time_start || ''}–${l.time_end || ''}`, l.subject || '', l.teacher || '', l.room || '']);
          });
        }
        pending--;
        finish();
      }).catch(() => { pending--; finish(); });
    }
  },

  exportCalendar() {
    const days = ['mon', 'tue', 'wed', 'thu', 'fri'];
    const now = new Date();
    const diffToMonday = (now.getDay() + 6) % 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - diffToMonday);
    monday.setHours(0, 0, 0, 0);

    const ics = [];
    ics.push('BEGIN:VCALENDAR');
    ics.push('VERSION:2.0');
    ics.push('PRODID:-//MeshCollege PWA//RU');
    ics.push('CALSCALE:GREGORIAN');
    ics.push('BEGIN:VTIMEZONE');
    ics.push('TZID:Europe/Moscow');
    ics.push('BEGIN:STANDARD');
    ics.push('DTSTART:19701025T030000');
    ics.push('TZOFFSETFROM:+0400');
    ics.push('TZOFFSETTO:+0300');
    ics.push('RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU');
    ics.push('END:STANDARD');
    ics.push('END:VTIMEZONE');

    const toDateStr = (d) => {
      const p = (n) => ('0' + n).slice(-2);
      return '' + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
    };
    const escapeICS = (s) => (s || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');

    days.forEach((day, idx) => {
      const date = new Date(monday);
      date.setDate(monday.getDate() + idx);
      const slots = API.SLOT_TIMES[stream];
      const subjects = API.DAY_LESSONS[day] || [];
      const dateStr = toDateStr(date);

      slots.forEach((slot, si) => {
        const subj = subjects[si];
        if (!subj) return;

        const dtStart = dateStr + 'T' + slot.start.replace(':', '') + '00';
        const dtEnd = dateStr + 'T' + slot.end.replace(':', '') + '00';

        ics.push('BEGIN:VEVENT');
        ics.push('UID:' + Math.random().toString(36).substr(2) + '@meshcollege');
        ics.push('DTSTAMP:' + toDateStr(new Date()) + 'T000000Z');
        ics.push('DTSTART;TZID=Europe/Moscow:' + dtStart);
        ics.push('DTEND;TZID=Europe/Moscow:' + dtEnd);
        ics.push('SUMMARY:' + escapeICS(subj.subject + ' (' + slot.pair + ' пара)'));
        ics.push('LOCATION:' + escapeICS(subj.room));
        ics.push('DESCRIPTION:' + escapeICS('Преподаватель: ' + subj.teacher + '\\nПереход в ' + slot.transition));
        ics.push('END:VEVENT');
      });
    });

    ics.push('END:VCALENDAR');

    const blob = new Blob([ics.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'raspisanie.ics';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  updatePushUI() {
    const btn = document.getElementById('btn-push');
    const text = document.getElementById('push-text');
    if (!btn || !text) return;

    const on = localStorage.getItem('mesh_reminders') === 'on'
      && 'Notification' in window
      && Notification.permission === 'granted';
    text.textContent = on ? 'Выключить' : 'Включить';
    btn.classList.toggle('on', on);
  },

  togglePush() {
    if (!('Notification' in window)) {
      alert('Уведомления не поддерживаются этим браузером');
      return;
    }

    if (localStorage.getItem('mesh_reminders') === 'on') {
      localStorage.setItem('mesh_reminders', 'off');
      this.unsubscribePushClient();
      this.updatePushUI();
      return;
    }

    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        localStorage.setItem('mesh_reminders', 'on');
        ['mesh_nt_repl','mesh_nt_grade','mesh_nt_hw','mesh_nt_debts'].forEach(k => { if (!localStorage.getItem(k)) localStorage.setItem(k, 'on'); });
        this.ensurePushSubscription();
        this.updatePushUI();
        this.updateNotifUI();
        this.checkReminders(true);
      } else {
        alert('Разрешите уведомления в настройках браузера');
      }
    });
  },

  urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const output = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
    return output;
  },

  ensurePushSubscription() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    if (localStorage.getItem('mesh_reminders') !== 'on') return;
    navigator.serviceWorker.ready.then(reg => {
      return reg.pushManager.getSubscription().then(existing => {
        if (existing) {
          API.subscribePush(existing.toJSON());
          return;
        }
        return API.getVapidKey().then(res => {
          if (!res || !res.key) return;
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: this.urlBase64ToUint8Array(res.key)
          }).then(sub => {
            API.subscribePush(sub.toJSON());
          }).catch(() => {});
        });
      });
    }).catch(() => {});
  },

  unsubscribePushClient() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.ready.then(reg => {
      return reg.pushManager.getSubscription();
    }).then(sub => {
      if (sub) {
        API.unsubscribePush(sub.toJSON());
        return sub.unsubscribe().catch(() => {});
      }
    }).catch(() => {});
  },

  updateNotifUI() {
    [['btn-nt-repl','mesh_nt_repl'],['btn-nt-grade','mesh_nt_grade'],['btn-nt-hw','mesh_nt_hw'],['btn-nt-debts','mesh_nt_debts']].forEach(([id,key]) => {
      const el = document.getElementById(id);
      if (!el) return;
      const on = localStorage.getItem(key) === 'on';
      el.classList.toggle('on', on);
      const sp = el.querySelector('span');
      if (sp) sp.textContent = on ? 'Вкл' : 'Выкл';
    });
  },

  toggleNotif(key) {
    const next = localStorage.getItem(key) === 'on' ? 'off' : 'on';
    localStorage.setItem(key, next);
    if (next === 'on') {
      if (key === 'mesh_nt_repl') API.getReplacements().then(d => { if (d) localStorage.setItem('mesh_repl_sig', (d.date||'') + '|' + (d.items||[]).map(r => r.pair+':'+r.subject).join(';')); });
      if (key === 'mesh_nt_grade') API.getGrades().then(d => { if (d && d.subjects) localStorage.setItem('mesh_grade_sig', d.subjects.map(s => s.name+':'+(s.marks||[]).map(m => m.value||m).join(',')).join('|')); });
      if (key === 'mesh_nt_debts') API.getMyDebts().then(d => { if (d && d.debts) localStorage.setItem('mesh_debt_sig', d.debts.map(x => x.subject + ':' + (x.need||'')).join('|')); });
    }
    this.updateNotifUI();
  },

  _notifReady(key) {
    return localStorage.getItem('mesh_reminders') === 'on'
      && localStorage.getItem(key) === 'on'
      && 'Notification' in window
      && Notification.permission === 'granted'
      && Auth.isAuthenticated();
  },

  _ntNotify(title, body, screen) {
    try {
      const n = new Notification(title, { body, icon: '/icons/icon-192.png' });
      n.onclick = () => { window.focus(); n.close(); this.navigateTo(screen); };
    } catch (e) {}
  },

  checkReplacesNotif() {
    if (!this._notifReady('mesh_nt_repl')) return;
    API.getReplacements().then(d => {
      if (!d || !d.items || !d.items.length) return;
      const today = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'][new Date().getDay()];
      const mine = d.items.filter(r => (r.day || '').toLowerCase().includes(today.toLowerCase()));
      if (!mine.length) return;
      const sig = (d.date || '') + '|' + d.items.map(r => r.pair + ':' + r.subject).join(';');
      const prev = localStorage.getItem('mesh_repl_sig');
      localStorage.setItem('mesh_repl_sig', sig);
      if (prev === null || prev === sig) return;
      this._ntNotify('Замены', `Появились замены на сегодня: ${mine.length} шт.`, 'replacements');
    });
  },

  checkGradesNotif() {
    if (!this._notifReady('mesh_nt_grade')) return;
    API.getGrades().then(d => {
      if (!d || !d.subjects) return;
      const sig = d.subjects.map(s => s.name + ':' + (s.marks||[]).map(m => m.value||m).join(',')).join('|');
      const prev = localStorage.getItem('mesh_grade_sig');
      localStorage.setItem('mesh_grade_sig', sig);
      if (!prev || prev === sig) return;
      this._ntNotify('Новые оценки', 'В журнале появились обновления.', 'grades');
    });
  },

  checkDebtsNotif() {
    if (!this._notifReady('mesh_nt_debts')) return;
    API.getMyDebts().then(d => {
      if (!d || !Array.isArray(d.debts)) return;
      const sig = d.debts.map(x => x.subject + ':' + (x.need||'')).join('|');
      const prev = localStorage.getItem('mesh_debt_sig');
      localStorage.setItem('mesh_debt_sig', sig);
      if (!prev || prev === sig) return;
      this._ntNotify(d.count > 0 ? 'Мои долги' : 'Долгов нет', d.count > 0 ? `Долгов стало: ${d.count} шт.` : 'Все долги закрыты — отлично!', 'today');
    });
  },

  checkReminders() {
    if (!Auth.isAuthenticated()) return;
    if (localStorage.getItem('mesh_reminders') !== 'on') return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;

    const now = new Date();
    const dayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][now.getDay()];
    if (dayKey === 'sun') return;

    API.getSchedule(dayKey, this.currentStream || 'alfa', this.getGroup()).then(res => {
      if (!res || !res.lessons || !res.lessons.length) return;
      const nowMin = now.getHours() * 60 + now.getMinutes();
      for (const l of res.lessons) {
        const [sh, sm] = l.time_start.split(':').map(Number);
        const startMin = sh * 60 + sm;
        const diff = startMin - nowMin;
        if (diff > 0 && diff <= 10) {
          const key = l.pair + '-' + now.toDateString();
          if (localStorage.getItem('mesh_notified_' + key)) break;
          localStorage.setItem('mesh_notified_' + key, '1');
          try {
            const n = new Notification('IT Москва Колледж', {
              body: `Пара ${l.pair} · ${l.subject} — скоро, начало в ${l.time_start}`,
              icon: '/icons/icon-192.png'
            });
            if ('vibrate' in navigator) { navigator.vibrate([180, 80, 180]); }
            n.onclick = () => {
              window.focus();
              n.close();
              this.navigateTo('schedule');
            };
          } catch (e) {}
          break;
        }
      }
    });
  },

  startReminders() {
    setInterval(() => this.checkReminders(), 30000);
    setInterval(() => this.checkReplacesNotif(), 120000);
    setInterval(() => this.checkGradesNotif(), 180000);
    setInterval(() => this.checkDebtsNotif(), 180000);
    setInterval(() => this.checkHwDeadlines(), 1800000);
    this.checkHwDeadlines();
    this.checkReplacesNotif();
    this.checkGradesNotif();
    this.checkDebtsNotif();
  },

  checkHwDeadlines() {
    if (!Auth.isAuthenticated()) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    if (localStorage.getItem('mesh_nt_hw') !== 'on') return;
    API.getHomework().then(items => {
      if (!items || !items.length) return;
      const now = new Date();
      for (const h of items) {
        const mark = String(h.deadline || '');
        const m = mark.match(/(\d{1,2})\.(\d{2})\s*[—-]?\s*(\d{2}):?(\d{2})?/);
        if (!m) continue;
        const month = parseInt(m[2], 10) - 1;
        const day = parseInt(m[1], 10);
        const hr = parseInt(m[3] || '23', 10);
        const mn = parseInt(m[4] || '59', 10);
        const due = new Date(now.getFullYear(), month, day, hr, mn);
        if (isNaN(due.getTime()) || due.getTime() < now.getTime()) continue;
        const within = due.getTime() - now.getTime();
        if (within <= 0 || within > 48 * 3600 * 1000) continue;
        const soon = within <= 24 * 3600 * 1000;
        const label = soon ? 'Сегодня дедлайн' : 'Завтра дедлайн';
        const key = 'mesh_hw_note_' + encodeURIComponent(h.task) + '_' + due.toDateString() + (soon ? '_24' : '_48');
        if (localStorage.getItem(key)) continue;
        localStorage.setItem(key, '1');
        try {
          const n = new Notification(label, {
            body: `${h.subject}: ${h.task} — сдать до ${h.deadline}`,
            icon: '/icons/icon-512.png',
            badge: '/icons/icon-192.png'
          });
          if ('vibrate' in navigator) { navigator.vibrate([160, 70, 160]); }
          n.onclick = () => { window.focus(); this.navigateTo('homework'); };
        } catch (e) {}
      }
    });
  },

  startDigest() {
    setInterval(() => this.checkDigest(), 60000);
    this.checkDigest();
  },

  checkDigest() {
    const now = new Date();
    if (now.getHours() !== 19) return;
    if (localStorage.getItem('mesh_digest_' + now.toDateString())) return;
    if (!Auth.isAuthenticated()) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    const dayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][now.getDay()];
    const tomorrowKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][new Date(now.getTime() + 86400000).getDay()];
    Promise.all([API.getSchedule(tomorrowKey, this.currentStream || 'alfa', this.getGroup()), API.getHomework()]).then(([sched, hw]) => {
      localStorage.setItem('mesh_digest_' + now.toDateString(), '1');
      const lessons = (sched && sched.lessons || []).filter(l => l.subject && l.subject !== 'Окно');
      const deadlines = (hw || []).filter(h => /завтра|завтр/.test(h.badge || h.deadline || '')).length;
      let body = `Завтра пар: ${lessons.length}.`;
      if (lessons.length) body += ` Первая: ${lessons[0].subject} в ${lessons[0].time_start}.`;
      if (deadlines) body += ` Дедлайнов на завтра: ${deadlines}.`;
      else body += ' Дедлайнов нет.';
      try {
        const n = new Notification('Дайджест на завтра', { body: body, icon: '/icons/icon-192.png' });
        n.onclick = () => { window.focus(); this.navigateTo('today'); };
      } catch (e) {}
    });
  },

  loadMaterials() {
    const container = document.getElementById('materials-content');
    if (container) this.showSkeleton('materials-content');
    API.getMaterials().then(data => {
      if (data) this.renderMaterials(data.materials || []);
    });
  },

  renderMaterials(materials) {
    const container = document.getElementById('materials-content');
    if (!container) return;
    if (!materials.length) {
      container.innerHTML = '<div class="empty-state"><p>Материалов пока нет</p></div>';
      return;
    }
    container.innerHTML = materials.map((m, i) => {
      const favMat = JSON.parse(localStorage.getItem('mesh_fav_mat') || '[]');
      const fav = favMat.indexOf(m.subject) !== -1;
      return `
      <div class="mat-card ${fav ? 'mat-card--fav' : ''}">
        <div class="mat-subject" onclick="App.toggleMatSubject(${i})">
          <span>${m.subject}</span>
          <span class="mat-fav" onclick="event.stopPropagation();App.toggleFavMat('${m.subject.replace(/'/g, "\\'")}',this)">${fav ? '★' : '☆'}</span>
          <span class="mat-caret">▾</span>
        </div>
        <div id="mat-body-${i}" class="mat-body" style="display:none">
          ${(m.materials || []).length ? `
            <div class="mat-list-title">Материалы</div>
            ${m.materials.map(x => `
              <div class="mat-item">
                <span class="mat-type">${x.type || 'Материал'}</span>
                <span>${x.title}</span>
              </div>`).join('')}` : ''}
          ${(m.terms || []).length ? `
            <div class="mat-list-title">Термины — нажмите, чтобы открыть определение</div>
            ${m.terms.map((t, ti) => `
              <div class="term-item" onclick="App.flipTerm('term-${i}-${ti}')">
                <div class="term-word" id="term-${i}-${ti}">${t.term}</div>
                <div class="term-def" style="display:none">${t.def}</div>
              </div>`).join('')}` : ''}
        </div>
      </div>`;
    }).join('');
  },

  toggleFavMat(subject, el) {
    const key = 'mesh_fav_mat';
    let arr = JSON.parse(localStorage.getItem(key) || '[]');
    if (arr.indexOf(subject) !== -1) arr = arr.filter(x => x !== subject);
    else arr.push(subject);
    localStorage.setItem(key, JSON.stringify(arr));
    this.markPrefsChanged();
    if (el) {
      el.textContent = arr.indexOf(subject) !== -1 ? '★' : '☆';
      el.closest('.mat-card').classList.toggle('mat-card--fav');
    }
  },

  flipTerm(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const item = el.closest('.term-item');
    const def = item.querySelector('.term-def');
    if (!item.dataset.orig) item.dataset.orig = el.textContent;
    const flipped = def.style.display !== 'none';
    def.style.display = flipped ? 'none' : 'block';
    el.textContent = flipped ? item.dataset.orig : 'Скрыть определение';
  },

  toggleMatSubject(i) {
    const body = document.getElementById('mat-body-' + i);
    if (!body) return;
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
  },

  loadExtern() {
    const container = document.getElementById('extern-content');
    if (container) this.showSkeleton('extern-content');
    Promise.all([API.getClubs(), API.getLost(), API.getFaq(), API.getPolls(), API.getReferences(), API.getChat()]).then(([clubs, lost, faq, polls, refs, chat]) => {
      const html = [];

      if (Auth.isAuthenticated()) {
        html.push('<div class="extern-section-title">Чат группы</div>');
        const msgs = (chat && chat.messages) || [];
        const me = JSON.parse(localStorage.getItem('mesh_user') || '{}').name || '';
        html.push(`<div id="chat-box">${msgs.map(m => {
          const isMe = m.fio === me;
          return `<div class="chat-msg ${isMe ? 'chat-msg--me' : ''}">
            <div class="chat-msg-head"><b>${m.fio}</b><span class="chat-msg-ts">${m.ts || ''}</span></div>
            <div class="chat-msg-text">${String(m.text || '').replace(/</g, '&lt;')}</div>
          </div>`;
        }).join('') || '<div class="sub-note">Сообщений пока нет</div>'}
        </div>`);
        html.push('<div class="chat-input-row"><input id="chat-input" class="goal-input" placeholder="Написать в чат группы..." onkeydown="if(event.key===\'Enter\')App.sendChat()"><button class="btn-primary chat-send" onclick="App.sendChat()">➤</button></div>');
      }

      html.push('<div class="extern-section-title">Кружки и секции</div>');
      const clubList = (clubs && clubs.clubs) || [];
      if (!clubList.length) html.push('<div class="sub-note">Кружков пока нет</div>');
      clubList.forEach(c => {
        html.push(`<div class="replacement-card">
          <div class="replacement-subject">${c.name} <span class="ticket-pill ticket-${(c.status || '').includes('набор') ? 'new' : 'done'}">${c.status || ''}</span></div>
          <div class="replacement-room">${c.schedule} · ${c.room}</div>
          <div class="replacement-note">Руководитель: ${c.coach}</div>
        </div>`);
      });

      html.push('<div class="extern-section-title">Потерянные вещи</div>');
      const lostList = (lost && lost.lost) || [];
      if (!lostList.length) html.push('<div class="sub-note">Объявлений нет</div>');
      lostList.forEach(l => {
        html.push(`<div class="replacement-card">
          <div class="replacement-subject">${l.item}</div>
          <div class="replacement-room">${l.place || '—'} · ${l.date || ''}</div>
          <div class="replacement-note">${l.contact || ''}${l.status ? ' · ' + l.status : ''}</div>
        </div>`);
      });

      html.push('<div class="extern-section-title">Частые вопросы</div>');
      const faqList = (faq && faq.faq) || [];
      if (!faqList.length) html.push('<div class="sub-note">FAQ пуст</div>');
      faqList.forEach((f, i) => {
        html.push(`<div class="faq-item">
          <div class="faq-q" onclick="App.toggleFaq(${i})">${f.q}</div>
          <div class="faq-a" id="faq-a-${i}" style="display:none">${f.a}</div>
        </div>`);
      });

      const pollList = (polls && polls.polls) || [];
      if (pollList.length) {
        html.push('<div class="extern-section-title">Опросы колледжа</div>');
        pollList.forEach((p, i) => {
          const voted = p.my !== null && p.my !== undefined;
          html.push(`<div class="prep-card">
            <div class="replacement-subject">${p.question}${p.closed ? ' <span class="ticket-pill ticket-done">Закрыт</span>' : ''}</div>
            ${p.options.map((o, oi) => {
              const pct = p.total ? Math.round((p.votes[oi] || 0) / p.total * 100) : 0;
              return `<div class="poll-option" onclick="App.votePoll('${p.id}',${oi})">
                <span>${o}</span>
                ${voted ? `<span class="today-price">${pct}% (${p.votes[oi] || 0})</span>` : ''}
                ${voted && p.my === oi ? '<span class="ticket-pill ticket-new">Вы</span>' : ''}
              </div>`;
            }).join('')}
            <div class="replacement-note">Всего голосов: ${p.total}${voted ? ' · Спасибо за участие!' : ' · Нажмите, чтобы проголосовать'}</div>
          </div>`);
        });
      }

      const r = (refs && refs.library) ? refs : (refs || {});
      if (r.library || r.medpoint || r.wifi || r.phones) {
        html.push('<div class="extern-section-title">Справочники колледжа</div>');
        const phones = (r.phones || []).map(p => `<div class="today-menu-row"><span>${p.name}</span><span class="today-price">${p.phone}</span></div>`).join('');
        const wifi = (r.wifi || []).map(w => `<div class="replacement-note">📶 ${w.name} — логин: ${w.login}${w.note ? ' (' + w.note + ')' : ''}</div>`).join('');
        html += `<div class="prep-card">
          ${r.library ? `<div class="replacement-subject">Библиотека</div>${(r.library.hours || []).map(h => `<div class="replacement-note">${h}</div>`).join('')}<div class="replacement-note">📍 ${r.library.address || ''}</div>` : ''}
          ${r.medpoint ? `<div class="replacement-subject">Медпункт</div>${(r.medpoint.hours || []).map(h => `<div class="replacement-note">${h}</div>`).join('')}<div class="replacement-note">☎ ${r.medpoint.phone || ''} · 📍 ${r.medpoint.address || ''}</div>` : ''}
          ${wifi}
          ${phones}
        </div>`;
      }

      if (container) container.innerHTML = html.join('');
    });
  },

  votePoll(id, option) {
    API.votePoll(id, option).then(res => {
      if (!res) return;
      const data = res.data || res;
      if (res.ok) this.loadExtern();
      else alert((data && data.detail) || 'Не удалось проголосовать');
    });
  },

  sendChat() {
    const input = document.getElementById('chat-input');
    if (!input || !input.value.trim()) return;
    if (navigator.onLine === false) {
      this.queueOffline('chat', { text: input.value.trim() });
      input.value = '';
      this.loadChat();
      return;
    }
    API.postChat(input.value.trim()).then(() => {
      input.value = '';
      this.loadChat();
    });
  },

  loadChat() {
    if (this.currentScreen !== 'extern') return;
    API.getChat().then(data => {
      const box = document.getElementById('chat-box');
      if (!box || this.currentScreen !== 'extern') return;
      const msgs = (data && data.messages) || [];
      const me = JSON.parse(localStorage.getItem('mesh_user') || '{}').name || '';
      box.innerHTML = msgs.map(m => {
        const isMe = m.fio === me;
        return `<div class="chat-msg ${isMe ? 'chat-msg--me' : ''}">
          <div class="chat-msg-head"><b>${m.fio}</b><span class="chat-msg-ts">${m.ts || ''}</span></div>
          <div class="chat-msg-text">${String(m.text || '').replace(/</g, '&lt;')}</div>
        </div>`;
      }).join('') || '<div class="sub-note">Сообщений пока нет</div>';
    });
  },

  startChatPolling() {
    if (this._chatTimer) { clearInterval(this._chatTimer); this._chatTimer = null; }
    this._chatTimer = setInterval(() => this.loadChat(), 15000);
  },

  stopChatPolling() {
    if (this._chatTimer) { clearInterval(this._chatTimer); this._chatTimer = null; }
  },

  toggleFaq(i) {
    const a = document.getElementById('faq-a-' + i);
    if (a) a.style.display = a.style.display === 'none' ? 'block' : 'none';
  },

  loadPrep() {
    const container = document.getElementById('prep-content');
    if (container) this.showSkeleton('prep-content');
    API.getExams().then(data => {
      const exams = (data && data.exams) || [];
      const subjects = exams.filter(e => e.subject).map(e => e.subject);
      this.renderPrep(exams, subjects);
    });
  },

  renderPrep(exams, subjects) {
    const container = document.getElementById('prep-content');
    if (!container) return;
    const list = subjects.length ? subjects : ['Математика', 'Информатика'];
    const total = list.length * 4;
    let done = 0;
    const rows = list.map(s => {
      const saved = JSON.parse(localStorage.getItem('mesh_check_' + encodeURIComponent(s)) || '[]');
      const topics = ['Конспекты и лекции', 'Практические работы', 'Типовые задачи', 'Билеты прошлых лет'];
      done += saved.length;
      return `<div class="prep-subject">${s}</div>${topics.map((t, ti) => {
        const checked = saved.includes(t);
        return `<div class="prep-check" onclick="App.togglePrepItem('${s.replace(/'/g, "\\'")}',${ti},this)">
          <span class="prep-box${checked ? ' checked' : ''}"></span><span>${t}</span>
        </div>`;
      }).join('')}`;
    }).join('');

    const pct = total ? Math.round(done / total * 100) : 0;
    const goals = JSON.parse(localStorage.getItem('mesh_goals') || '[]');
    container.innerHTML = `
      <div class="prep-card">
        <div class="replacement-subject">Мои цели на семестр</div>
        <div class="goal-add-row">
          <input class="text-field goal-input" id="goal-input" placeholder="Цель, например «Сдать ЕГЭ-демо по информатике»">
          <button class="btn-secondary" onclick="App.addGoal()">Добавить</button>
        </div>
        ${goals.map((g, gi) => `
          <div class="prep-check" onclick="App.toggleGoal(${gi},this)">
            <span class="prep-box${g.done ? ' checked' : ''}"></span><span>${g.text}</span>
            <span class="goal-del" onclick="event.stopPropagation();App.removeGoal(${gi})">✕</span>
          </div>`).join('') || '<div class="sub-note">Целей пока нет</div>'}
      </div>
      <div class="prep-card">
        <div class="replacement-subject">Прогресс подготовки</div>
        <div class="prep-bar"><div class="prep-bar-fill" style="width:${pct}%"></div></div>
        <div class="replacement-note">${done} из ${total} пунктов выполнено (${pct}%)</div>
      </div>
      ${exams.length ? `<div class="prep-card"><div class="replacement-subject">Ближайшие экзамены</div>${exams.map(e => `<div class="today-menu-row"><span>${e.subject} — ${e.form}</span><span class="today-price">${e.date}</span></div>`).join('')}</div>` : ''}
      <div class="extern-section-title">Таймер фокуса (Pomodoro 25 мин)</div>
      <div class="pomo-card">
        <div class="pomo-time" id="pomo-time">25:00</div>
        <div class="pomo-controls">
          <button class="btn-secondary" onclick="App.togglePomo()" id="pomo-btn">Старт</button>
          <button class="btn-secondary" onclick="App.resetPomo()">Сброс</button>
        </div>
      </div>
      <div class="prep-list">${rows}</div>`;
  },

  addGoal() {
    const input = document.getElementById('goal-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    const goals = JSON.parse(localStorage.getItem('mesh_goals') || '[]');
    goals.push({ text, done: false });
    localStorage.setItem('mesh_goals', JSON.stringify(goals));
    this.markPrefsChanged();
    this.loadPrep();
  },

  toggleGoal(i, el) {
    const goals = JSON.parse(localStorage.getItem('mesh_goals') || '[]');
    goals[i].done = !goals[i].done;
    localStorage.setItem('mesh_goals', JSON.stringify(goals));
    this.markPrefsChanged();
    if (el) el.querySelector('.prep-box').classList.toggle('checked');
  },

  removeGoal(i) {
    const goals = JSON.parse(localStorage.getItem('mesh_goals') || '[]');
    goals.splice(i, 1);
    localStorage.setItem('mesh_goals', JSON.stringify(goals));
    this.markPrefsChanged();
    this.loadPrep();
  },

  togglePrepItem(subject, ti, el) {
    const key = 'mesh_check_' + encodeURIComponent(subject);
    const topics = ['Конспекты и лекции', 'Практические работы', 'Типовые задачи', 'Билеты прошлых лет'];
    let saved = JSON.parse(localStorage.getItem(key) || '[]');
    const t = topics[ti];
    if (saved.includes(t)) saved = saved.filter(x => x !== t);
    else saved.push(t);
    localStorage.setItem(key, JSON.stringify(saved));
    if (el) el.querySelector('.prep-box').classList.toggle('checked');
    this.loadPrep();
  },

  popupomo: null,
  pomoRemaining: 25 * 60,

  togglePomo() {
    const btn = document.getElementById('pomo-btn');
    if (this.popupomo) {
      clearInterval(this.popupomo);
      this.popupomo = null;
      if (btn) btn.textContent = 'Продолжить';
      return;
    }
    this.popupomo = setInterval(() => {
      this.pomoRemaining--;
      if (this.pomoRemaining <= 0) {
        clearInterval(this.popupomo);
        this.popupomo = null;
        this.pomoRemaining = 25 * 60;
        const el = document.getElementById('pomo-time');
        if (el) el.textContent = '25:00';
        try {
          const n = new Notification('IT Москва Колледж', { body: 'Перерыв! Отдохни 5 минут.', icon: '/icons/icon-192.png' });
          if ('vibrate' in navigator) navigator.vibrate([200, 100, 200]);
        } catch (e) {}
        if (btn) btn.textContent = 'Старт';
        return;
      }
      const el = document.getElementById('pomo-time');
      if (el) {
        const m = Math.floor(this.pomoRemaining / 60);
        const s = this.pomoRemaining % 60;
        el.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
      }
    }, 1000);
    if (btn) btn.textContent = 'Пауза';
  },

  resetPomo() {
    if (this.popupomo) { clearInterval(this.popupomo); this.popupomo = null; }
    this.pomoRemaining = 25 * 60;
    this.toggle_clear = null;
    const el = document.getElementById('pomo-time');
    if (el) el.textContent = '25:00';
    const btn = document.getElementById('pomo-btn');
    if (btn) btn.textContent = 'Старт';
  },

  loadTeacher() {
    const container = document.getElementById('teacher-content');
    const groupEl = document.getElementById('teacher-group');
    if (container) this.showSkeleton('teacher-content');
    API.teacherAttendance().then(data => {
      if (!data) { if (container) container.innerHTML = '<div class="empty-state"><p>Нет данных</p></div>'; return; }
      if (data) {
        this.teacherGroups = data.groups || (data.group ? [data.group] : []);
        if (this.teacherGroups.length > 1 && !this.teacherGroup) this.teacherGroup = this.teacherGroups[0];
      }
      const groups = this.teacherGroups || (data ? [data.group] : []);
      const groupSelector = groups.length > 1 ? `
        <div class="field-label">Группа</div>
        <select class="text-field" id="tg-select" onchange="App.switchTeacherGroup(this.value)">
          ${groups.map(g => `<option value="${this.esc(g)}" ${g === data.group ? 'selected' : ''}>${this.esc(g)}</option>`).join('')}
        </select>` : '';
      if (groupEl) groupEl.textContent = 'Группа ' + (data && data.group ? data.group : '');
      const marks = data.days || [];
      if (container) container.innerHTML = `
        ${groupSelector}
        <div class="attendance-summary">
          <div class="grade-stat"><div class="grade-stat-value">${data.attendance}%</div><div class="grade-stat-label">Посещаемость группы</div></div>
        </div>
        ${marks.length ? `<div class="sub-note">Отмечено дней: ${marks.join(', ')}</div>` : ''}
        <div class="screen-title">Отметить за день</div>
        <label class="field-label">Дата</label>
        <input class="text-field" type="date" id="tea-date">
        <div id="tea-rows"></div>
        <div class="row-space-top" id="tea-actions">
          <button class="btn-secondary profile-action-btn" onclick="App.teacherAddRow()">+ Добавить предмет</button>
          <button class="btn-secondary profile-action-btn" onclick="App.saveTeacherMarks()">Сохранить отметки</button>
        </div>
        <div class="ticket-status" id="tea-status"></div>
        <div class="screen-title">Журнал оценок</div>
        <div class="sub-note">Выберите предмет и выставляйте оценки прямо в журнал группы.</div>
        <div class="row-space-top">
          <button class="btn-secondary profile-action-btn" onclick="App.exportJournal()">Скачать журнал (CSV)</button>
        </div>
        <label class="field-label">Предмет</label>
        <select class="text-field" id="tj-subject" onchange="App.renderJournal()"></select>
        <div id="tj-rows"></div>
        <div class="ticket-status" id="tj-status"></div>
        <div class="screen-title">Контроль ДЗ</div>
        <div class="sub-note">Отмечайте сдачу заданий ваших предметов и ставьте черновик оценки.</div>
        <div id="tea-hw"></div>`;
      this.teacherAddRow(true);
      API.teacherJournal().then(j => {
        this.journalData = j;
        const subjEl = document.getElementById('tj-subject');
        if (subjEl && j) {
          subjEl.innerHTML = (j.subjects || []).map(s => `<option value="${this.esc(s)}">${this.esc(s)}</option>`).join('') || '<option>Математика</option>';
          this.renderJournal();
        }
      });
      API.getTeacherSchedule().then(ts => {
        const schedEl = document.getElementById('tea-schedule');
        if (!schedEl || !ts) return;
        const dayNames = { mon: 'Понедельник', tue: 'Вторник', wed: 'Среда', thu: 'Четверг', fri: 'Пятница', sat: 'Суббота' };
        const groups = ts.groups || [{ group: this.teacherGroup || (ts.group || ''), days: ts.days || [] }];
        schedEl.innerHTML = groups.map(g => `
          <div class="screen-title" style="font-size:14px;margin-top:6px">Расписание — ${this.esc(g.group)}</div>
          ${(g.days || []).map(d => `
            <div class="sub-note">${dayNames[d.day] || d.day}</div>
            ${(d.lessons || []).map(l => `
              <div class="replacement-card">
                <div class="replacement-subject">${l.subject}</div>
                <div class="replacement-room">${l.room || ''}</div>
              </div>`).join('')}`).join('') || '<div class="sub-note">Пар сегодня нет</div>'}`).join('');
      });
      this.loadTeacherHomework();
    });
  },

  loadTeacherHomework() {
    const wrap = document.getElementById('tea-hw');
    if (!wrap) return;
    API.teacherHomework().then(data => {
      if (!data) { wrap.innerHTML = '<div class="sub-note">Нет данных</div>'; return; }
      const items = data.items || [];
      const students = data.students || [];
      if (!items.length) { wrap.innerHTML = '<div class="sub-note">Пока нет заданий по вашим предметам</div>'; return; }
      wrap.innerHTML = items.map(item => {
        const checks = item.checks || {};
        const doneCount = students.filter(s => checks[s.login] && checks[s.login].done).length;
        return `<div class="hw-item">
          <div class="hw-item-head"><b>${this.esc(item.subject)}</b><span class="ticket-pill">${this.esc(item.deadline || '')}</span></div>
          <div class="hw-item-task">${this.esc(item.task)}</div>
          <div class="sub-note">Сдано: ${doneCount} из ${students.length}</div>
          <div class="hw-students">${students.map(s => {
            const st = checks[s.login] || {};
            return `<div class="hw-student">
              <label class="hw-check"><input type="checkbox" ${st.done ? 'checked' : ''} onchange="App.setTeacherHw('${item.id}','${s.login}',this.checked)"><span>${this.esc(s.fio)}</span></label>
              <select class="goal-input" style="min-width:70px" onchange="App.setTeacherHwGrade('${item.id}','${s.login}',this.value)">
                <option value="">—</option>
                ${[2,3,4,5].map(g => `<option value="${g}" ${String(st.grade) === String(g) ? 'selected' : ''}>${g}</option>`).join('')}
              </select>
            </div>`;
          }).join('')}</div>
        </div>`;
      }).join('');
    });
  },

  setTeacherHw(itemId, login, done) {
    API.teacherHomeworkCheck({ item_id: itemId, login, done, grade: null }).then(res => {
      if (res && res.ok) this.loadTeacherHomework();
    });
  },

  setTeacherHwGrade(itemId, login, value) {
    const done = true;
    API.teacherHomeworkCheck({ item_id: itemId, login, done, grade: value ? parseInt(value, 10) : null }).then(res => {
      if (res && res.ok) this.loadTeacherHomework();
    });
  },

  teacherAddRow(first) {
    const rows = document.getElementById('tea-rows');
    if (!rows) return;
    const row = document.createElement('div');
    row.className = 'tea-row';
    row.innerHTML = `
      <input class="text-field tea-subj" placeholder="Предмет" ${first ? 'value="Информатика"' : ''}>
      <select class="text-field tea-status">
        <option value="present">Был(а)</option>
        <option value="late">Опоздал(а)</option>
        <option value="absent">Отсутствовал(а)</option>
      </select>
      <button class="icon-btn" onclick="this.parentNode.remove()">✕</button>`;
    rows.appendChild(row);
  },

  saveTeacherMarks() {
    const dateEl = document.getElementById('tea-date');
    const statusEl = document.getElementById('tea-status');
    if (!dateEl) return;
    let date = dateEl.value;
    if (date) {
      const [y, m, d] = date.split('-');
      date = d + '.' + m;
    }
    const lessons = [];
    document.querySelectorAll('#tea-rows .tea-row').forEach(row => {
      const subj = row.querySelector('.tea-subj').value.trim();
      const status = row.querySelector('.tea-status').value;
      if (subj) lessons.push({ subject: subj, status });
    });
    if (!lessons.length) { if (statusEl) statusEl.textContent = 'Добавьте хотя бы один предмет'; return; }
    API.saveTeacherAttendance({ date, lessons }).then(res => {
      if (statusEl) statusEl.textContent = (res && res.ok) ? 'Сохранено! ' + (res.data && res.data.date || '') : 'Ошибка сохранения';
      if (res && res.ok) this.loadTeacher();
    });
  },

  renderJournal() {
    const rows = document.getElementById('tj-rows');
    const subjEl = document.getElementById('tj-subject');
    if (!rows || !subjEl) return;
    const j = this.journalData;
    if (!j || !j.students || !j.students.length) {
      rows.innerHTML = '<div class="sub-note">Студентов в группе пока нет</div>';
      return;
    }
    const subject = subjEl.value;
    const today = new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
    rows.innerHTML = (j.students || []).map(s => {
      const avg = this.subjectAvg(s.marks || [], subject);
      return `<div class="tj-row">
        <div class="tj-name">${this.esc(s.fio)}<em>${avg ? 'ср. ' + avg : 'ещё нет оценок'}</em></div>
        <div class="tj-controls">
          <select class="text-field tj-value" data-login="${this.esc(s.login)}">${[5,4,3,2].map(v => `<option value="${v}">${v}</option>`).join('')}</select>
          <input class="text-field tj-date" data-login="${this.esc(s.login)}" placeholder="ДД.ММ" value="${today}">
          <button class="btn-primary chat-send tj-save" data-login="${this.esc(s.login)}" onclick="App.teacherPutGrade(this)">✓</button>
        </div>
      </div>`;
    }).join('') || '<div class="sub-note">Студентов нет</div>';
  },

  subjectAvg(marks, subject) {
    const vals = marks.filter(m => m.subject === subject).map(m => Number(m.value)).filter(v => v >= 1 && v <= 5);
    if (!vals.length) return '';
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  },

  switchTeacherGroup(group) {
    this.teacherGroup = group;
    this.loadTeacher();
  },

  exportJournal() {
    const a = document.createElement('a');
    a.href = '/api/teacher/journal/export' + API.teacherGroupQS();
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  },

  exportGrades() {
    const a = document.createElement('a');
    a.href = '/api/grades/export';
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  },

  async shareProgress() {
    const user = JSON.parse(localStorage.getItem('mesh_user') || '{}');
    try {
      const [grades, rank, attendance] = await Promise.all([
        API.getGrades(), API.getRank(), API.getAttendance()
      ]);
      const avg = (grades && grades.average) || '—';
      const total = (grades && grades.total) || 0;
      const place = (rank && rank.place) || null;
      const att = attendance && typeof attendance.attendance === 'number' ? attendance.attendance : null;
      const blob = await this.buildProgressImage({ user, avg, total, place, att, subjects: (grades && grades.subjects) || [] });
      const file = new File([blob], 'progress.png', { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({
            files: [file],
            title: 'Мои успехи',
            text: `${user.name || ''}: средний балл ${avg}`
          });
          return;
        } catch (e) { if (e && e.name === 'AbortError') return; }
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'progress.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch (e) {
      console.error(e);
    }
  },

  buildProgressImage({ user, avg, total, place, att, subjects }) {
    return new Promise(resolve => {
      const W = 1080, H = 1080;
      const c = document.createElement('canvas');
      c.width = W; c.height = H;
      const ctx = c.getContext('2d');
      const cs = getComputedStyle(document.documentElement);
      const accent = (cs.getPropertyValue('--primary') || '#5b5bd6').trim() || '#5b5bd6';

      const grad = ctx.createLinearGradient(0, 0, W, H);
      grad.addColorStop(0, '#1e1b4b');
      grad.addColorStop(0.55, accent);
      grad.addColorStop(1, '#4c1d95');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      ctx.globalAlpha = 0.12;
      for (const [x, y, r] of [[180, 200, 260], [900, 320, 200], [780, 900, 300], [220, 880, 180]]) {
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff'; ctx.fill();
      }
      ctx.globalAlpha = 1;

      ctx.fillStyle = 'rgba(255,255,255,0.14)';
      this.roundRect(ctx, 70, 70, W - 140, H - 140, 48);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.35)';
      ctx.lineWidth = 3;
      this.roundRect(ctx, 70, 70, W - 140, H - 140, 48);
      ctx.stroke();

      ctx.textAlign = 'left';
      ctx.fillStyle = '#ffffff';
      ctx.font = '600 40px -apple-system, Segoe UI, sans-serif';
      ctx.fillText('IT Москва Колледж', 130, 175);

      ctx.font = '800 74px -apple-system, Segoe UI, sans-serif';
      const name = String(user.name || 'Студент');
      ctx.fillText(name.length > 20 ? name.slice(0, 19) + '…' : name, 130, 275);

      ctx.font = '500 34px -apple-system, Segoe UI, sans-serif';
      ctx.globalAlpha = 0.85;
      ctx.fillText((user.group ? 'Группа ' + user.group : '') + (place ? '  ·  ' + place + ' место в группе' : ''), 130, 335);
      ctx.globalAlpha = 1;

      const metrics = [
        ['Средний балл', String(avg)],
        ['Оценок', String(total)],
        ['Посещаемость', att != null ? att + '%' : '—']
      ];
      metrics.forEach((m, i) => {
        const x = 130 + i * 280;
        ctx.fillStyle = 'rgba(255,255,255,0.16)';
        this.roundRect(ctx, x, 400, 250, 210, 32); ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = '800 76px -apple-system, Segoe UI, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(m[1], x + 125, 510);
        ctx.font = '500 28px -apple-system, Segoe UI, sans-serif';
        ctx.globalAlpha = 0.8;
        ctx.fillText(m[0], x + 125, 565);
        ctx.globalAlpha = 1;
      });

      ctx.textAlign = 'left';
      ctx.font = '600 34px -apple-system, Segoe UI, sans-serif';
      ctx.fillText('Лучшие предметы', 130, 700);
      const top = subjects.slice().map(s => ({ n: s.name, a: parseFloat(s.average) || 0 }))
        .sort((a, b) => b.a - a.a).slice(0, 4);
      top.forEach((s, i) => {
        const y = 750 + i * 62;
        ctx.font = '500 32px -apple-system, Segoe UI, sans-serif';
        ctx.globalAlpha = 0.9;
        ctx.fillText(s.n.length > 26 ? s.n.slice(0, 25) + '…' : s.n, 130, y);
        ctx.textAlign = 'right';
        ctx.font = '700 32px -apple-system, Segoe UI, sans-serif';
        ctx.fillText(s.a.toFixed(2), W - 150, y);
        ctx.textAlign = 'left';
        ctx.globalAlpha = 1;
      });

      ctx.globalAlpha = 0.7;
      ctx.font = '500 26px -apple-system, Segoe UI, sans-serif';
      ctx.fillText('mesh-psi.vercel.app · ' + new Date().toLocaleDateString('ru-RU'), 130, H - 120);
      ctx.globalAlpha = 1;

      c.toBlob(b => resolve(b), 'image/png');
    });
  },

  roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  },

  burstConfetti(el) {
    const rect = el && el.getBoundingClientRect ? el.getBoundingClientRect() : { left: window.innerWidth / 2, top: window.innerHeight / 3, width: 0, height: 0 };
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#a855f7'];
    for (let i = 0; i < 26; i++) {
      const p = document.createElement('span');
      p.className = 'confetti-bit';
      const angle = Math.random() * Math.PI * 2;
      const dist = 60 + Math.random() * 130;
      p.style.left = cx + 'px';
      p.style.top = cy + 'px';
      p.style.background = colors[i % colors.length];
      p.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
      p.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
      p.style.animationDelay = (Math.random() * 0.12) + 's';
      document.body.appendChild(p);
      setTimeout(() => p.remove(), 1100);
    }
  },

  teacherPutGrade(btn) {
    const login = btn.dataset.login;
    const subjEl = document.getElementById('tj-subject');
    const valueEl = document.querySelector(`.tj-value[data-login="${login}"]`);
    const dateEl = document.querySelector(`.tj-date[data-login="${login}"]`);
    const status = document.getElementById('tj-status');
    if (!subjEl || !valueEl) return;
    API.teacherAddGrade({
      login, subject: subjEl.value, value: Number(valueEl.value), date: dateEl ? dateEl.value.trim() : ''
    }).then(res => {
      if (status) status.textContent = (res && res.ok) ? `Оценка ${valueEl.value} сохранена для ${login}` : ((res && res.data && res.data.detail) || 'Ошибка');
      if (res && res.ok) {
        this.haptic && this.haptic();
        this.burstConfetti(btn);
        API.teacherJournal().then(j => {
          this.journalData = j;
          this.renderJournal();
        });
      }
    });
  },

  loadCurator() {
    const container = document.getElementById('curator-content');
    const groupEl = document.getElementById('curator-group');
    if (container) this.showSkeleton('curator-content');
    API.curatorDashboard().then(data => {
      if (!data) { if (container) container.innerHTML = '<div class="empty-state"><p>Нет данных</p></div>'; return; }
      if (groupEl) groupEl.textContent = 'Группа ' + data.group;
      const labels = { 'new': 'Новое', 'in-progress': 'В работе', 'done': 'Готово' };
      if (container) container.innerHTML = `
        <div class="grades-summary">
          <div class="grade-stat"><div class="grade-stat-value">${data.students}</div><div class="grade-stat-label">Студентов</div></div>
          <div class="grade-stat"><div class="grade-stat-value">${data.attendance}%</div><div class="grade-stat-label">Посещаемость</div></div>
          <div class="grade-stat"><div class="grade-stat-value">${data.average || '—'}</div><div class="grade-stat-label">Средний балл</div></div>
        </div>
        ${(data.rating || []).length ? `
        <div class="screen-title">Рейтинг группы</div>
        <div class="rating-list">${data.rating.map((r, i) => `
          <div class="rating-row">
            <span class="rating-pos">${i + 1}</span>
            <span class="rating-name">${r.name}</span>
            <span class="rating-avg">${r.avg}</span>
          </div>`).join('')}</div>` : ''}
        <div class="row-space-top" style="display:flex;gap:8px">
          <button class="btn-secondary profile-action-btn" onclick="App.exportCuratorCsv()">Скачать CSV</button>
          <button class="btn-secondary profile-action-btn" onclick="window.print()">Печать</button>
        </div>
        <div class="screen-title">Сообщение группе</div>
        <input class="text-field" id="cur-ann-title" placeholder="Тема (например, «Собрание в пятницу»)">
        <textarea class="text-field" id="cur-ann-body" style="min-height:70px" placeholder="Текст объявления"></textarea>
        <button class="btn-secondary profile-action-btn" onclick="App.curatorSendAnnounce()">Отправить группе</button>
        <div class="ticket-status" id="cur-ann-status"></div>
        <div class="screen-title">Обращения группы (${data.tickets.length})</div>
        ${(data.tickets || []).map(t => `
          <div class="ticket-item">
            <div class="ticket-item-head"><b>${t.topic}</b><span class="ticket-pill ticket-${t.status}">${labels[t.status] || t.status}</span></div>
            <div class="ticket-item-text">${t.text}</div>
            <div class="ticket-item-meta">${t.name || ''} · ${t.created || ''}</div>
            ${t.answer ? `<div class="ticket-answer">Ваш ответ: ${t.answer}</div>` : ''}
            <div class="curator-reply-row">
              <select class="goal-input" style="min-width:130px" id="cur-ans-status-${t.id}">
                <option value="in-progress" ${t.status === 'in-progress' ? 'selected' : ''}>В работе</option>
                <option value="done" ${t.status === 'done' ? 'selected' : ''}>Готово</option>
              </select>
              <input class="goal-input" id="cur-ans-text-${t.id}" placeholder="Ответ студенту…" value="${t.answer || ''}">
              <button class="btn-primary chat-send" onclick="App.curatorReply('${t.id}')">➤</button>
            </div>
          </div>`).join('') || '<div class="sub-note">Обращений нет</div>'}`;
    });
  },

  exportCuratorCsv() {
    API.curatorDashboard().then(data => {
      if (!data) return;
      const rows = [
        ['Место', 'Студент', 'Средний балл'],
        ...(data.rating || []).map((r, i) => [String(i + 1), r.name, String(r.avg)])
      ];
      const csv = '\uFEFF' + rows.map(r => r.join(';')).join('\r\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `rating-${data.group}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  },

  curatorReply(id) {
    const status = document.getElementById('cur-ans-status-' + id);
    const text = document.getElementById('cur-ans-text-' + id);
    if (!status || !text) return;
    API.curatorReplyTicket(id, status.value, text.value.trim()).then(res => {
      if (res && res.ok) this.loadCurator();
    });
  },

  curatorSendAnnounce() {
    const title = document.getElementById('cur-ann-title');
    const body = document.getElementById('cur-ann-body');
    const status = document.getElementById('cur-ann-status');
    if (!title || !body) return;
    API.curatorAnnounce(title.value.trim(), body.value.trim()).then(res => {
      if (res && res.ok) {
        if (status) status.textContent = 'Отправлено! Студенты увидят новость и получат push.';
        title.value = '';
        body.value = '';
      } else {
        if (status) status.textContent = (res && res.data && res.data.detail) || 'Ошибка отправки';
      }
    });
  },

  showSpravka() {
    const modal = document.getElementById('spravka-modal');
    const body = document.getElementById('spravka-body');
    if (!modal || !body) return;
    API.getProfile().then(p => {
      const today = new Date();
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      const html = `
        <p class="spravka-line">СПРАВКА об обучении</p>
        <p>Выдана учащемуся <b>${p ? p.name : ''}</b>,</p>
        <p>обучающемуся на ${p && p.course ? p.course : '1 курсе'} по специальности «${p ? p.speciality : ''}»</p>
        <p>ГБПОУ ИТ Москвы, группа ${p ? p.group : ''}, форма обучения: ${p ? p.forma : ''}.</p>
        <p class="spravka-meta">Выдана ${today.getDate()} ${months[today.getMonth()]} ${today.getFullYear()} года для представления по месту требования.</p>`;
      body.innerHTML = html;
      const printArea = document.getElementById('print-area');
      if (printArea) {
        printArea.innerHTML = `<div class="print-doc"><h1>СПРАВКА об обучении</h1><p>Выдана учащемуся <b>${p ? p.name : ''}</b>, обучающемуся на ${p && p.course ? p.course : '1 курсе'} по специальности «${p ? p.speciality : ''}», ГБПОУ ИТ Москвы, группа ${p ? p.group : ''}, форма обучения: ${p ? p.forma : ''}.</p><p class="spravka-meta">Выдана ${today.getDate()} ${months[today.getMonth()]} ${today.getFullYear()} года для представления по месту требования.</p></div>`;
      }
      const shareBtn = document.getElementById('btn-share-report');
      if (shareBtn) shareBtn.style.display = 'none';
      modal.style.display = 'flex';
    });
  },

  showReport() {
    const modal = document.getElementById('spravka-modal');
    const body = document.getElementById('spravka-body');
    const title = document.getElementById('spravka-title');
    if (!modal || !body) return;
    Promise.all([API.getProfile(), API.getGrades(), API.getAttendance()]).then(([p, g, a]) => {
      const today = new Date();
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      const grades = (g && g.subjects) || [];
      const rows = grades.map(s => `<div class="today-menu-row"><span>${s.subject}</span><span class="today-price">${s.average ? parseFloat(s.average).toFixed(2) : '—'}</span></div>`).join('');
      body.innerHTML = `
        <p class="spravka-line">Отчёт об успеваемости</p>
        <p><b>${p ? p.name : ''}</b>, группа ${p ? p.group : ''}</p>
        ${grades.length ? `<div class="report-table">${rows}</div>` : '<p>Оценок пока нет</p>'}
        <p class="spravka-meta">Посещаемость: ${a && typeof a.attendance === 'number' ? a.attendance + '%' : '—'} · Средний балл: ${g && g.average ? g.average : '—'}</p>
        <p class="spravka-meta">Составлено ${today.getDate()} ${months[today.getMonth()]} ${today.getFullYear()} года</p>`;
      const printArea = document.getElementById('print-area');
      if (printArea) {
        printArea.innerHTML = `<div class="print-doc"><h1>Отчёт об успеваемости</h1><p><b>${p ? p.name : ''}</b>, группа ${p ? p.group : ''}.</p>${grades.map(s => `<p>${s.subject}: ${s.average ? parseFloat(s.average).toFixed(2) : '—'}</p>`).join('')}<p class="spravka-meta">Посещаемость: ${a && typeof a.attendance === 'number' ? a.attendance + '%' : '—'}</p></div>`;
      }
      if (title) title.textContent = 'Отчёт об успеваемости';
      const shareBtn = document.getElementById('btn-share-report');
      if (shareBtn) shareBtn.style.display = 'flex';
      modal.style.display = 'flex';
    });
  },

  shareReport() {
    const btn = document.getElementById('btn-share-report');
    if (btn) btn.textContent = 'Создаю ссылку…';
    API.createShare().then(res => {
      if (res && res.ok && res.url) {
        const url = window.location.origin + res.url;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(() => {
            if (btn) btn.textContent = 'Ссылка скопирована! ' + url;
          }).catch(() => this._flashShare(btn, url));
        } else {
          this._flashShare(btn, url);
        }
      } else {
        if (btn) btn.textContent = 'Не удалось создать ссылку';
      }
    });
  },

  _flashShare(btn, url) {
    if (!btn) return;
    const old = btn.textContent;
    btn.textContent = 'Ссылка: ' + url;
    btn.setAttribute('title', 'Скопируйте адрес вручную');
    setTimeout(() => { if (btn) btn.textContent = old; }, 8000);
  },

  openShareReport(payload) {
    const modal = document.getElementById('spravka-modal');
    const body = document.getElementById('spravka-body');
    const title = document.getElementById('spravka-title');
    if (!modal || !body) return;
    const grades = (payload && payload.subjects) || [];
    const rows = grades.map(s => `<div class="today-menu-row"><span>${this.esc(s.name)}</span><span class="today-price">${s.average || '—'}</span></div>`).join('');
    body.innerHTML = `
      <p class="spravka-line">Отчёт об успеваемости (по ссылке)</p>
      <p><b>${this.esc(payload.fio || '')}</b>, группа ${this.esc(payload.group || '')}</p>
      ${rows.length ? `<div class="report-table">${rows}</div>` : '<p>Оценок пока нет</p>'}
      <p class="spravka-meta">Создан ${this.esc(payload.created || '')} · Отмечено занятий: ${payload.attendance_marked || 0}</p>
      <p class="sub-note">Ссылка действует 24 часа. Поделитесь ею с родителями — они сами могут войти по ссылке без пароля.</p>`;
    if (title) title.textContent = 'Отчёт об успеваемости';
    modal.style.display = 'flex';
  },

  printSpravka() {
    this.closeModal(document.getElementById('spravka-modal'));
    const shareBtn = document.getElementById('btn-share-report');
    if (shareBtn) shareBtn.style.display = 'none';
    const title = document.getElementById('spravka-title');
    if (title) title.textContent = 'Справка об обучении';
    document.body.classList.add('print-spravka');
    setTimeout(() => {
      window.print();
      document.body.classList.remove('print-spravka');
    }, 150);
  },

  showPasswordModal() {
    const m = document.getElementById('password-modal');
    if (!m) return;
    document.getElementById('pw-current').value = '';
    document.getElementById('pw-new').value = '';
    document.getElementById('pw-confirm').value = '';
    const s = document.getElementById('pw-status');
    if (s) s.textContent = '';
    m.style.display = 'flex';
  },

  submitPasswordChange() {
    const cur = document.getElementById('pw-current').value;
    const nw = document.getElementById('pw-new').value;
    const cf = document.getElementById('pw-confirm').value;
    const s = document.getElementById('pw-status');
    if (!cur || !nw) { if (s) s.textContent = 'Заполните все поля'; return; }
    if (nw !== cf) { if (s) s.textContent = 'Новые пароли не совпадают'; return; }
    API.changePassword(cur, nw).then(res => {
      if (res && res.ok) {
        if (s) s.textContent = 'Пароль изменён';
        setTimeout(() => this.closeModal(document.getElementById('password-modal')), 900);
      } else if (s) {
        s.textContent = (res && res.data && res.data.detail) || 'Ошибка: проверьте текущий пароль';
      }
    });
  },

  closeModal(el) {
    if (el) el.style.display = 'none';
  },

  showFreeRooms() {
    API.getFreeRooms().then(data => {
      if (!data) return;
      const panel = document.getElementById('bells-panel');
      if (!panel) return;
      panel.appendChild(document.createElement('div')).outerHTML =
        `<div class="bells-rooms">
          <div class="bells-panel-title">Свободные аудитории · ${data.current || 'сейчас'}</div>
          ${data.free_all ? `<div class="sub-note">Все ${data.rooms.length} аудиторий свободны</div>`
            : data.rooms.length ? `<div class="rooms-chips">${data.rooms.map(r => `<span class="room-chip">${r}</span>`).join('')}</div>`
            : `<div class="sub-note">Свободных аудиторий сейчас нет</div>`}
        </div>`;
    });
  },

  favDishes() {
    try { return JSON.parse(localStorage.getItem('mesh_fav_dishes') || '[]'); } catch (e) { return []; }
  },

  loadPrefs() {
    if (!Auth.isAuthenticated()) return;
    API.getPrefs().then(res => {
      const srv = (res && res.prefs) || {};
      const merge = (key, localKey) => {
        const locArr = JSON.parse(localStorage.getItem(localKey) || '[]');
        const srvArr = Array.isArray(srv[syncKey(key)]) ? srv[syncKey(key)] : [];
        const merged = [...new Set([...locArr, ...srvArr])];
        localStorage.setItem(localKey, JSON.stringify(merged));
        return merged;
      };
      const syncKey = k => ({ favDishes: 'fav_dishes', favHw: 'fav_hw', favMat: 'fav_mat', goals: 'goals' }[k] || k);
      const remoteTheme = srv.theme;
      if (remoteTheme && ['light','dark','blue','auto'].includes(remoteTheme) && !localStorage.getItem('mesh_theme')) {
        localStorage.setItem('mesh_theme', remoteTheme);
        this.applyTheme();
      }
      if (srv.target && !localStorage.getItem('mesh_target')) {
        localStorage.setItem('mesh_target', String(srv.target));
      }
      this.prefs = {
        fav_dishes: merge('favDishes', 'mesh_fav_dishes'),
        fav_hw: merge('favHw', 'mesh_fav_hw'),
        fav_mat: merge('favMat', 'mesh_fav_mat'),
        goals: merge('goals', 'mesh_goals'),
        theme: localStorage.getItem('mesh_theme') || 'light',
        target: localStorage.getItem('mesh_target') || '4.5'
      };
      this.syncPrefsToServer();
    });
  },

  markPrefsChanged() {
    const read = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || '[]'); } catch (e) { return d || []; } };
    this.prefs = {
      fav_dishes: read('mesh_fav_dishes'),
      fav_hw: read('mesh_fav_hw'),
      fav_mat: read('mesh_fav_mat'),
      goals: read('mesh_goals'),
      theme: localStorage.getItem('mesh_theme') || 'light',
      target: localStorage.getItem('mesh_target') || '4.5'
    };
    if (this._prefsTimer) clearTimeout(this._prefsTimer);
    this._prefsTimer = setTimeout(() => this.syncPrefsToServer(), 1200);
  },

  syncPrefsToServer() {
    if (!Auth.isAuthenticated() || !this.prefs) return;
    API.savePrefs(this.prefs).then(res => {
      if (res && res.ok) return;
      if (navigator.onLine === false) localStorage.setItem('mesh_prefs_dirty', '1');
    });
  },

  flushPrefsOnOnline() {
    if (navigator.onLine && localStorage.getItem('mesh_prefs_dirty')) {
      localStorage.removeItem('mesh_prefs_dirty');
      this.markPrefsChanged();
    }
  },

  toggleFavDish(name) {
    name = decodeURIComponent(name || '');
    let favs = this.favDishes();
    if (favs.includes(name)) favs = favs.filter(f => f !== name);
    else favs.push(name);
    localStorage.setItem('mesh_fav_dishes', JSON.stringify(favs));
    this.markPrefsChanged();
    this.loadToday();
  },

  toggleNewsLike(id) {
    const meta = this.newsMeta || { likes: {}, comments: {} };
    const likes = (meta.likes && meta.likes[id]) || [];
    const me = this.getRole();
    const name = JSON.parse(localStorage.getItem('mesh_user') || '{}').name || '';
    const liked = Array.isArray(likes) && likes.indexOf(name) !== -1;
    (liked ? API.unlikeNews(id) : API.likeNews(id)).then(res => {
      if (res) {
        if (!this.newsMeta) this.newsMeta = {};
        this.newsMeta.likes = this.newsMeta.likes || {};
        this.newsMeta.likes[id] = new Array(res.likes).fill('x');
        this.loadNews(true);
      }
    });
  },

  addNewsComment(id) {
    const input = document.getElementById('nc-input-' + encodeURIComponent(id));
    const text = input ? input.value.trim() : '';
    if (!text) return;
    API.commentNews(id, text).then(res => {
      if (res && res.comments) {
        if (!this.newsMeta) this.newsMeta = {};
        this.newsMeta.comments = this.newsMeta.comments || {};
        this.newsMeta.comments[id] = res.comments;
        this.loadNews(true);
      }
    });
  },

  togglePrepShow() {
    this.navigateTo('prep');
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
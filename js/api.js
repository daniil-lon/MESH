const API = {
  BASE_URL: '/api',

  SLOT_TIMES: {
    alfa: [
      { pair: 1, start: '08:30', transition: '09:13', end: '10:00' },
      { pair: 2, start: '10:10', transition: '10:53', end: '11:40' },
      { pair: 3, start: '12:10', transition: '12:53', end: '13:40' }
    ],
    beta: [
      { pair: 4, start: '14:00', transition: '14:43', end: '15:30' },
      { pair: 5, start: '16:00', transition: '16:43', end: '17:30' },
      { pair: 6, start: '17:50', transition: '18:33', end: '19:20' }
    ],
    sat: [
      { pair: 1, start: '09:00', transition: '09:43', end: '10:30' },
      { pair: 2, start: '10:40', transition: '11:23', end: '12:10' },
      { pair: 3, start: '12:20', transition: '13:03', end: '13:50' },
      { pair: 4, start: '14:00', transition: '14:43', end: '15:30' }
    ]
  },

  DAY_LESSONS: {
    mon: [
      { subject: 'Математика', teacher: 'Иванова И.И.', room: 'Каб. 214', type: 'lection' },
      { subject: 'Информатика', teacher: 'Петров П.П.', room: 'Каб. 312', type: 'practice' },
      { subject: 'Английский язык', teacher: 'Смирнова А.В.', room: 'Каб. 108', type: 'practice' }
    ],
    tue: [
      { subject: 'Физика', teacher: 'Сидоров С.С.', room: 'Каб. 201', type: 'lection' },
      { subject: 'Русский язык', teacher: 'Козлова К.К.', room: 'Каб. 105', type: 'practice' },
      { subject: 'История', teacher: 'Новиков Н.Н.', room: 'Каб. 303', type: 'lection' }
    ],
    wed: [
      { subject: 'Информатика', teacher: 'Петров П.П.', room: 'Каб. 312', type: 'practice' },
      { subject: 'Математика', teacher: 'Иванова И.И.', room: 'Каб. 214', type: 'lection' },
      { subject: 'Литература', teacher: 'Белова Б.Б.', room: 'Каб. 110', type: 'lection' }
    ],
    thu: [
      { subject: 'Английский язык', teacher: 'Смирнова А.В.', room: 'Каб. 108', type: 'practice' },
      { subject: 'Физика', teacher: 'Сидоров С.С.', room: 'Каб. 201', type: 'practice' },
      { subject: 'Химия', teacher: 'Морозова М.М.', room: 'Каб. 215', type: 'lection' }
    ],
    fri: [
      { subject: 'Математика', teacher: 'Иванова И.И.', room: 'Каб. 214', type: 'practice' },
      { subject: 'История', teacher: 'Новиков Н.Н.', room: 'Каб. 303', type: 'practice' },
      { subject: 'Информатика', teacher: 'Петров П.П.', room: 'Каб. 312', type: 'practice' }
    ],
    sat: [
      { subject: 'ОБЖ', teacher: 'Волков В.В.', room: 'Онлайн', type: 'lection' },
      { subject: 'География', teacher: 'Лесова Л.Л.', room: 'Онлайн', type: 'lection' },
      { subject: 'Программирование', teacher: 'Петров П.П.', room: 'Онлайн', type: 'practice' },
      { subject: 'Классный час', teacher: 'Куратор группы', room: 'Онлайн', type: 'lection' }
    ]
  },

  async login(login, password) {
    const response = await fetch(`${this.BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Неверный логин или пароль');
    }
    return data;
  },

  async refreshToken() {
    const token = Auth.getToken();
    if (!token) return null;
    try {
      const response = await fetch(`${this.BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) return null;
      const data = await response.json();
      if (data && data.access_token) {
        localStorage.setItem('mesh_token', data.access_token);
        return data.access_token;
      }
    } catch (e) {}
    return null;
  },

  async request(endpoint) {
    const token = Auth.getToken();
    if (!token) return null;

    const cacheKey = 'cache' + endpoint;
    const offline = navigator.onLine === false;
    const cached = this.readCache(cacheKey, offline);

    if (navigator.onLine === false) {
      if (cached) return cached.data;
      return this.getFallbackData(endpoint);
    }

    try {
      const response = await fetch(`${this.BASE_URL}${endpoint}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 401) {
        Auth.logout();
        return null;
      }

      const data = await response.json();
      this.writeCache(cacheKey, data);
      return data;
    } catch (err) {
      console.error('API Error:', err);
      if (cached) return cached.data;
      return this.getFallbackData(endpoint);
    }
  },

  readCache(key, allowStale) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!allowStale) {
        const age = Date.now() - (parsed.timestamp || 0);
        if (age > 15 * 60 * 1000) return null;
      }
      return parsed;
    } catch (e) {
      return null;
    }
  },

  writeCache(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify({ timestamp: Date.now(), data }));
    } catch (e) {}
  },

  clearCache() {
    try {
      Object.keys(localStorage)
        .filter(k => k.startsWith('cache'))
        .forEach(k => localStorage.removeItem(k));
    } catch (e) {}
  },

  getSchedule(day, stream, group) {
    let endpoint = `/schedule/${day}?stream=${stream}`;
    if (group) endpoint += `&group=${encodeURIComponent(group)}`;
    return this.request(endpoint);
  },

  getGrades() {
    return this.request('/grades');
  },

  getHomework() {
    return this.request('/homework');
  },

  getProfile() {
    return this.request('/profile');
  },

  getReplacements() {
    return this.request('/replacements');
  },

  getExams() {
    return this.request('/exams');
  },

  getAttendance() {
    return this.request('/attendance');
  },

  getStudentCard() {
    return this.request('/student-card');
  },

  getAnnual() {
    return this.request('/annual');
  },

  getCanteen() {
    return this.request('/canteen');
  },

  getPortfolio() {
    return this.request('/portfolio');
  },

  getTickets() {
    return this.request('/tickets');
  },

  createTicket(topic, text) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/tickets`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ topic, text })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  getPublic(endpoint) {
    const cacheKey = 'cache' + endpoint;
    const offline = navigator.onLine === false;
    const cached = this.readCache(cacheKey, offline);
    if (navigator.onLine === false) {
      if (cached) return Promise.resolve(cached.data);
      return Promise.resolve(this.getFallbackData(endpoint));
    }
    return fetch(`${this.BASE_URL}${endpoint}`)
      .then(r => r.json())
      .then(data => {
        this.writeCache(cacheKey, data);
        return data;
      })
      .catch(() => cached ? cached.data : this.getFallbackData(endpoint));
  },

  getMaterials() {
    return this.getPublic('/materials');
  },

  getClubs() {
    return this.getPublic('/clubs');
  },

  getLost() {
    return this.getPublic('/lost');
  },

  getFaq() {
    return this.getPublic('/faq');
  },

  getNewsMeta() {
    return this.getPublic('/news/meta');
  },

  likeNews(id) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/news/${encodeURIComponent(id)}/like`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ liked: false }));
  },

  unlikeNews(id) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/news/${encodeURIComponent(id)}/like`, {
      method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ liked: false }));
  },

  commentNews(id, text) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/news/${encodeURIComponent(id)}/comment`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    }).then(r => r.json().catch(() => ({ comments: [] })));
  },

  getFreeRooms() {
    return this.getPublic('/rooms/free');
  },

  postJSON(endpoint, body, method = 'POST') {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }).then(async r => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }));
  },

  changePassword(current, newPassword) {
    return this.postJSON('/me/password', { current, new_password: newPassword });
  },

  teacherGroupQS() {
    const g = (typeof App !== 'undefined' && App.teacherGroup) || '';
    return g ? `?group=${encodeURIComponent(g)}` : '';
  },

  teacherAttendance() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/teacher/attendance${this.teacherGroupQS()}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => null);
  },

  saveTeacherAttendance(body) {
    return this.postJSON('/teacher/attendance', body, 'PUT');
  },

  curatorDashboard() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/curator/dashboard`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => null);
  },

  getTeacherSchedule() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/teacher/schedule`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => null);
  },

  curatorAnnounce(title, body) {
    return this.postJSON('/curator/announce', { title, body });
  },

  getPolls() {
    return this.getPublic('/polls');
  },

  votePoll(id, option) {
    return this.postJSON(`/polls/${encodeURIComponent(id)}/vote`, { option: option });
  },

  getReferences() {
    return this.getPublic('/references');
  },

  getBirthdays() {
    return this.getPublic('/birthdays');
  },

  adminCreatePoll(question, options) {
    return fetch(`${this.BASE_URL}/admin/polls`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify({ question, options })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  adminGetVersions(name) {
    return fetch(`${this.BASE_URL}/admin/versions/${encodeURIComponent(name)}`, {
      headers: this.adminHeaders()
    }).then(r => r.json()).catch(() => ({ versions: [] }));
  },

  adminRestoreVersion(name, version) {
    return fetch(`${this.BASE_URL}/admin/versions/${encodeURIComponent(name)}/restore`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify({ version })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  getPrefs() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/me/prefs`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ prefs: null }));
  },

  savePrefs(prefs) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/me/prefs`, {
      method: 'PUT',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ prefs })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  getDuties() {
    return this.getPublic('/duties');
  },

  getChat() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/chat`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ messages: [] }));
  },

  postChat(text) {
    return this.postJSON('/chat', { text });
  },

  curatorReplyTicket(id, status, answer) {
    return this.postJSON(`/curator/tickets/${encodeURIComponent(id)}`, { status, answer });
  },

  newsRead(id) {
    return this.postJSON(`/news/${encodeURIComponent(id)}/read`, {});
  },

  adminImportStudents(csv) {
    return fetch(`${this.BASE_URL}/admin/students/import`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify({ csv })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  adminExport(name) {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/admin/export/${encodeURIComponent(name)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.text()).catch(() => null);
  },

  adminStats() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/admin/stats`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({}));
  },

  getMyLogins() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/me/logins`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ logins: [] }));
  },

  getMyDebts() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/me/debts`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ debts: [], count: 0, ok: [] }));
  },

  teacherJournal() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/teacher/journal${this.teacherGroupQS()}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => null);
  },

  teacherAddGrade(body) {
    return this.postJSON('/teacher/journal/grade', body);
  },

  createShare() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/share`, {
      method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  getShare(token) {
    return fetch(`${this.BASE_URL}/share/${encodeURIComponent(token)}`)
      .then(async r => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }));
  },

  logError(message, stack) {
    try {
      const now = Date.now();
      const key = 'mesh_err_' + String(message).slice(0, 80);
      const last = parseInt(localStorage.getItem(key) || '0', 10) || 0;
      if (now - last < 60000) return;
      localStorage.setItem(key, String(now));
      const sessionCount = parseInt(sessionStorage.getItem('mesh_err_total') || '0', 10) || 0;
      if (sessionCount >= 30) return;
      sessionStorage.setItem('mesh_err_total', String(sessionCount + 1));
      fetch(`${this.BASE_URL}/log-error`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: String(message || '').slice(0, 200), stack: String(stack || '').slice(0, 300) })
      }).catch(() => {});
    } catch (e) {}
  },

  subscribePush(subscription) {
    const user = (JSON.parse(localStorage.getItem('mesh_user') || '{}') || {}).login || '';
    return fetch(`${this.BASE_URL}/push/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription, user })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  unsubscribePush(subscription) {
    return fetch(`${this.BASE_URL}/push/unsubscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  getVapidKey() {
    return fetch(`${this.BASE_URL}/vapid-public-key`)
      .then(r => r.json()).catch(() => ({ key: '' }));
  },

  getWeather() {
    return fetch(`${this.BASE_URL}/weather`)
      .then(r => r.json()).catch(() => null);
  },

  getRank() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/me/rank`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.json()).catch(() => null);
  },

  teacherHomework() {
    const token = Auth.getToken();
    return fetch(`${this.BASE_URL}/teacher/homework${this.teacherGroupQS()}`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.json()).catch(() => null);
  },

  teacherHomeworkCheck(body) {
    return this.postJSON('/teacher/homework/check', body);
  },

  adminImportSchedule(csv) {
    return fetch(`${this.BASE_URL}/admin/import/schedule`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify({ csv })
    }).then(r => r.json()).catch(() => ({ ok: false }));
  },

  adminHeaders() {
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + (localStorage.getItem('mesh_admin_token') || '')
    };
  },

  adminGetData() {
    return fetch(`${this.BASE_URL}/admin/data`, { headers: this.adminHeaders() }).then(r => r.json());
  },

  adminAddNews(item) {
    return fetch(`${this.BASE_URL}/admin/news`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify(item)
    }).then(r => r.json());
  },

  adminDeleteNews(id) {
    return fetch(`${this.BASE_URL}/admin/news/${encodeURIComponent(id)}`, {
      method: 'DELETE', headers: this.adminHeaders()
    }).then(r => r.json());
  },

  adminSetReplacements(body) {
    return fetch(`${this.BASE_URL}/admin/replacements`, {
      method: 'POST', headers: this.adminHeaders(), body: JSON.stringify(body)
    }).then(r => r.json());
  },

  adminReload() {
    return fetch(`${this.BASE_URL}/admin/reload`, {
      method: 'POST', headers: this.adminHeaders(), body: '{}'
    }).then(r => r.json());
  },

  getFallbackData(endpoint) {
    const dayMatch = endpoint.match(/\/schedule\/(\w+)/);
    if (dayMatch) {
      const day = dayMatch[1];
      const stream = new URLSearchParams(endpoint.split('?')[1] || '').get('stream') || 'alfa';
      const isSat = day === 'sat';
      const slots = isSat ? this.SLOT_TIMES.sat : this.SLOT_TIMES[stream];
      const subjects = this.DAY_LESSONS[day] || [];
      const lessons = slots.map((slot, i) => ({
        pair: slot.pair,
        time_start: slot.start,
        time_end: slot.end,
        transition: slot.transition,
        subject: subjects[i] ? subjects[i].subject : 'Окно',
        teacher: subjects[i] ? subjects[i].teacher : '—',
        room: subjects[i] ? subjects[i].room : '—',
        type: subjects[i] ? subjects[i].type : 'lection'
      }));
      return { lessons };
    }

    const fallback = {
      '/grades': {
        average: '4.2',
        total: 47,
        subjects: [
          { name: 'Математика', marks: [
            { value: 5, date: '05.09' }, { value: 5, date: '08.09' },
            { value: 4, date: '10.09', comment: 'Контрольная работа' }, { value: 5, date: '15.09' },
            { value: 4, date: '17.09' }, { value: 5, date: '19.09' }], average: '4.8' },
          { name: 'Информатика', marks: [
            { value: 5, date: '05.09', comment: 'Практическое задание' }, { value: 5, date: '08.09' },
            { value: 5, date: '10.09' }, { value: 4, date: '15.09' }, { value: 5, date: '17.09' }], average: '4.8' },
          { name: 'Английский язык', marks: [
            { value: 4, date: '05.09' }, { value: 3, date: '08.09' },
            { value: 4, date: '10.09' }, { value: 5, date: '15.09' }, { value: 4, date: '17.09' }], average: '4.0' },
          { name: 'Русский язык', marks: [
            { value: 4, date: '05.09' }, { value: 4, date: '08.09' },
            { value: 3, date: '10.09', comment: 'Диктант' }, { value: 4, date: '15.09' }], average: '3.8' },
          { name: 'Физика', marks: [
            { value: 5, date: '05.09', comment: 'Лабораторная работа №1' }, { value: 4, date: '08.09' },
            { value: 5, date: '10.09' }, { value: 4, date: '15.09' },
            { value: 5, date: '17.09', comment: 'Контрольная работа' }, { value: 5, date: '19.09' }], average: '4.7' }
        ]
      },
      '/homework': [
        { subject: 'Математика', task: 'Решить задачи №12-18 стр. 45', deadline: '11 сентября, 08:30', badge: 'Завтра', urgent: true, soon: false },
        { subject: 'Информатика', task: 'Написать программу на Python', deadline: '12 сентября, 09:25', badge: 'Через 2 дня', urgent: false, soon: true },
        { subject: 'Английский язык', task: 'Выучить слова Unit 5, подготовить презентацию', deadline: '13 сентября, 10:20', badge: 'Через 3 дня', urgent: false, soon: false },
        { subject: 'Физика', task: 'Лабораторная работа №3, отчёт', deadline: '15 сентября, 11:15', badge: 'Через 5 дней', urgent: false, soon: false }
      ],
      '/replacements': {
        date: '11 сентября 2026',
        items: [
          { day: 'пятница', pair: 4, time: '14:00 — 15:30', subject: 'Математика', from_teacher: 'Иванова И.И.', replacement_teacher: 'Смирнов А.А.', room: 'Каб. 302', note: 'Замена по расписанию' },
          { day: 'пятница', pair: 5, time: '16:00 — 17:30', subject: 'Информатика', from_teacher: 'Петров П.П.', replacement_teacher: 'Кузнецов К.К.', room: 'Каб. 312', note: 'Урок перенесён из каб. 118' },
          { day: 'понедельник', pair: 6, time: '17:50 — 19:20', subject: 'Физика', from_teacher: 'Сидоров С.С.', replacement_teacher: 'Орлов О.О.', room: 'Онлайн', note: 'Педагогический совет' }
        ]
      },
      '/exams': {
        session: 'Зимняя сессия 2026/27',
        exams: [
          { subject: 'Математика', date: '2026-12-15', form: 'Экзамен', time: '09:00' },
          { subject: 'Информатика', date: '2026-12-18', form: 'Экзамен', time: '09:00' },
          { subject: 'Английский язык', date: '2026-12-22', form: 'Зачёт', time: '10:00' },
          { subject: 'Физика', date: '2026-12-25', form: 'Диф. зачёт', time: '09:00' },
          { subject: 'История', date: '2026-12-28', form: 'Экзамен', time: '10:00' }
        ]
      },
      '/profile': {
        name: 'Иванов Петр',
        initials: 'ИП',
        course: '2 курс',
        school: 'ГБПОУ ИТ Москвы',
        speciality: 'Информационные системы и программирование',
        group: 'ИС-21',
        forma: 'Бюджет',
        address: 'ул. Академика Миллионщикова, д. 20',
        advisor: 'Сидорова М.В.',
        advisorPhone: '',
        attendance: 94,
        homeworkPercent: 87
      },
      '/news': [
        { title: 'Новостей пока нет', date: '', category: '', body: 'Подключитесь к интернету, чтобы загрузить свежие новости.' }
      ],
      '/attendance': {
        group: '—',
        attendance: 94,
        days: [
          { date: 'Сегодня', weekday: '', present: 3, total: 3, lessons: [
            { subject: 'Математика', status: 'present' },
            { subject: 'Информатика', status: 'present' },
            { subject: 'Английский язык', status: 'present' }
          ] }
        ]
      },
      '/student-card': null,
      '/annual': {
        events: [
          { date: '2026-11-04', title: 'День народного единства — выходной', type: 'holiday' },
          { date: '2026-12-15', title: 'Начало зимней сессии', type: 'exam' }
        ],
        next: [{ date: '2026-12-15', title: 'Начало зимней сессии', type: 'exam' }]
      },
      '/canteen': {
        days: [
          { day: 'Понедельник', meals: [{ name: 'Суп овощной', price: 85 }, { name: 'Котлета с пюре', price: 130 }, { name: 'Компот', price: 30 }] },
          { day: 'Вторник', meals: [{ name: 'Борщ', price: 90 }, { name: 'Курица с рисом', price: 140 }, { name: 'Чай', price: 20 }] },
          { day: 'Среда', meals: [{ name: 'Солянка', price: 95 }, { name: 'Макароны с сыром', price: 110 }, { name: 'Морс', price: 35 }] },
          { day: 'Четверг', meals: [{ name: 'Суп куриный', price: 85 }, { name: 'Рыба с картофелем', price: 135 }, { name: 'Компот', price: 30 }] },
          { day: 'Пятница', meals: [{ name: 'Щи', price: 80 }, { name: 'Блины с творогом', price: 90 }, { name: 'Какао', price: 40 }] }
        ]
      },
      '/portfolio': {
        practice: [
          { type: 'Учебная практика', place: 'Учебные мастерские колледжа', hours: '36 ч', period: 'сентябрь — октябрь 2026' }
        ],
        coursework: { subject: 'Информатика', topic: 'Разработка информационной системы «Электронное расписание»', curator: 'Петров П.П.', deadline: '20 декабря 2026' },
        diploma: { topic: 'Разработка автоматизированной информационной системы колледжа', curator: 'Петров П.П.', year: '2027' },
        achievements: [{ title: 'Призёр олимпиады «Программист будущего»', level: 'Городская', date: '2025' }]
      },
      '/tickets': { tickets: [] },
      '/materials': {
        materials: [
          { subject: 'Информатика', materials: [
            { title: 'Конспект лекций по Python', type: 'Конспект' },
            { title: 'Практикум: списки и словари', type: 'Практикум' }
          ], terms: [
            { term: 'Алгоритм', def: 'Последовательность шагов для решения задачи' }
          ] }
        ]
      },
      '/clubs': { clubs: [
        { name: 'Баскетбол', schedule: 'Вт, Чт 17:00–19:00', coach: 'Тренеров Т.Т.', room: 'Спортзал', status: 'Идёт набор' }
      ] },
      '/lost': { lost: [
        { item: 'Наушники TWS', place: 'Аудитория 312', date: '10 сентября', status: 'Найдено', contact: 'Вахта' }
      ] },
      '/faq': { faq: [
        { q: 'Как получить справку об обучении?', a: 'Обратитесь в деканат через профиль.' }
      ] },
      '/rooms/free': { rooms: [], current: '', free_all: true }
    };

    return fallback[endpoint] || null;
  },

  getBells() {
    return this.request('/bells').then(data => {
      if (data) {
        const satKey = Object.keys(data).find(k => /satur|суб/i.test(k));
        return {
          first: data.first || [],
          second: data.second || [],
          saturday: data[satKey] || []
        };
      }
      return null;
    });
  },

  getNews() {
    return this.request('/news').then(data => {
      if (!data) return null;
      const items = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      return items.filter(n => n && n.title);
    });
  }
};
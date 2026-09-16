# Деплой: как выложить сайт бесплатно (PythonAnywhere)

PythonAnywhere — бесплатный хостинг без карты, данные сохраняются, сайт всегда включён, HTTPS автоматически.

## Шаг 0. Что понадобится
- Email (для регистрации на pythonanywhere.com)
- Этот проект (готов к переносу: фронт+бэкенд в одном процессе, данные лежат в `backend/data/`)

## Шаг 1. Регистрация
1. Открой https://www.pythonanywhere.com/ → **Start running Python online in your browser**.
2. Зарегистрируйся (Username, почта, пароль) — бесплатно, карта НЕ нужна.
3. Подтверди почту. Запиши свой Username — он станет адресом сайта: `https://<username>.pythonanywhere.com`.

## Шаг 2. Загрузка кода
1. На дашборде: **Files → Upload a file**, выбери `mesh-pwa.zip` из папки проекта → жди загрузку (проект ~5 МБ).
   Файл появится в `/home/<username>/mesh-pwa.zip`.
2. Открой вкладку **Consoles → $ Bash**, выполни:
   ```bash
   cd ~
   unzip -o mesh-pwa.zip -d /home/<username>/mesh_pwa
   ls /home/<username>/mesh_pwa   # должны быть index.html, backend, asgi.py и т.д.
   ```

## Шаг 3. Зависимости (виртуальное окружение)
В той же Bash-консоли (выбери свежий Python 3.12):
```bash
cd /home/<username>/mesh_pwa
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```
> Если python3.12 нет, подойдёт python3.11. (НЕ бери 3.13: старые версии pydantic/cryptography могут не собраться.)

## Шаг 4. Веб-приложение (ASGI)
1. **Web tab → Add a new web app** → Next → **Manual configuration** → Python 3.12.
2. В секции **Code**:
   - Working directory: `/home/<username>/mesh_pwa`
   - ASGI application file: `/home/<username>/mesh_pwa/asgi.py`
3. Нажми **Reload** (клавиша/кнопка вверху страницы Web).

## Шаг 5. Проверка
- Студенческий портал: `https://<username>.pythonanywhere.com/`
- Админка: `https://<username>.pythonanywhere.com/admin.html` — пароль `1111`
- Сайт отдаётся по HTTPS → работают сервис-воркер, push-уведомления, PWA-установка.

## Важные замечания
- Данные хранятся в файлах проекта (`backend/data/*.json`) и **переживают перезапуски**. Сделай «Скачать бэкап» в админке, чтобы иметь копию.
- Админ-пароль лучше сменить (раздел «Сменить пароль» в админке) — после смены он хранится в `backend/data/admin_pass.json`.
- Панель статистики («Обзор») показывает данные за текущий день.
- PG (Postgres) на бесплатном тарифе недоступен — проекту он и не нужен (всё на файлах).
- Если что-то пошло не так: вкладка **Web → Error log** покажет ошибки Python.

## Возврат на локальную разработку
Ничего не ломается: локально продолжай запускать `python backend/main.py` на 8000 порту.
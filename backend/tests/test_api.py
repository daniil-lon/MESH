import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import main
from main import app, _save_json, TICKETS_FILE, LOGIN_ATTEMPTS, GRADES_FILE, SHARES_FILE
from main import reload_data_files, reload_accounts, DATA_FILES_MAP, STUDENTS_FILE
from main import CHAT_FILE, ADMIN_FAILS, ADMIN_PASS_FILE, SCHEDULED_POSTS_FILE


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def snapshot_data():
    LOGIN_ATTEMPTS.clear()
    ADMIN_FAILS.clear()
    paths = [STUDENTS_FILE] + list(DATA_FILES_MAP.values())
    if SCHEDULED_POSTS_FILE.exists():
        paths.append(SCHEDULED_POSTS_FILE)
    snaps = {}
    for p in paths:
        if p.exists():
            snaps[str(p)] = p.read_bytes()
    yield
    for p, content in snaps.items():
        with open(p, "wb") as f:
            f.write(content)
    LOGIN_ATTEMPTS.clear()
    ADMIN_FAILS.clear()
    reload_data_files()
    reload_accounts()


def login(client, login="abdulkadirova0001", password="abur2wza9z"):
    r = client.post("/api/auth/login", json={"login": login, "password": password})
    return r


def auth(client):
    r = login(client)
    assert r.status_code == 200
    return r.json()["access_token"]


def test_index_served(client):
    r = client.get("/index.html")
    assert r.status_code == 200
    assert "IT Москва Колледж" in r.text


def test_admin_html_served(client):
    r = client.get("/admin.html")
    assert r.status_code == 200


def test_login_success_and_fail(client):
    ok = login(client)
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = login(client, password="wrong")
    assert bad.status_code == 401


def test_login_rate_limit(client):
    for _ in range(10):
        login(client, login="spamuser", password="x")
    blocked = login(client, login="spamuser", password="x")
    assert blocked.status_code == 429


def test_profile_requires_connection(client):
    token = auth(client)
    r = client.get("/api/profile", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["real"] is True
    assert data["name"]
    assert data["group"]


def test_grades_structure(client):
    token = auth(client)
    r = client.get("/api/grades", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "average" in data
    assert len(data["subjects"]) >= 3
    assert all("marks" in s and "average" in s for s in data["subjects"])


def test_homework_from_file(client):
    r = client.get("/api/homework")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["subject"]


def test_bells_structure(client):
    r = client.get("/api/bells")
    assert r.status_code == 200
    data = r.json()
    assert len(data["first"]) >= 3
    assert len(data["second"]) >= 3
    assert len(data["saturday"]) >= 3


def test_annual_contains_next_event(client):
    r = client.get("/api/annual")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["events"], list)
    assert len(data["events"]) >= 1
    assert isinstance(data["next"], list)


def test_canteen_days(client):
    r = client.get("/api/canteen")
    assert r.status_code == 200
    data = r.json()
    assert len(data["days"]) >= 5
    assert data["days"][0]["meals"]


def test_portfolio_sections(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert "practice" in data
    assert "coursework" in data
    assert "diploma" in data


def test_schedule_group_specific(client):
    g = "%D0%90%D0%B1%D0%B4%D1%83%D0%BB%D0%BA%D0%B0%D0%B4%D0%B8%D1%80%D0%BE%D0%B2%D0%B0"
    r = client.get("/api/schedule/mon", params={"stream": "alfa", "group": "1ГД-2-11-26"})
    r2 = client.get("/api/schedule/mon", params={"stream": "alfa", "group": "1И-1-26"})
    assert r.status_code == 200 and r2.status_code == 200
    a = [l["subject"] for l in r.json()["lessons"]]
    b = [l["subject"] for l in r2.json()["lessons"]]
    assert a != b
    assert a[0] == "Рисунок"


def test_attendance_requires_and_returns(client):
    token = auth(client)
    r = client.get("/api/attendance", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["group"] == "1ГД-2-11-26"
    assert 0 <= data["attendance"] <= 100
    assert len(data["days"]) >= 5


def test_student_card_401_without_token(client):
    r = client.get("/api/student-card")
    assert r.status_code == 401


def test_student_card_with_token(client):
    token = auth(client)
    r = client.get("/api/student-card", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["fio"]
    assert data["svg"].startswith("<svg")


def test_tickets_require_auth(client):
    r = client.get("/api/tickets")
    assert r.status_code == 401

    r = client.post("/api/tickets", json={"topic": "x", "text": "y"})
    assert r.status_code == 401


def test_admin_requires_token(client):
    r = client.get("/api/admin/data")
    assert r.status_code == 401

    r = client.get("/api/admin/data", headers={"Authorization": "Bearer 1111"})
    assert r.status_code == 200
    assert "news" in r.json()


def test_admin_announce(client):
    r = client.post("/api/admin/announce",
                    json={"title": "Тест", "body": "Тело"},
                    headers={"Authorization": "Bearer 1111"})
    assert r.status_code == 200
    assert "ok" in r.json()


def test_admin_reset_password_rejects_unknown(client):
    r = client.post("/api/admin/reset-password",
                    json={"login": "nobody", "password": "x"},
                    headers={"Authorization": "Bearer 1111"})
    assert r.status_code == 404


def test_admin_log_access(client):
    no = client.get("/api/admin/log")
    assert no.status_code == 401
    yes = client.get("/api/admin/log", headers={"Authorization": "Bearer 1111"})
    assert yes.status_code == 200
    assert "log" in yes.json()


def test_content_files_accessible(client):
    for url in ("/api/materials", "/api/clubs", "/api/lost", "/api/faq"):
        r = client.get(url)
        assert r.status_code == 200
    materials = client.get("/api/materials").json()
    assert len(materials["materials"]) >= 1
    clubs = client.get("/api/clubs").json()
    assert len(clubs["clubs"]) >= 1
    lost = client.get("/api/lost").json()
    assert len(lost["lost"]) >= 1
    faq = client.get("/api/faq").json()
    assert len(faq["faq"]) >= 1


def test_news_meta_and_like_comment(client):
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}
    meta = client.get("/api/news/meta", headers=h)
    assert meta.status_code == 200
    assert "likes" in meta.json() and "comments" in meta.json()

    like = client.post("/api/news/_t1/like", headers=h)
    assert like.status_code == 200
    assert like.json()["liked"] is True

    comment = client.post("/api/news/_t1/comment", headers=h, json={"text": "спасибо!"})
    assert comment.status_code == 200
    assert any(c["name"] for c in comment.json()["comments"])

    unlike = client.delete("/api/news/_t1/like", headers=h)
    assert unlike.status_code == 200
    assert unlike.json()["liked"] is False


def test_news_comment_requires_student(client):
    token = auth(client)
    empty = client.post("/api/news/_t1/comment", json={"text": "   "},
                        headers={"Authorization": f"Bearer {token}"})
    assert empty.status_code == 400


def test_free_rooms(client):
    r = client.get("/api/rooms/free")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["rooms"], list)


def test_teacher_role_and_attendance(client):
    no = client.get("/api/teacher/attendance")
    assert no.status_code == 403

    r = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"})
    assert r.status_code == 200
    assert r.json()["role"] == "teacher"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    get = client.get("/api/teacher/attendance", headers=h)
    assert get.status_code == 200
    assert get.json()["group"]

    put = client.put("/api/teacher/attendance", headers=h,
                     json={"date": "01.01", "lessons": [{"subject": "Информатика", "status": "absent"}]})
    assert put.status_code == 200
    assert put.json()["ok"] is True
    assert put.json()["lessons"][0]["status"] == "absent"

    bad = client.put("/api/teacher/attendance", headers=h,
                     json={"date": "01.01", "lessons": [{"subject": "Информатика", "status": "no"}]})
    assert bad.status_code == 400


def test_curator_dashboard(client):
    r = client.post("/api/auth/login", json={"login": "curator01", "password": "curator01"})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    dash = client.get("/api/curator/dashboard", headers=h)
    assert dash.status_code == 200
    data = dash.json()
    assert data["group"]
    assert data["students"] >= 1
    assert isinstance(data["tickets"], list)


def test_change_password_flow(client):
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}

    wrong = client.post("/api/me/password", json={"current": "nope", "new_password": "xyz"}, headers=h)
    assert wrong.status_code == 400

    ok = client.post("/api/me/password", json={"current": "abur2wza9z", "new_password": "newpass1"}, headers=h)
    assert ok.status_code == 200

    relogin = client.post("/api/auth/login", json={"login": "abdulkadirova0001", "password": "newpass1"})
    assert relogin.status_code == 200

    back = client.post("/api/me/password", json={"current": "newpass1", "new_password": "abur2wza9z"},
                       headers={"Authorization": f"Bearer {relogin.json()['access_token']}"})
    assert back.status_code == 200


def test_admin_file_editor(client):
    h = {"Authorization": "Bearer 1111"}
    get = client.get("/api/admin/file/faq", headers=h)
    assert get.status_code == 200
    assert "content" in get.json()

    put = client.put("/api/admin/file/faq", headers=h, json={"content": [{"q": "тест", "a": "ок"}]})
    assert put.status_code == 200

    bad = client.put("/api/admin/file/faq", headers=h, json={"content": "строка"})
    assert bad.status_code == 400

    missing = client.get("/api/admin/file/unknown", headers=h)
    assert missing.status_code == 404


def test_admin_backup_and_restore(client):
    h = {"Authorization": "Bearer 1111"}
    backup = client.get("/api/admin/backup", headers=h)
    assert backup.status_code == 200
    assert backup.headers["content-type"] == "application/zip"
    assert len(backup.content) > 0

    restore = client.post("/api/admin/restore", headers=h, json={"files": {"faq": [{"q": "1", "a": "1"}]}})
    assert restore.status_code == 200
    assert "faq" in restore.json()["restored"]


def test_curator_and_teacher_block_student(client):
    token = auth(client)
    r = client.get("/api/curator/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    r2 = client.get("/api/teacher/attendance", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 403


def test_polls_vote_and_admin_create(client):
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}
    polls = client.get("/api/polls", headers=h).json()["polls"]
    assert len(polls) >= 2
    pid = polls[0]["id"]

    vote = client.post(f"/api/polls/{pid}/vote", json={"option": 0}, headers=h)
    assert vote.status_code == 200

    again = client.post(f"/api/polls/{pid}/vote", json={"option": 1}, headers=h)
    assert again.status_code == 200

    dup = client.post(f"/api/polls/{pid}/vote", json={"option": 99}, headers=h)
    assert dup.status_code == 400

    adm = client.post("/api/admin/polls", headers={"Authorization": "Bearer 1111"},
                      json={"question": "Тест?", "options": ["да", "нет"]})
    assert adm.status_code == 200

    bad = client.post("/api/admin/polls", headers={"Authorization": "Bearer 1111"},
                      json={"question": "?"})
    assert bad.status_code == 400


def test_references_and_birthdays(client):
    token = auth(client)
    refs = client.get("/api/references").json()
    assert isinstance(refs, dict)
    assert "library" in refs

    b = client.get("/api/birthdays", headers={"Authorization": f"Bearer {token}"}).json()
    assert isinstance(b["birthdays"], list)


def test_curator_announce_and_teacher_schedule(client):
    t = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"}).json()
    teacher = client.get("/api/teacher/schedule", headers={"Authorization": f"Bearer {t['access_token']}"})
    assert teacher.status_code == 200
    assert teacher.json()["groups"]

    c = client.post("/api/auth/login", json={"login": "curator01", "password": "curator01"}).json()
    ann = client.post("/api/curator/announce",
                      json={"title": "Собрание", "body": "В понедельник в 15:00"},
                      headers={"Authorization": f"Bearer {c['access_token']}"})
    assert ann.status_code == 200
    top = ann.json()["news"][0]
    assert top["groups"] == ["1ГД-2-11-26"]

    student = auth(client)
    visible = client.get("/api/news", headers={"Authorization": f"Bearer {student}"}).json()
    assert any(n["id"] == top["id"] for n in visible)


def test_teacher_multi_group(client):
    t = client.post("/api/auth/login", json={"login": "teacher02", "password": "teacher02"}).json()
    assert t["groups"] == ["1ГД-2-11-26", "1ИС-26"]
    h = {"Authorization": f"Bearer {t['access_token']}"}

    j = client.get("/api/teacher/journal", headers=h)
    assert j.status_code == 200
    assert j.json()["group"] == "1ГД-2-11-26"

    j2 = client.get("/api/teacher/journal", headers=h, params={"group": "1ИС-26"})
    assert j2.status_code == 200
    assert j2.json()["group"] == "1ИС-26"

    att = client.get("/api/teacher/attendance", headers=h, params={"group": "1ИС-26"})
    assert att.status_code == 200
    assert att.json()["group"] == "1ИС-26"

    bad = client.get("/api/teacher/journal", headers=h, params={"group": "1ХХ-99"})
    assert bad.status_code == 200
    assert bad.json()["group"] == "1ГД-2-11-26"


def test_versions_roundtrip(client):
    h = {"Authorization": "Bearer 1111"}
    client.put("/api/admin/file/faq", headers=h, json={"content": [{"q": "до", "a": "v1"}]})
    client.put("/api/admin/file/faq", headers=h, json={"content": [{"q": "после", "a": "v2"}]})

    versions = client.get("/api/admin/versions/faq", headers=h).json()["versions"]
    assert len(versions) >= 2
    v1 = versions[1]["version"]

    restored = client.post(f"/api/admin/versions/faq/restore", headers=h, json={"version": v1})
    assert restored.status_code == 200
    assert restored.json()["content"][0]["a"] == "v1"


def test_news_group_filter(client):
    admin = {"Authorization": "Bearer 1111"}
    title = "Только для первой группы"
    post = client.post("/api/admin/news", headers=admin,
                       json={"title": title, "groups": ["1И-1-26"], "body": "тест"})
    assert post.status_code == 200
    pid = post.json()["news"][0]["id"]

    token = auth(client)
    mine = client.get("/api/news", headers={"Authorization": f"Bearer {token}"}).json()
    assert all(n["id"] != pid for n in mine)


def test_log_error_rate_limit(client):
    ok = client.post("/api/log-error", json={"message": "boom"})
    assert ok.status_code == 200
    for _ in range(25):
        client.post("/api/log-error", json={"message": "x"})
    limited = client.post("/api/log-error", json={"message": "y"})
    assert limited.status_code == 429


def test_prefs_sync(client):
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}
    put = client.put("/api/me/prefs", headers=h, json={"prefs": {"fav_mat": ["Информатика"], "goals": []}})
    assert put.status_code == 200
    get = client.get("/api/me/prefs", headers=h)
    assert get.json()["prefs"].get("fav_mat") == ["Информатика"]
    assert client.get("/api/me/prefs").status_code == 401


def test_duties(client):
    token = auth(client)
    d = client.get("/api/duties", headers={"Authorization": f"Bearer {token}"}).json()
    assert isinstance(d["schedule"], list)
    assert "today" in d


def test_chat_flow(client):
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}
    post = client.post("/api/chat", json={"text": "привет"}, headers=h)
    assert post.status_code == 200
    get = client.get("/api/chat", headers=h).json()
    assert get["messages"][-1]["text"] == "привет"
    bad = client.post("/api/chat", json={"text": "   "}, headers=h)
    assert bad.status_code == 400


def test_news_important_reads(client):
    adm = {"Authorization": "Bearer 1111"}
    post = client.post("/api/admin/news", headers=adm,
                       json={"title": "Важно", "body": "текст", "important": True})
    nid = post.json()["news"][0]["id"]

    token = auth(client)
    r1 = client.post(f"/api/news/{nid}/read", headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200
    assert r1.json()["count"] == 1

    t2 = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"}).json()
    r2 = client.post(f"/api/news/{nid}/read", headers={"Authorization": f"Bearer {t2['access_token']}"})
    assert r2.json()["count"] == 2


def test_curator_ticket_reply(client):
    token = auth(client)
    ticket = client.post("/api/tickets", json={
        "topic": "Справка", "text": "Нужна справка"}, headers={"Authorization": f"Bearer {token}"})
    tid = ticket.json()["ticket"]["id"]

    cur = client.post("/api/auth/login", json={"login": "curator01", "password": "curator01"}).json()
    reply = client.post(f"/api/curator/tickets/{tid}", headers={"Authorization": f"Bearer {cur['access_token']}"},
                        json={"status": "done", "answer": "Готово"})
    assert reply.status_code == 200
    done = [t for t in reply.json()["tickets"] if t["id"] == tid][0]
    assert done["status"] == "done"
    assert done["answer"] == "Готово"


def test_teacher_journal_and_grades(client):
    t = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"}).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}
    journal = client.get("/api/teacher/journal", headers=h)
    assert journal.status_code == 200
    data = journal.json()
    assert data["group"] == "1ГД-2-11-26"
    assert len(data["students"]) >= 1
    assert "Математика" in data["subjects"]

    noauth = client.get("/api/teacher/journal")
    assert noauth.status_code == 403

    added = client.post("/api/teacher/journal/grade", headers=h,
                        json={"login": "abdulkadirova0001", "subject": "Математика",
                              "value": 3, "date": "12.09", "comment": "Тест"})
    assert added.status_code == 200
    assert added.json()["marks"][-1]["value"] == 3

    fixed = client.post("/api/teacher/journal/grade", headers=h,
                        json={"login": "abdulkadirova0001", "subject": "Математика",
                              "value": 4, "date": "12.09"})
    assert fixed.json()["marks"][-1]["value"] == 4
    assert len(fixed.json()["marks"]) == 1

    bad = client.post("/api/teacher/journal/grade", headers=h,
                      json={"login": "abdulkadirova0001", "subject": "Математика", "value": 9})
    assert bad.status_code == 400

    student = auth(client)
    grades = client.get("/api/grades", headers={"Authorization": f"Bearer {student}"}).json()
    math = next(s for s in grades["subjects"] if s["name"] == "Математика")
    assert math["marks"][-1]["value"] == 4

    GRADES_FILE.unlink(missing_ok=True)
    reload_data_files()


def test_my_debts(client):
    token = auth(client)
    r = client.get("/api/me/debts", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "debts" in data and "count" in data and "ok" in data
    assert client.get("/api/me/debts").status_code == 401


def test_share_link(client):
    token = auth(client)
    r = client.post("/api/share", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    url = r.json()["url"]
    tok = url.split("share=")[1]
    got = client.get(f"/api/share/{tok}")
    assert got.status_code == 200
    data = got.json()
    assert data["ok"] is True
    assert data["fio"]
    assert data["group"]
    bad = client.get("/api/share/notexist")
    assert bad.status_code == 404
    SHARES_FILE.unlink(missing_ok=True)
    reload_data_files()


def test_students_csv_import_and_export(client):
    adm = {"Authorization": "Bearer 1111"}
    imp = client.post("/api/admin/students/import", headers=adm,
                      json={"csv": "py1,1111,Пытов П.П.,1ГД-2-11-26\npy2,2222,Новов Н.Н.,1И-1-26"})
    assert imp.status_code == 200
    assert imp.json()["created"] == 2
    ok_login = client.post("/api/auth/login", json={"login": "py1", "password": "1111"})
    assert ok_login.status_code == 200

    exp = client.get("/api/admin/export/polls", headers=adm)
    assert exp.status_code == 200
    assert exp.headers["content-type"].startswith("text/csv")

    blocked = client.get("/api/admin/export/polls")
    assert blocked.status_code == 401


def test_admin_stats(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.get("/api/admin/stats", headers=adm)
    assert r.status_code == 200
    assert set(r.json()) >= {"logins_today", "logins_week", "frontend_errors"}


def test_push_subscribe(client):
    sub = {"endpoint": "https://example.test/push/1",
           "keys": {"p256dh": "x", "auth": "y"}}
    st = auth(client)
    r = client.post("/api/push/subscribe", headers={"Authorization": f"Bearer {st}"},
                    json={"subscription": sub, "user": "abdulkadirova0001"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    u = client.post("/api/push/unsubscribe", json={"subscription": sub})
    assert u.status_code == 200


def test_rank_student(client):
    st = auth(client)
    r = client.get("/api/me/rank", headers={"Authorization": f"Bearer {st}"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"place", "total", "average", "above"}


def test_rank_teacher_forbidden(client):
    t = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"}).json()
    r = client.get("/api/me/rank", headers={"Authorization": f"Bearer {t['access_token']}"})
    assert r.status_code == 403


def test_teacher_homework_forbidden_student(client):
    st = auth(client)
    r = client.get("/api/teacher/homework", headers={"Authorization": f"Bearer {st}"})
    assert r.status_code == 403


def test_teacher_homework_ok(client):
    t = client.post("/api/auth/login", json={"login": "teacher01", "password": "teacher01"}).json()["access_token"]
    r = client.get("/api/teacher/homework", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert "items" in r.json() and "students" in r.json()


def test_import_schedule_csv(client):
    adm = {"Authorization": "Bearer 1111"}
    csv = "day;subject;teacher;room;type\nпн;Math;Иванов И.И.;каб. 1;lection\nвт;Python;Петров П.П.;каб. 2;practice"
    r = client.post("/api/admin/import/schedule", headers=adm, json={"csv": csv})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "default" in r.json()["groups"]
    blocked = client.post("/api/admin/import/schedule", json={"csv": csv})
    assert blocked.status_code == 401


def test_admin_backup_settings(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.get("/api/admin/backup-settings", headers=adm)
    assert r.status_code == 200
    post = client.post("/api/admin/backup-settings", headers=adm,
                       json={"auto_backup": False, "backup_days": 3})
    assert post.status_code == 200
    assert post.json()["backup_days"] == 3
    assert post.json()["auto_backup"] is False
    blocked = client.get("/api/admin/backup-settings")
    assert blocked.status_code == 401


def test_admin_top_groups(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.get("/api/admin/top-groups", headers=adm)
    assert r.status_code == 200
    assert "groups" in r.json()


def test_admin_attendance_stats(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.get("/api/admin/attendance-stats", headers=adm)
    assert r.status_code == 200
    assert "groups" in r.json()


def test_admin_frontend_errors(client):
    adm = {"Authorization": "Bearer 1111"}
    main.FRONTEND_ERRORS.clear()
    client.post("/api/log-error", json={"message": "тест ошибки"})
    r = client.get("/api/admin/frontend-errors", headers=adm)
    assert r.status_code == 200
    msgs = [e["msg"] for e in r.json()["errors"]]
    assert any("тест ошибки" in m for m in msgs)
    c = client.post("/api/admin/frontend-errors/clear", headers=adm)
    assert c.status_code == 200
    r2 = client.get("/api/admin/frontend-errors", headers=adm)
    assert not any("тест ошибки" in e["msg"] for e in r2.json()["errors"])


def test_admin_announce_addressed(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.post("/api/admin/announce", headers=adm,
                    json={"title": "t", "body": "b", "login": "abdulkadirova0001"})
    assert r.status_code == 200
    blocked = client.post("/api/admin/announce", json={"title": "t", "body": "b"})
    assert blocked.status_code == 401


def test_admin_ticket_answer(client):
    adm = {"Authorization": "Bearer 1111"}
    create = client.post("/api/tickets", json={"topic": "тема", "text": "текст"},
                         headers={"Authorization": f"Bearer {auth(client)}"})
    assert create.status_code == 200
    tid = create.json()["ticket"]["id"]

    r = client.post(f"/api/admin/tickets/{tid}/answer", headers=adm,
                    json={"status": "done", "answer": "Всё исправлено"})
    assert r.status_code == 200
    ticket = next(t for t in r.json()["tickets"] if t["id"] == tid)
    assert ticket["answer"] == "Всё исправлено"
    assert ticket["status"] == "done"
    assert ticket.get("answer_ts")

    noauth = client.post(f"/api/admin/tickets/{tid}/answer", json={"answer": "x"})
    assert noauth.status_code == 401

    missing = client.post("/api/admin/tickets/t0/answer", headers=adm, json={"answer": "x"})
    assert missing.status_code == 404


def test_admin_chat_moderation(client):
    adm = {"Authorization": "Bearer 1111"}
    token = auth(client)
    h = {"Authorization": f"Bearer {token}"}
    client.post("/api/chat", json={"text": "сообщение на модерацию"}, headers=h)

    r = client.get("/api/admin/chat", headers=adm)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs
    assert all(m.get("id") for m in msgs)

    target = next(m for m in msgs if m["text"] == "сообщение на модерацию")
    d = client.delete(f"/api/admin/chat/{target['id']}", headers=adm)
    assert d.status_code == 200
    assert not any(m["id"] == target["id"] for m in d.json()["messages"])

    again = client.delete(f"/api/admin/chat/{target['id']}", headers=adm)
    assert again.status_code == 404

    noauth = client.get("/api/admin/chat")
    assert noauth.status_code == 401


def test_admin_upload_flow(client, tmp_path):
    adm = {"Authorization": "Bearer 1111"}
    orig = main.UPLOADS_DIR
    main.UPLOADS_DIR = tmp_path
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        up = client.post("/api/admin/upload", headers=adm,
                         files={"file": ("тест.png", b"\x89PNG\r\n\x1a\ndata", "image/png")})
        assert up.status_code == 200
        name = up.json()["name"]
        assert "/uploads/" in up.json()["url"]

        lst = client.get("/api/admin/uploads", headers=adm)
        assert lst.status_code == 200
        assert any(f["name"] == name for f in lst.json()["files"])

        bad = client.post("/api/admin/upload", headers=adm,
                          files={"file": ("evil.exe", b"mz", "application/octet-stream")})
        assert bad.status_code == 400

        d = client.delete(f"/api/admin/uploads/{name}", headers=adm)
        assert d.status_code == 200
        lst2 = client.get("/api/admin/uploads", headers=adm).json()["files"]
        assert not any(f["name"] == name for f in lst2)

        noauth = client.get("/api/admin/uploads")
        assert noauth.status_code == 401
    finally:
        main.UPLOADS_DIR = orig


def test_admin_push_dashboard(client):
    adm = {"Authorization": "Bearer 1111"}
    r = client.get("/api/admin/push", headers=adm)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and isinstance(body["total"], int)
    assert isinstance(body["users"], list)

    rm = client.delete("/api/admin/push/abdulkadirova0001", headers=adm)
    assert rm.status_code == 200
    assert rm.json()["ok"] is True

    noauth = client.get("/api/admin/push")
    assert noauth.status_code == 401


def test_admin_scheduled_posts(client):
    adm = {"Authorization": "Bearer 1111"}
    import datetime as _dt
    when = (_dt.datetime.now() + _dt.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")

    add = client.post("/api/admin/scheduled", headers=adm,
                      json={"title": "Плановая новость", "body": "текст",
                            "category": "Важное", "publish_at": when, "announce": True})
    assert add.status_code == 200
    sid = add.json()["posts"][0]["id"]

    lst = client.get("/api/admin/scheduled", headers=adm)
    assert lst.status_code == 200
    assert any(p["id"] == sid for p in lst.json()["posts"])

    bad = client.post("/api/admin/scheduled", headers=adm,
                      json={"title": "", "publish_at": when})
    assert bad.status_code == 400

    cancel = client.post(f"/api/admin/scheduled/{sid}/cancel", headers=adm)
    assert cancel.status_code == 200
    assert not any(p["id"] == sid for p in cancel.json()["posts"])


def test_admin_scheduled_publish_due(client):
    adm = {"Authorization": "Bearer 1111"}
    past = "2000-01-01 00:00"
    add = client.post("/api/admin/scheduled", headers=adm,
                      json={"title": "Просроченная", "body": "", "publish_at": past})
    assert add.status_code == 200
    add2 = client.post("/api/admin/scheduled", headers=adm,
                       json={"title": "Будущая", "body": "", "publish_at": "2099-01-01 00:00"})
    assert add2.status_code == 200

    main._publish_due_posts()
    posts = main._read_scheduled()
    assert not any(p["title"] == "Просроченная" for p in posts)
    titles = [n["title"] for n in (main.FILE_NEWS or [])]
    assert any("Просроченная" in t for t in titles)


def test_admin_change_password(client, tmp_path):
    adm_pass_name = "admin_pass_test.json"
    orig_file = main.ADMIN_PASS_FILE
    tmp_file = tmp_path / adm_pass_name
    main.ADMIN_PASS_FILE = tmp_file
    try:
        adm = {"Authorization": "Bearer 1111"}
        bad = client.post("/api/admin/change-password", headers=adm,
                          json={"current": "wrong", "new_password": "12345678"})
        assert bad.status_code == 403

        ok = client.post("/api/admin/change-password", headers=adm,
                         json={"current": "1111", "new_password": "12345678"})
        assert ok.status_code == 200
        assert ok.json()["token"] == "12345678"

        assert tmp_file.exists()
        old = client.get("/api/admin/data", headers={"Authorization": "Bearer 1111"})
        assert old.status_code == 401
        new = client.get("/api/admin/data", headers={"Authorization": "Bearer 12345678"})
        assert new.status_code == 200

        short = client.post("/api/admin/change-password",
                            headers={"Authorization": "Bearer 12345678"},
                            json={"current": "12345678", "new_password": "1"})
        assert short.status_code == 400
    finally:
        main.ADMIN_PASS_FILE = orig_file
        if tmp_file.exists():
            tmp_file.unlink()


def test_admin_login_blocked(client):
    for _ in range(5):
        r = client.get("/api/admin/data", headers={"Authorization": "Bearer wrong01"})
        assert r.status_code == 401
    blocked = client.get("/api/admin/data", headers={"Authorization": "Bearer 1111"})
    assert blocked.status_code == 429
    assert "10 минут" in blocked.json()["detail"]


def test_admin_canteen_validation_fixed(client):
    adm = {"Authorization": "Bearer 1111"}
    content = {"days": [{"day": "Понедельник", "meals": [{"name": "Суп", "price": 80}]}]}
    put = client.put("/api/admin/file/canteen", headers=adm, json={"content": content})
    assert put.status_code == 200
from fastapi import FastAPI, HTTPException, Depends, status, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import os, json, secrets, hashlib, hmac, re
import asyncio
import time
import zipfile
import io
import httpx
from datetime import datetime, timedelta
import qrcode
from qrcode.image.svg import SvgPathImage
import jwt as pyjwt
from dotenv import load_dotenv
from pathlib import Path
import push_service

load_dotenv()

BASE_DIR = Path(os.getenv("MESH_BASE_DIR") or Path(__file__).resolve().parent.parent)

app = FastAPI(title="IT Москва Колледж API", version="2.0.0")

app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    login: str
    password: str


class NewsItem(BaseModel):
    id: str = ""
    title: str
    category: str = ""
    date: str = ""
    body: str = ""
    groups: list[str] = []
    important: bool = False


class ReplacementsBody(BaseModel):
    date: str = ""
    items: list[dict] = []


class PushSubscribeBody(BaseModel):
    subscription: dict
    user: str = ""


class HomeworkCheckBody(BaseModel):
    item_id: str
    login: str
    done: bool = False
    grade: Optional[int] = None


class CsvImportBody(BaseModel):
    csv: str = ""


class TicketCreate(BaseModel):
    topic: str
    text: str


class TicketStatus(BaseModel):
    status: str


class ResetPassword(BaseModel):
    login: str
    password: str


class AnnounceBody(BaseModel):
    title: str = ""
    body: str = ""
    login: str = ""
    url: str = "/"


class Lesson(BaseModel):
    time_start: str
    time_end: str
    subject: str
    teacher: str
    room: str
    type: str


class GradeMark(BaseModel):
    value: int
    date: str
    comment: str = ""


class GradeSubject(BaseModel):
    name: str
    marks: list[GradeMark]
    average: str


class HomeworkItem(BaseModel):
    subject: str
    task: str
    deadline: str
    badge: str
    urgent: bool = False
    soon: bool = False


class CommentBody(BaseModel):
    text: str


class ChangePasswordBody(BaseModel):
    current: str
    new_password: str


class AttendanceMarkBody(BaseModel):
    date: str
    lessons: List[dict] = []


class FilePayload(BaseModel):
    content: Any


class RestoreBody(BaseModel):
    files: Dict[str, Any] = {}


class VoteBody(BaseModel):
    option: int


class PollCreateBody(BaseModel):
    question: str
    options: List[str] = []
    closed: bool = False


class CuratorAnnounceBody(BaseModel):
    title: str
    body: str = ""


class RestoreVersionBody(BaseModel):
    version: str


class PrefsBody(BaseModel):
    prefs: Dict[str, Any] = {}


class ChatPostBody(BaseModel):
    text: str


class TicketReplyBody(BaseModel):
    status: str = "in-progress"
    answer: str = ""


class ImportStudentsBody(BaseModel):
    csv: str = ""


class TeacherGradeBody(BaseModel):
    login: str
    subject: str
    value: int = 5
    date: str = ""
    comment: str = ""


@app.get("/")
async def root():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/index.html")
async def index_html():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/css/{file_path:path}")
async def serve_css(file_path: str):
    return FileResponse(BASE_DIR / "css" / file_path)


@app.get("/js/{file_path:path}")
async def serve_js(file_path: str):
    return FileResponse(BASE_DIR / "js" / file_path)


@app.get("/icons/{file_path:path}")
async def serve_icons(file_path: str):
    return FileResponse(BASE_DIR / "icons" / file_path)


@app.get("/manifest.json")
async def serve_manifest():
    return FileResponse(BASE_DIR / "manifest.json")


@app.get("/sw.js")
async def serve_sw():
    return FileResponse(BASE_DIR / "sw.js")


@app.get("/admin.html")
async def serve_admin():
    return FileResponse(BASE_DIR / "admin.html",
                        headers={"Cache-Control": "no-store"})


def load_students() -> list[dict]:
    path = BASE_DIR / "backend" / "data" / "students.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def load_curators() -> dict:
    path = BASE_DIR / "backend" / "data" / "curators.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


STUDENTS = load_students()
CURATORS = load_curators()
SESSION_USERS: Dict[str, dict] = {}

DATA_DIR = Path(os.getenv("MESH_DATA_DIR") or (BASE_DIR / "backend" / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
NEWS_FILE = DATA_DIR / "news.json"
REPLACEMENTS_FILE = DATA_DIR / "replacements.json"
EXAMS_FILE = DATA_DIR / "exams.json"
ATTENDANCE_FILE = DATA_DIR / "attendance.json"
SCHEDULE_FILE = DATA_DIR / "schedule.json"
STUDENTS_FILE = DATA_DIR / "students.json"
BELLS_FILE = DATA_DIR / "bells.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
HOMEWORK_FILE = DATA_DIR / "homework.json"
HOMEWORK_CHECKS_FILE = DATA_DIR / "homework-checks.json"
GRADES_FILE = DATA_DIR / "grades.json"
ANNUAL_FILE = DATA_DIR / "annual.json"
CANTEEN_FILE = DATA_DIR / "canteen.json"
SPECIALITIES_FILE = DATA_DIR / "specialities.json"
TICKETS_FILE = DATA_DIR / "tickets.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
ADMIN_LOG_FILE = DATA_DIR / "admin_log.jsonl"
MATERIALS_FILE = DATA_DIR / "materials.json"
CLUBS_FILE = DATA_DIR / "clubs.json"
LOST_FILE = DATA_DIR / "lost.json"
FAQ_FILE = DATA_DIR / "faq.json"
NEWS_META_FILE = DATA_DIR / "news_meta.json"
STAFF_FILE = DATA_DIR / "staff.json"
POLLS_FILE = DATA_DIR / "polls.json"
REFERENCES_FILE = DATA_DIR / "references.json"
BIRTHDAYS_FILE = DATA_DIR / "birthdays.json"
PROFILE_SYNC_FILE = DATA_DIR / "profile.json"
DUTIES_FILE = DATA_DIR / "duties.json"
CHAT_FILE = DATA_DIR / "chat.json"
LOGINS_LOG_FILE = DATA_DIR / "logins.jsonl"
SHARES_FILE = DATA_DIR / "shares.json"
VERSIONS_DIR = DATA_DIR / "versions"
DATA_FILES_MAP = {
    "news": NEWS_FILE, "replacements": REPLACEMENTS_FILE, "exams": EXAMS_FILE,
    "schedule": SCHEDULE_FILE, "attendance": ATTENDANCE_FILE, "grades": GRADES_FILE,
    "bells": BELLS_FILE, "homework": HOMEWORK_FILE, "annual": ANNUAL_FILE,
    "canteen": CANTEEN_FILE, "specialities": SPECIALITIES_FILE, "tickets": TICKETS_FILE,
    "portfolio": PORTFOLIO_FILE, "materials": MATERIALS_FILE, "clubs": CLUBS_FILE,
    "lost": LOST_FILE, "faq": FAQ_FILE, "news-meta": NEWS_META_FILE, "staff": STAFF_FILE,
    "polls": POLLS_FILE, "references": REFERENCES_FILE, "birthdays": BIRTHDAYS_FILE,
    "profile": PROFILE_SYNC_FILE, "duties": DUTIES_FILE, "chat": CHAT_FILE,
    "shares": SHARES_FILE,
}

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "1111")
ADMIN_PASS_FILE = DATA_DIR / "admin_pass.json"
SCHEDULED_POSTS_FILE = DATA_DIR / "scheduled_posts.json"
UPLOADS_DIR = Path(os.getenv("MESH_UPLOADS_DIR") or (BASE_DIR / "uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path, default):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path, data, snapshot=True):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
    if snapshot and path.parent == DATA_DIR and snapshots_enabled:
        _snapshot_file(path)


snapshots_enabled = True


def _snapshot_file(path, keep=20):
    try:
        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        name = path.stem
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = VERSIONS_DIR / f"{name}.{ts}.json"
        target.write_bytes(path.read_bytes())
        files = sorted(VERSIONS_DIR.glob(f"{name}.*.json"))
        for old in files[:-keep]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


def _file_versions(name):
    out = []
    try:
        for p in sorted(VERSIONS_DIR.glob(f"{name}.*.json"), reverse=True):
            out.append({"name": name, "version": p.stem.replace(name + ".", ""), "path": str(p)})
    except Exception:
        out = []
    return {"versions": out}


def _restore_version(name, version):
    target = DATA_FILES_MAP[name]
    versions = _file_versions(name)["versions"]
    src = None
    for v in versions:
        if v["version"] == version:
            src = v["path"]
            break
    if not src:
        return None
    content = _read_json(type(target)(src), None)
    if content is None:
        return None
    _save_json(target, content)
    reload_data_files()
    _log_admin(f"Откат файла {name} к версии {version}")
    return content


DEFAULT_NEWS = [
    {"id": "n1", "title": "Открыта запись на подготовительные курсы по программированию", "date": "10 сентября 2026", "category": "Объявление", "body": "Для студентов 1 курса открыта запись на дополнительные курсы Python и веб-разработки. Запись у куратора группы до 20 сентября."},
    {"id": "n2", "title": "Олимпиада по информатике «Программист будущего»", "date": "08 сентября 2026", "category": "Олимпиада", "body": "Регистрация на городскую олимпиаду до 15 октября. Участники получат дополнительные баллы при поступлении в вузы."},
    {"id": "n3", "title": "Изменение расписания звонков с 14 сентября", "date": "05 сентября 2026", "category": "Важное", "body": "Со следующей недели вводится новый поток расписания (Альфа). Проверьте актуальное расписание в приложении."},
    {"id": "n4", "title": "День открытых дверей ГБПОУ ИТ Москвы", "date": "01 сентября 2026", "category": "Мероприятие", "body": "Приглашаем абитуриентов и их родителей 20 октября. Начало в 10:00 в главном корпусе."},
]

DEFAULT_REPLACEMENTS = {
    "date": "11 сентября 2026",
    "items": [
        {"day": "пятница", "pair": 4, "time": "14:00 — 15:30", "subject": "Математика", "from_teacher": "Иванова И.И.", "replacement_teacher": "Смирнов А.А.", "room": "Каб. 302", "note": "Замена по расписанию"},
        {"day": "пятница", "pair": 5, "time": "16:00 — 17:30", "subject": "Информатика", "from_teacher": "Петров П.П.", "replacement_teacher": "Кузнецов К.К.", "room": "Каб. 312", "note": "Урок перенесён из каб. 118"},
        {"day": "понедельник", "pair": 6, "time": "17:50 — 19:20", "subject": "Физика", "from_teacher": "Сидоров С.С.", "replacement_teacher": "Орлов О.О.", "room": "Онлайн", "note": "Педагогический совет"},
    ],
}

DEFAULT_EXAMS = {
    "session": "Зимняя сессия 2026/27",
    "exams": [
        {"subject": "Математика", "date": "2026-12-15", "form": "Экзамен", "time": "09:00"},
        {"subject": "Информатика", "date": "2026-12-18", "form": "Экзамен", "time": "09:00"},
        {"subject": "Английский язык", "date": "2026-12-22", "form": "Зачёт", "time": "10:00"},
        {"subject": "Физика", "date": "2026-12-25", "form": "Диф. зачёт", "time": "09:00"},
        {"subject": "История", "date": "2026-12-28", "form": "Экзамен", "time": "10:00"},
    ],
    "consultations": [
        {"subject": "Математика", "date": "14 декабря 2026", "time": "13:00", "room": "Каб. 214"},
        {"subject": "Информатика", "date": "17 декабря 2026", "time": "13:00", "room": "Каб. 312"},
    ],
    "retakes": "Пересдача по каждому предмету не позднее 10 января 2027 (по расписанию комиссии).",
}

DEFAULT_BELLS = {
    "first": [
        {"pair": 1, "start": "08:30", "transition": "09:13", "end": "10:00"},
        {"pair": 2, "start": "10:10", "transition": "10:53", "end": "11:40"},
        {"pair": 3, "start": "12:10", "transition": "12:53", "end": "13:40"},
    ],
    "second": [
        {"pair": 4, "start": "14:00", "transition": "14:43", "end": "15:30"},
        {"pair": 5, "start": "16:00", "transition": "16:43", "end": "17:30"},
        {"pair": 6, "start": "17:50", "transition": "18:33", "end": "19:20"},
    ],
    "saturday": [
        {"pair": 1, "start": "09:00", "transition": "09:43", "end": "10:30"},
        {"pair": 2, "start": "10:40", "transition": "11:23", "end": "12:10"},
        {"pair": 3, "start": "12:20", "transition": "13:03", "end": "13:50"},
        {"pair": 4, "start": "14:00", "transition": "14:43", "end": "15:30"},
    ],
}

DEFAULT_HOMEWORK = [
    {"subject": "Математика", "task": "Решить задачи №12-18 стр. 45", "deadline": "11 сентября, 08:30", "badge": "Завтра", "urgent": True, "soon": False},
    {"subject": "Информатика", "task": "Написать программу на Python", "deadline": "12 сентября, 09:25", "badge": "Через 2 дня", "urgent": False, "soon": True},
    {"subject": "Английский язык", "task": "Выучить слова Unit 5, подготовить презентацию", "deadline": "13 сентября, 10:20", "badge": "Через 3 дня", "urgent": False, "soon": False},
    {"subject": "Физика", "task": "Лабораторная работа №3, отчёт", "deadline": "15 сентября, 11:15", "badge": "Через 5 дней", "urgent": False, "soon": False},
]

DEFAULT_ANNUAL = [
    {"date": "2026-10-05", "title": "День учителя — праздничное мероприятие", "type": "event"},
    {"date": "2026-11-04", "title": "День народного единства — выходной", "type": "holiday"},
    {"date": "2026-11-16", "title": "Промежуточная аттестация 1 триместр", "type": "attestation"},
    {"date": "2026-12-15", "title": "Начало зимней сессии", "type": "exam"},
    {"date": "2026-12-25", "title": "Начало зимних каникул", "type": "holiday"},
    {"date": "2027-01-10", "title": "Окончание зимних каникул, начало занятий", "type": "holiday"},
    {"date": "2027-03-08", "title": "Международный женский день — выходной", "type": "holiday"},
    {"date": "2027-04-01", "title": "Промежуточная аттестация 3 триместр", "type": "attestation"},
]

DEFAULT_CANTEEN = {
    "days": [
        {"day": "Понедельник", "meals": [{"name": "Суп овощной", "price": 85}, {"name": "Котлета с пюре", "price": 130}, {"name": "Компот", "price": 30}, {"name": "Салат «Витаминный»", "price": 60}]},
        {"day": "Вторник", "meals": [{"name": "Борщ", "price": 90}, {"name": "Курица с рисом", "price": 140}, {"name": "Чай", "price": 20}, {"name": "Фрукт", "price": 40}]},
        {"day": "Среда", "meals": [{"name": "Солянка", "price": 95}, {"name": "Макароны с сыром", "price": 110}, {"name": "Морс", "price": 35}, {"name": "Салат «Оливье»", "price": 70}]},
        {"day": "Четверг", "meals": [{"name": "Суп куриный", "price": 85}, {"name": "Рыба с картофелем", "price": 135}, {"name": "Компот", "price": 30}, {"name": "Салат из капусты", "price": 50}]},
        {"day": "Пятница", "meals": [{"name": "Щи", "price": 80}, {"name": "Блины с творогом", "price": 90}, {"name": "Какао", "price": 40}, {"name": "Сок", "price": 45}]},
    ]
}

DEFAULT_PORTFOLIO = {
    "practice": [
        {"type": "Учебная практика", "place": "Учебные мастерские колледжа", "hours": "36 ч", "period": "сентябрь — октябрь 2026"},
        {"type": "Производственная практика", "place": "Предприятия-партнёры", "hours": "72 ч", "period": "февраль — март 2027"},
    ],
    "coursework": {
        "subject": "Информатика",
        "topic": "Разработка информационной системы «Электронное расписание»",
        "curator": "Петров П.П.",
        "deadline": "20 декабря 2026",
    },
    "diploma": {
        "topic": "Разработка автоматизированной информационной системы колледжа",
        "curator": "Петров П.П.",
        "year": "2027",
    },
    "achievements": [
        {"title": "Призёр олимпиады «Программист будущего»", "level": "Городская", "date": "2025"},
        {"title": "Сертификат о прохождении курса Python", "level": "Курс", "date": "2026"},
    ],
}


SPECIALITIES = {
    "1И-": ("Обеспечение информационной безопасности автоматизированных систем", "специальность", "Харьковский проезд, д. 5А / ул. Академика Миллионщикова, д. 20"),
    "1ИИ-": ("Интеграция решений с применением технологий искусственного интеллекта", "специальность", "Харьковский проезд, д. 5А"),
    "1ГД-": ("Графический дизайнер", "профессия", "ул. Коломенская, д. 5, корп. 3"),
    "1МВТ-": ("Мастер вертикального транспорта", "профессия", "Харьковский проезд, д. 5А"),
    "1БТС-": ("Информационные системы и программирование", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1ИС-": ("Информационные системы и программирование", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1КС-": ("Компьютерные системы и комплексы", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1СА-": ("Сетевое и системное администрирование", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1ИМС-": ("Информационные системы и программирование", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1ЭВМ-": ("Вычислительные машины, комплексы, системы и сети", "специальность", "Харьковский проезд, д. 5А"),
    "1РКИ-": ("Реклама и издательское дело", "специальность", "Харьковский проезд, д. 5А"),
    "1РУП-": ("Реклама", "специальность", "Харьковский проезд, д. 5А"),
    "1ВР-": ("Веб-разработка на Python", "профессия", "Харьковский проезд, д. 5А"),
    "1ЭИС-": ("Эксплуатация и обслуживание информационных систем", "специальность", "Харьковский проезд, д. 5А"),
    "1КНк-": ("Коммерция (по отраслям)", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1ПВк-": ("Поварское и кондитерское дело", "профессия", "ул. Академика Миллионщикова, д. 20"),
    "1ЭМ-": ("Экономика и бухгалтерский учёт", "специальность", "ул. Академика Миллионщикова, д. 20"),
    "1ЭО-": ("Эксплуатация оборудования и систем", "специальность", "Харьковский проезд, д. 5А"),
}


def _ensure_data_files():
    if not NEWS_FILE.exists():
        _save_json(NEWS_FILE, DEFAULT_NEWS)
    if not REPLACEMENTS_FILE.exists():
        _save_json(REPLACEMENTS_FILE, DEFAULT_REPLACEMENTS)
    if not EXAMS_FILE.exists():
        _save_json(EXAMS_FILE, DEFAULT_EXAMS)
    if not BELLS_FILE.exists():
        _save_json(BELLS_FILE, DEFAULT_BELLS)
    if not HOMEWORK_FILE.exists():
        _save_json(HOMEWORK_FILE, DEFAULT_HOMEWORK)
    if not ANNUAL_FILE.exists():
        _save_json(ANNUAL_FILE, DEFAULT_ANNUAL)
    if not CANTEEN_FILE.exists():
        _save_json(CANTEEN_FILE, DEFAULT_CANTEEN)
    if not TICKETS_FILE.exists():
        _save_json(TICKETS_FILE, {"tickets": []})
    if not PORTFOLIO_FILE.exists():
        _save_json(PORTFOLIO_FILE, DEFAULT_PORTFOLIO)
    if not SPECIALITIES_FILE.exists():
        _save_json(SPECIALITIES_FILE, _default_specialities_list())
    if not MATERIALS_FILE.exists():
        _save_json(MATERIALS_FILE, DEFAULT_MATERIALS)
    if not CLUBS_FILE.exists():
        _save_json(CLUBS_FILE, DEFAULT_CLUBS)
    if not LOST_FILE.exists():
        _save_json(LOST_FILE, DEFAULT_LOST)
    if not FAQ_FILE.exists():
        _save_json(FAQ_FILE, DEFAULT_FAQ)
    if not NEWS_META_FILE.exists():
        _save_json(NEWS_META_FILE, DEFAULT_NEWS_META)
    if not STAFF_FILE.exists():
        _save_json(STAFF_FILE, DEFAULT_STAFF)
    if not POLLS_FILE.exists():
        _save_json(POLLS_FILE, DEFAULT_POLLS)
    if not REFERENCES_FILE.exists():
        _save_json(REFERENCES_FILE, DEFAULT_REFERENCES)
    if not BIRTHDAYS_FILE.exists():
        _save_json(BIRTHDAYS_FILE, DEFAULT_BIRTHDAYS)
    if not PROFILE_SYNC_FILE.exists():
        _save_json(PROFILE_SYNC_FILE, {})
    if not DUTIES_FILE.exists():
        _save_json(DUTIES_FILE, DEFAULT_DUTIES)
    if not CHAT_FILE.exists():
        _save_json(CHAT_FILE, DEFAULT_CHAT)


def _default_specialities_list() -> list:
    return [
        {"prefix": k, "name": v[0], "type": v[1], "address": v[2]}
        for k, v in SPECIALITIES.items()
    ]


DEFAULT_TICKETS = {"tickets": []}

DEFAULT_MATERIALS = [
    {
        "subject": "Информатика",
        "materials": [
            {"title": "Конспект лекций по Python", "type": "Конспект"},
            {"title": "Практикум: списки и словари", "type": "Практикум"},
            {"title": "Пример решения задач ЕГЭ по информатике", "type": "Разбор"},
        ],
        "terms": [
            {"term": "Алгоритм", "def": "Последовательность шагов для решения задачи"},
            {"term": "Переменная", "def": "Именованная область памяти для хранения значения"},
        ],
    },
    {
        "subject": "Математика",
        "materials": [
            {"title": "Формулы тригонометрии", "type": "Шпаргалка"},
            {"title": "Методичка: производная", "type": "Методичка"},
        ],
        "terms": [
            {"term": "Производная", "def": "Скорость изменения функции в точке"},
            {"term": "Интеграл", "def": "Площадь под графиком функции"},
        ],
    },
    {
        "subject": "Английский язык",
        "materials": [
            {"title": "Tenses Table (времена)", "type": "Таблица"},
            {"title": "Топики для устного ответа", "type": "Топики"},
        ],
        "terms": [
            {"term": "Present Perfect", "def": "Настоящее совершенное время"},
        ],
    },
]

DEFAULT_CLUBS = [
    {"name": "Баскетбол", "schedule": "Вт, Чт 17:00–19:00", "coach": "Тренеров Т.Т.", "room": "Спортзал", "status": "Идёт набор"},
    {"name": "Волейбол", "schedule": "Пн, Ср 18:00–20:00", "coach": "Лебедева Л.Л.", "room": "Спортзал", "status": "Идёт набор"},
    {"name": "Робототехника", "schedule": "Сб 12:00–14:00", "coach": "Петров П.П.", "room": "Каб. 312", "status": "Группа укомплектована"},
    {"name": "Театральная студия", "schedule": "Ср 16:00–18:00", "coach": "Артистикова А.А.", "room": "Актовый зал", "status": "Идёт набор"},
    {"name": "Волонтёрский центр", "schedule": "Пт 15:00–16:30", "coach": "Куратор центра", "room": "Каб. 205", "status": "Идёт набор"},
]

DEFAULT_LOST = [
    {"item": "Наушники TWS (чёрные)", "place": "Аудитория 312", "date": "10 сентября", "status": "Найдено", "contact": "Вахта главного корпуса"},
    {"item": "Портативное зарядное устройство", "place": "Столовая", "date": "9 сентября", "status": "Найдено", "contact": "Вахта столовой"},
    {"item": "Синяя шапка", "place": "Спортзал", "date": "8 сентября", "status": "Найдено", "contact": "Спортивный зал"},
]

DEFAULT_FAQ = [
    {"q": "Как получить справку об обучении?", "a": "Оставьте обращение в деканат в разделе «Портфолио» — справка будет готова в течение 3 рабочих дней."},
    {"q": "Где взять электронный студенческий?", "a": "В профиле нажмите «Электронный студенческий» — появится QR-код для прохода."},
    {"q": "Забыли пароль от учётной записи?", "a": "Обратитесь к куратору группы или в деканат — администратор установит новый пароль."},
    {"q": "Как смотреть расписание своей группы?", "a": "Расписание автоматически строится по вашей группе. Кнопка звонка показывает расписание звонков."},
    {"q": "Куда сдавать справки о болезни?", "a": "Справки принимает куратор группы в течение 3 дней после болезни."},
]

DEFAULT_NEWS_META = {"likes": {}, "comments": {}, "reads": {}}

DEFAULT_STAFF = {
    "teachers": [
        {"login": "teacher01", "password": "teacher01", "fio": "Петров Петр Петрович", "group": "1ГД-2-11-26", "role": "teacher"},
        {"login": "kipitch", "password": "12345678", "fio": "Кипич", "group": "1ГД-2-11-26", "role": "teacher"},
    ],
    "curators": [
        {"login": "curator01", "password": "curator01", "fio": "Смирнова Анна Викторовна", "group": "1ГД-2-11-26", "role": "curator"},
    ],
}

DEFAULT_POLLS = [
    {
        "id": "p1",
        "question": "Какое время начала занятий вам удобнее?",
        "options": ["8:30 (как сейчас)", "9:00", "9:30"],
        "results": {},
        "closed": False,
    },
    {
        "id": "p2",
        "question": "Что добавить в столовой?",
        "options": ["Больше салатов", "Супы", "Вегетарианские блюда", "Всё устраивает"],
        "results": {},
        "closed": False,
    },
]

DEFAULT_REFERENCES = {
    "library": {"hours": ["Пн–Пт: 09:00 — 18:00", "Сб: 10:00 — 15:00", "Вс: выходной"], "address": "Корпус 1, 2 этаж"},
    "medpoint": {"hours": ["Пн–Пт: 08:30 — 17:00"], "phone": "+7 (495) 123-45-67", "address": "Корпус 2, 1 этаж"},
    "wifi": [{"name": "College-WiFi", "login": "студенческий билет", "note": "Авторизация через логин и пароль учётной записи"}],
    "phones": [
        {"name": "Деканат", "phone": "+7 (495) 123-45-60"},
        {"name": "Куратор", "phone": "через приложение, вкладка «Куратор»"},
        {"name": "Психологическая поддержка", "phone": "+7 (495) 234-56-78"},
        {"name": "Техподдержка приложения", "phone": "admin@example.ru"},
    ],
}

DEFAULT_BIRTHDAYS = [
    {"name": "Абдулкадирова Алина", "date": "17.01", "group": "1ГД-2-11-26"},
    {"name": "Иванов Иван", "date": "03.03", "group": "1ГД-2-11-26"},
    {"name": "Петрова Полина", "date": "25.04", "group": "1ГД-2-11-26"},
    {"name": "Смирнов Сергей", "date": "12.06", "group": "1ГД-2-11-26"},
    {"name": "Кузнецова Кристина", "date": "08.09", "group": "1ГД-2-11-26"},
]

DEFAULT_DUTIES = {
    "list": [
        {"day": "понедельник", "names": ["Абдулкадирова Алина"]},
        {"day": "вторник", "names": ["Иванов Иван"]},
        {"day": "среда", "names": ["Петрова Полина"]},
        {"day": "четверг", "names": ["Смирнов Сергей"]},
        {"day": "пятница", "names": ["Кузнецова Кристина"]},
    ]
}

DEFAULT_CHAT = {"messages": []}


_ensure_data_files()

FILE_NEWS = _read_json(NEWS_FILE, DEFAULT_NEWS)
FILE_REPLACEMENTS = _read_json(REPLACEMENTS_FILE, DEFAULT_REPLACEMENTS)
FILE_EXAMS = _read_json(EXAMS_FILE, DEFAULT_EXAMS)
FILE_SCHEDULE = _read_json(SCHEDULE_FILE, None)
FILE_ATTENDANCE = _read_json(ATTENDANCE_FILE, None)
FILE_GRADES = _read_json(GRADES_FILE, None)
FILE_BELLS = _read_json(BELLS_FILE, DEFAULT_BELLS)
FILE_ANNUAL = _read_json(ANNUAL_FILE, DEFAULT_ANNUAL)
FILE_CANTEEN = _read_json(CANTEEN_FILE, DEFAULT_CANTEEN)
FILE_TICKETS = _read_json(TICKETS_FILE, DEFAULT_TICKETS)
FILE_PORTFOLIO = _read_json(PORTFOLIO_FILE, DEFAULT_PORTFOLIO)
FILE_SPECIALITIES = _read_json(SPECIALITIES_FILE, None)
FILE_MATERIALS = _read_json(MATERIALS_FILE, DEFAULT_MATERIALS)
FILE_CLUBS = _read_json(CLUBS_FILE, DEFAULT_CLUBS)
FILE_LOST = _read_json(LOST_FILE, DEFAULT_LOST)
FILE_FAQ = _read_json(FAQ_FILE, DEFAULT_FAQ)
FILE_NEWS_META = _read_json(NEWS_META_FILE, DEFAULT_NEWS_META)
FILE_STAFF = _read_json(STAFF_FILE, DEFAULT_STAFF)
FILE_POLLS = _read_json(POLLS_FILE, DEFAULT_POLLS)
FILE_REFERENCES = _read_json(REFERENCES_FILE, DEFAULT_REFERENCES)
FILE_BIRTHDAYS = _read_json(BIRTHDAYS_FILE, DEFAULT_BIRTHDAYS)
FILE_PROFILE_SYNC = _read_json(PROFILE_SYNC_FILE, {})
FILE_DUTIES = _read_json(DUTIES_FILE, DEFAULT_DUTIES)
FILE_CHAT = _read_json(CHAT_FILE, DEFAULT_CHAT)
FILE_SHARES = _read_json(SHARES_FILE, {})


def _all_staff() -> list:
    staff = FILE_STAFF or {}
    result = list(staff.get("teachers", [])) + list(staff.get("curators", []))
    known = {s.get("login") for s in result}
    for s in DEFAULT_STAFF.get("teachers", []) + DEFAULT_STAFF.get("curators", []):
        if s.get("login") not in known:
            result.append(s)
    return result


def _staff_by_login(login: str):
    return next((s for s in _all_staff() if s.get("login") == login), None)


def reload_data_files():
    global FILE_NEWS, FILE_REPLACEMENTS, FILE_EXAMS, FILE_SCHEDULE, FILE_ATTENDANCE
    global FILE_GRADES, FILE_BELLS, FILE_HOMEWORK, FILE_ANNUAL, FILE_CANTEEN
    global FILE_TICKETS, FILE_PORTFOLIO, FILE_SPECIALITIES
    global FILE_MATERIALS, FILE_CLUBS, FILE_LOST, FILE_FAQ, FILE_NEWS_META, FILE_STAFF
    global FILE_POLLS, FILE_REFERENCES, FILE_BIRTHDAYS
    global FILE_PROFILE_SYNC, FILE_DUTIES, FILE_CHAT
    global FILE_SHARES, FILE_HW_CHECKS
    _ensure_data_files()
    FILE_NEWS = _read_json(NEWS_FILE, DEFAULT_NEWS)
    FILE_REPLACEMENTS = _read_json(REPLACEMENTS_FILE, DEFAULT_REPLACEMENTS)
    FILE_EXAMS = _read_json(EXAMS_FILE, DEFAULT_EXAMS)
    FILE_SCHEDULE = _read_json(SCHEDULE_FILE, None)
    FILE_ATTENDANCE = _read_json(ATTENDANCE_FILE, None)
    FILE_GRADES = _read_json(GRADES_FILE, None)
    FILE_BELLS = _read_json(BELLS_FILE, DEFAULT_BELLS)
    FILE_HOMEWORK = _read_json(HOMEWORK_FILE, DEFAULT_HOMEWORK)
    FILE_HW_CHECKS = _read_json(HOMEWORK_CHECKS_FILE, {})
    FILE_ANNUAL = _read_json(ANNUAL_FILE, DEFAULT_ANNUAL)
    FILE_CANTEEN = _read_json(CANTEEN_FILE, DEFAULT_CANTEEN)
    FILE_TICKETS = _read_json(TICKETS_FILE, DEFAULT_TICKETS)
    FILE_PORTFOLIO = _read_json(PORTFOLIO_FILE, DEFAULT_PORTFOLIO)
    FILE_SPECIALITIES = _read_json(SPECIALITIES_FILE, None)
    FILE_MATERIALS = _read_json(MATERIALS_FILE, DEFAULT_MATERIALS)
    FILE_CLUBS = _read_json(CLUBS_FILE, DEFAULT_CLUBS)
    FILE_LOST = _read_json(LOST_FILE, DEFAULT_LOST)
    FILE_FAQ = _read_json(FAQ_FILE, DEFAULT_FAQ)
    FILE_NEWS_META = _read_json(NEWS_META_FILE, DEFAULT_NEWS_META)
    FILE_STAFF = _read_json(STAFF_FILE, DEFAULT_STAFF)
    FILE_POLLS = _read_json(POLLS_FILE, DEFAULT_POLLS)
    FILE_REFERENCES = _read_json(REFERENCES_FILE, DEFAULT_REFERENCES)
    FILE_BIRTHDAYS = _read_json(BIRTHDAYS_FILE, DEFAULT_BIRTHDAYS)
    FILE_PROFILE_SYNC = _read_json(PROFILE_SYNC_FILE, {})
    FILE_DUTIES = _read_json(DUTIES_FILE, DEFAULT_DUTIES)
    FILE_CHAT = _read_json(CHAT_FILE, DEFAULT_CHAT)
    FILE_SHARES = _read_json(SHARES_FILE, {})


_initial_data_loaded = False


def reload_accounts():
    global STUDENTS, CURATORS
    STUDENTS = load_students()
    CURATORS = load_curators()


async def _auto_reload_loop():
    while True:
        await asyncio.sleep(60)
        try:
            reload_data_files()
            reload_accounts()
        except Exception:
            pass


@app.on_event("startup")
async def _startup_tasks():
    app.state.auto_reload = asyncio.create_task(_auto_reload_loop())
    app.state.auto_backup = asyncio.create_task(_auto_backup_loop())
    app.state.auto_publish = asyncio.create_task(_auto_publish_loop())


LOGIN_ATTEMPTS: Dict[str, list] = {}


def _check_login_rate(request: Request):
    ip = request.client.host if request.client else "?"
    now = time.time()
    ts = [t for t in LOGIN_ATTEMPTS.get(ip, []) if now - t < 60]
    if len(ts) >= 10:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Подождите минуту и попробуйте снова.")
    ts.append(now)
    LOGIN_ATTEMPTS[ip] = ts


def speciality_info(group: str) -> dict:
    rows = FILE_SPECIALITIES or _default_specialities_list()
    best_prefix = ""
    best = None
    for r in rows:
        prefix = r.get("prefix", "")
        if group.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best = {"name": r.get("name", "—"), "type": r.get("type", "—"), "address": r.get("address", "—")}
    if best:
        return best
    return {"name": "—", "type": "—", "address": "—"}


def group_curator(group: str) -> dict:
    c = CURATORS.get(group, {})
    return {"fio": c.get("fio", ""), "phone": c.get("phone", "")}


def schedule_subjects(day: str, group: str = "") -> list:
    if FILE_SCHEDULE and isinstance(FILE_SCHEDULE, dict):
        key = "default"
        best = ""
        for k in FILE_SCHEDULE:
            if k == "default":
                continue
            if group.startswith(k) and len(k) > len(best):
                best = k
        if best:
            key = best
        entry = FILE_SCHEDULE.get(key, {})
        if isinstance(entry, dict) and day in entry:
            return entry[day] or []
    return []


DAY_SUBJECTS_DEFAULT = {
    "mon": [
        {"subject": "Математика", "teacher": "Иванова И.И.", "room": "Каб. 214", "type": "lection"},
        {"subject": "Информатика", "teacher": "Петров П.П.", "room": "Каб. 312", "type": "practice"},
        {"subject": "Английский язык", "teacher": "Смирнова А.В.", "room": "Каб. 108", "type": "practice"},
    ],
    "tue": [
        {"subject": "Физика", "teacher": "Сидоров С.С.", "room": "Каб. 201", "type": "lection"},
        {"subject": "Русский язык", "teacher": "Козлова К.К.", "room": "Каб. 105", "type": "practice"},
        {"subject": "История", "teacher": "Новиков Н.Н.", "room": "Каб. 303", "type": "lection"},
    ],
    "wed": [
        {"subject": "Информатика", "teacher": "Петров П.П.", "room": "Каб. 312", "type": "practice"},
        {"subject": "Математика", "teacher": "Иванова И.И.", "room": "Каб. 214", "type": "lection"},
        {"subject": "Литература", "teacher": "Белова Б.Б.", "room": "Каб. 110", "type": "lection"},
    ],
    "thu": [
        {"subject": "Английский язык", "teacher": "Смирнова А.В.", "room": "Каб. 108", "type": "practice"},
        {"subject": "Физика", "teacher": "Сидоров С.С.", "room": "Каб. 201", "type": "practice"},
        {"subject": "Химия", "teacher": "Морозова М.М.", "room": "Каб. 215", "type": "lection"},
    ],
    "fri": [
        {"subject": "Математика", "teacher": "Иванова И.И.", "room": "Каб. 214", "type": "practice"},
        {"subject": "История", "teacher": "Новиков Н.Н.", "room": "Каб. 303", "type": "practice"},
        {"subject": "Информатика", "teacher": "Петров П.П.", "room": "Каб. 312", "type": "practice"},
    ],
    "sat": [
        {"subject": "ОБЖ", "teacher": "Волков В.В.", "room": "Онлайн", "type": "lection"},
        {"subject": "География", "teacher": "Лесова Л.Л.", "room": "Онлайн", "type": "lection"},
        {"subject": "Программирование", "teacher": "Петров П.П.", "room": "Онлайн", "type": "practice"},
        {"subject": "Классный час", "teacher": "Куратор группы", "room": "Онлайн", "type": "lection"},
    ],
}


def _hash_admin_key(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _check_admin_token(token: str) -> bool:
    if ADMIN_PASS_FILE.exists():
        try:
            data = json.loads(ADMIN_PASS_FILE.read_text(encoding="utf-8"))
            salt, hashed = data.get("salt", ""), data.get("hash", "")
            if salt and hashed:
                return hmac.compare_digest(_hash_admin_key(token, salt), str(hashed))
        except Exception:
            pass
    return secrets.compare_digest(token, ADMIN_TOKEN)


ADMIN_FAILS: Dict[str, list] = {}
ADMIN_BLOCK_WINDOW = 600
ADMIN_BLOCK_LIMIT = 5


def _admin_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _record_admin_fail(request: Request):
    ip = _admin_ip(request)
    now = time.time()
    ts = [t for t in ADMIN_FAILS.get(ip, []) if now - t < ADMIN_BLOCK_WINDOW]
    ts.append(now)
    ADMIN_FAILS[ip] = ts


def _check_admin_blocked(request: Request):
    ip = _admin_ip(request)
    now = time.time()
    ts = [t for t in ADMIN_FAILS.get(ip, []) if now - t < ADMIN_BLOCK_WINDOW]
    if len(ts) >= ADMIN_BLOCK_LIMIT:
        raise HTTPException(status_code=429,
                            detail="Слишком много неудачных входов. Попробуйте через 10 минут.")


def require_admin(request: Request) -> None:
    _check_admin_blocked(request)
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not _check_admin_token(token):
        if token:
            _record_admin_fail(request)
        raise HTTPException(status_code=401, detail="Требуется доступ администратора")


def _student_from_request(request: Request):
    token = get_bearer_token(request)
    if not token:
        return None
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return _student_by_fio(payload.get("sub"))
    except Exception:
        return None


def _student_by_login(login: str):
    return next((s for s in STUDENTS if s.get("login") == login), None)


def _student_by_fio(fio: str):
    return next((s for s in STUDENTS if s.get("fio") == fio), None)


def _staff_by_fio(fio: str):
    return next((s for s in _all_staff() if s.get("fio") == fio), None)


def _current_role(request: Request) -> str:
    token = get_bearer_token(request)
    if not token:
        return "guest"
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("role", "student")
    except Exception:
        return "guest"


def _identity(request: Request):
    token = get_bearer_token(request)
    if not token:
        return None
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        role = payload.get("role", "student")
        fio = payload.get("sub", "")
        if role == "student":
            return {"role": role, "person": _student_by_fio(fio)}
        return {"role": role, "person": _staff_by_fio(fio)}
    except Exception:
        return None


def _make_token(sub: str, role: str = "student") -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=30),
        "iat": datetime.utcnow(),
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")


@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request):
    _check_login_rate(request)
    student = _student_by_login(req.login.strip())
    if student and student.get("password") == req.password:
        SESSION_USERS[student["fio"]] = student
        token = _make_token(student["fio"])
        _log_login(student["fio"], "student", request)
        return {"access_token": token, "name": student["fio"], "group": student["group"], "role": "student"}

    staff = _staff_by_login(req.login.strip())
    if staff and staff.get("password") == req.password:
        token = _make_token(staff["fio"], staff.get("role", "teacher"))
        _log_login(staff["fio"], staff.get("role", "teacher"), request)
        return {"access_token": token, "name": staff["fio"], "group": staff.get("group", ""), "role": staff.get("role", "teacher")}

    raise HTTPException(status_code=401, detail="Неверный логин или пароль")


@app.post("/api/auth/refresh")
async def api_refresh(request: Request):
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Требуется вход")
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Сессия истекла")
    sub = payload.get("sub", "")
    role = payload.get("role", "student")
    return {"access_token": _make_token(sub, role)}


def _log_login(fio: str, role: str, request: Optional[Request] = None):
    try:
        with open(LOGINS_LOG_FILE, "a", encoding="utf-8") as f:
            line = json.dumps({
                "fio": fio, "role": role,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ip": request.client.host if request and request.client else "",
            }, ensure_ascii=False)
            f.write(line + "\n")
    except Exception:
        pass


def _read_logins():
    out = []
    if LOGINS_LOG_FILE.exists():
        try:
            with open(LOGINS_LOG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
    return out


def get_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.query_params.get("token")


@app.post("/api/auth/verify")
async def verify_token(token: str):
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"valid": True, "user_id": payload.get("sub")}
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/schedule/{day}")
async def get_schedule(day: str, stream: str = "alfa", group: str = ""):
    SLOT_TIMES = {
        "alfa": [
            {"pair": 1, "start": "08:30", "transition": "09:13", "end": "10:00"},
            {"pair": 2, "start": "10:10", "transition": "10:53", "end": "11:40"},
            {"pair": 3, "start": "12:10", "transition": "12:53", "end": "13:40"},
        ],
        "beta": [
            {"pair": 4, "start": "14:00", "transition": "14:43", "end": "15:30"},
            {"pair": 5, "start": "16:00", "transition": "16:43", "end": "17:30"},
            {"pair": 6, "start": "17:50", "transition": "18:33", "end": "19:20"},
        ],
    }
    SATURDAY_SLOTS = [
        {"pair": 1, "start": "09:00", "transition": "09:43", "end": "10:30"},
        {"pair": 2, "start": "10:40", "transition": "11:23", "end": "12:10"},
        {"pair": 3, "start": "12:20", "transition": "13:03", "end": "13:50"},
        {"pair": 4, "start": "14:00", "transition": "14:43", "end": "15:30"},
    ]

    subjects = schedule_subjects(day, group) or DAY_SUBJECTS_DEFAULT.get(day, [])

    if day == "sat":
        slots = SATURDAY_SLOTS
    else:
        slots = SLOT_TIMES.get(stream, SLOT_TIMES["alfa"])

    lessons = []
    for i, slot in enumerate(slots):
        subj = subjects[i] if i < len(subjects) else {"subject": "Окно", "teacher": "—", "room": "—", "type": "lection"}
        lessons.append({
            "pair": slot["pair"],
            "time_start": slot["start"],
            "time_end": slot["end"],
            "transition": slot["transition"],
            "subject": subj["subject"],
            "teacher": subj["teacher"],
            "room": subj["room"],
            "type": subj["type"],
        })

    return {"lessons": lessons}


def _grade_list_view(marks: list) -> list:
    return [
        {"value": int(m.get("value", 0)), "date": m.get("date", ""), "comment": m.get("comment", "")}
        for m in marks
    ]


def _group_grade_store(group: str) -> dict:
    if FILE_GRADES and isinstance(FILE_GRADES, dict):
        entry = FILE_GRADES.get(group) or FILE_GRADES.get("default")
        if isinstance(entry, dict):
            store = entry.get("students", {})
            if isinstance(store, dict):
                return store
    return {}


def _student_fio(login: str) -> str:
    s = next((x for x in STUDENTS if x.get("login") == login), None)
    return (s or {}).get("fio", login)


def _student_grades_view(mymarks: list) -> dict:
    by_subj = {}
    for m in mymarks:
        name = m.get("subject", "—")
        by_subj.setdefault(name, []).append(m)
    subjects, total, count = [], 0, 0
    for name in by_subj:
        vals = [int(m.get("value", 0)) for m in by_subj[name]]
        total += sum(vals)
        count += len(vals)
        subjects.append({
            "name": name,
            "marks": _grade_list_view(by_subj[name]),
            "average": f"{sum(vals) / len(vals):.1f}",
        })
    avg = f"{total / count:.1f}" if count else "0.0"
    return {"average": avg, "total": total, "subjects": sorted(subjects, key=lambda s: s["name"])}


def _group_taught_subjects(group: str) -> list:
    out = []
    for day in ("mon", "tue", "wed", "thu", "fri", "sat"):
        for lesson in (schedule_subjects(day, group) or []):
            name = lesson.get("subject")
            if name and name not in out:
                out.append(name)
    return out


@app.get("/api/grades")
async def get_grades(request: Request):
    student = _student_from_request(request)
    group = student.get("group") if student else "1ИС-26"

    if FILE_GRADES and isinstance(FILE_GRADES, dict):
        entry = FILE_GRADES.get(group) or FILE_GRADES.get("default")
        if isinstance(entry, dict):
            store = entry.get("students", {})
            if student and isinstance(store, dict) and store.get(student.get("login", "")):
                return _student_grades_view(store[student["login"]])
            if "subjects" in entry and isinstance(entry.get("subjects"), list):
                return {k: entry[k] for k in ("average", "total", "subjects") if k in entry}

    def marks(vals, comments):
        return [{"value": v, "date": d, "comment": c} for v, d, c in zip(vals, DATES, comments)]

    def subj(name, vals, comments):
        return {
            "name": name,
            "marks": marks(vals, comments),
            "average": f"{sum(vals)/len(vals):.1f}",
        }

    DATES = ["05.09", "08.09", "10.09", "15.09", "17.09", "19.09"]
    return {
        "average": "4.2",
        "total": 47,
        "subjects": [
            subj("Математика", [5, 5, 4, 5, 4, 5], ["Контрольная работа", "", "", "Самостоятельная работа", "", ""]),
            subj("Информатика", [5, 5, 5, 4, 5], ["Практическое задание", "", "Домашняя работа", "", "Лабораторная работа"]),
            subj("Английский язык", [4, 3, 4, 5, 4], ["Диктант", "", "", "Устный ответ", ""]),
            subj("Русский язык", [4, 4, 3, 4], ["Изложение", "", "Диктант", ""]),
            subj("Физика", [5, 4, 5, 4, 5, 5], ["Лабораторная работа №1", "", "Лабораторная работа №2", "", "Контрольная работа", ""]),
        ],
    }


@app.get("/api/teacher/journal")
async def teacher_journal(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    store = _group_grade_store(group)
    students = []
    for s in STUDENTS:
        if s.get("group") != group:
            continue
        students.append({
            "login": s.get("login", ""),
            "fio": s.get("fio", ""),
            "marks": _grade_list_view(store.get(s.get("login"), [])),
        })
    return {"group": group, "subjects": _group_taught_subjects(group), "students": students}


@app.post("/api/teacher/journal/grade")
async def teacher_add_grade(body: TeacherGradeBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    body_subject = body.subject.strip() or "Математика"
    if not (1 <= int(body.value) <= 5):
        raise HTTPException(status_code=400, detail="Оценка должна быть от 1 до 5")
    student = next((s for s in STUDENTS if s.get("login") == body.login), None)
    if not student or student.get("group") != group:
        raise HTTPException(status_code=404, detail="Студент не найден в вашей группе")
    data = FILE_GRADES if isinstance(FILE_GRADES, dict) else {}
    entry = data.setdefault(group, {})
    store = entry.setdefault("students", {})
    marks = store.setdefault(body.login, [])
    date = body.date.strip() or datetime.now().strftime("%d.%m.%Y")
    replaced = False
    for m in marks:
        if m.get("subject") == body_subject and m.get("date") == date:
            m["value"] = int(body.value)
            m["comment"] = body.comment.strip()
            replaced = True
            break
    if not replaced:
        marks.append({"subject": body_subject, "value": int(body.value), "date": date, "comment": body.comment.strip()})
    _save_json(GRADES_FILE, data)
    reload_data_files()
    _log_admin(f"Преподаватель {identity['person'].get('fio', '')} выставил оценку: {body_subject} = {body.value} ({body.login}, {date})")
    try:
        push_service.send_push({
            "title": "Новая оценка",
            "body": f"{body_subject}: {body.value} за {date}",
            "url": "/grades",
        }, user=body.login)
    except Exception:
        pass
    return {"ok": True, "marks": _grade_list_view(store[body.login])}


@app.get("/api/teacher/homework")
async def teacher_homework(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    teacher_subjects = set(_group_taught_subjects(group))
    items = []
    for i, hw in enumerate(FILE_HOMEWORK or []):
        if not isinstance(hw, dict):
            continue
        if hw.get("subject") not in teacher_subjects:
            continue
        item_id = hashlib.md5(f"{hw.get('subject','')}|{hw.get('task','')}".encode()).hexdigest()[:8]
        checks = (FILE_HW_CHECKS or {}).get(item_id, {}) or {}
        items.append({
            "id": item_id,
            "subject": hw.get("subject", ""),
            "task": hw.get("task", ""),
            "deadline": hw.get("deadline", ""),
            "badge": hw.get("badge", ""),
            "urgent": bool(hw.get("urgent")),
            "checks": checks,
        })
    students = [{
        "login": s.get("login", ""),
        "fio": s.get("fio", ""),
    } for s in STUDENTS if s.get("group") == group]
    return {"group": group, "items": items, "students": students}


@app.post("/api/teacher/homework/check")
async def teacher_homework_check(body: HomeworkCheckBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    data = FILE_HW_CHECKS if isinstance(FILE_HW_CHECKS, dict) else {}
    if not body.item_id or not body.login:
        raise HTTPException(status_code=400, detail="Не указаны item_id/login")
    entry = data.setdefault(body.item_id, {})
    grade = body.grade if body.grade is not None else (entry.get(body.login, {}).get("grade") if isinstance(entry.get(body.login), dict) else None)
    entry[body.login] = {"done": body.done, "grade": grade}
    _save_json(HOMEWORK_CHECKS_FILE, data)
    reload_data_files()
    return {"ok": True, "item_id": body.item_id, "login": body.login, "checks": entry[body.login]}


@app.get("/api/me/debts")
async def my_debts(request: Request):
    student = _student_from_request(request)
    if not student:
        raise HTTPException(status_code=401, detail="Требуется вход студента")
    grades = await get_grades(request)
    debts, ok_list = [], []
    for subj in grades.get("subjects", []):
        vals = [int(m.get("value", 0)) for m in subj.get("marks", []) if isinstance(m.get("value"), (int, float))]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        item = {"subject": subj["name"], "average": round(avg, 2), "marks": vals}
        if avg < 3.5:
            need = max(1, int(4.0 * (len(vals) + 1) - sum(vals) + 0.999))
            if need <= 5:
                item["need"] = need
            debts.append(item)
        else:
            ok_list.append(item)
    return {"debts": debts, "count": len(debts), "ok": ok_list}


@app.post("/api/share")
async def create_share(request: Request):
    student = _student_from_request(request)
    if not student:
        raise HTTPException(status_code=401, detail="Требуется вход студента")
    grades = await get_grades(request)
    group = student.get("group", "")
    attendance = FILE_ATTENDANCE.get(group, []) if isinstance(FILE_ATTENDANCE, dict) else []
    my_att = [a for a in attendance if a.get("login") == student.get("login")]
    payload = {
        "fio": student.get("fio", ""),
        "login": student.get("login", ""),
        "group": group,
        "average": grades.get("average"),
        "total": grades.get("total"),
        "subjects": grades.get("subjects", []),
        "attendance_marked": len(my_att),
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    token = secrets.token_urlsafe(8)
    shares = dict(FILE_SHARES or {})
    now = datetime.now()
    shares = {k: v for k, v in shares.items() if v.get("expires_at", "") > now.isoformat()}
    shares[token] = {"payload": payload, "expires_at": (now + timedelta(hours=24)).isoformat()}
    _save_json(SHARES_FILE, shares)
    reload_data_files()
    return {"ok": True, "url": f"/?share={token}"}


@app.get("/api/share/{token}")
async def get_share(token: str):
    shares = dict(FILE_SHARES or {})
    entry = shares.get(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Ссылка не найдена или истекла")
    if entry.get("expires_at", "") < datetime.now().isoformat():
        raise HTTPException(status_code=404, detail="Срок действия ссылки истек")
    return {"ok": True, **entry["payload"]}


@app.get("/api/homework")
async def get_homework():
    return FILE_HOMEWORK or DEFAULT_HOMEWORK


@app.get("/api/annual")
async def get_annual():
    data = FILE_ANNUAL or DEFAULT_ANNUAL
    upcoming = []
    today = datetime.now().date()
    for e in data:
        d = _parse_date(e.get("date"))
        if d and d >= today:
            upcoming.append(e)
    upcoming.sort(key=lambda e: str(e.get("date", "")))
    return {"events": data, "next": upcoming[:3]}


def _parse_date(value) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


@app.get("/api/canteen")
async def get_canteen():
    return FILE_CANTEEN or DEFAULT_CANTEEN


@app.get("/api/portfolio")
async def get_portfolio():
    return FILE_PORTFOLIO or DEFAULT_PORTFOLIO


@app.get("/api/replacements")
async def get_replacements():
    return FILE_REPLACEMENTS or DEFAULT_REPLACEMENTS


_SUBJECT_AVERAGES = {
    "Математика": 4.8,
    "Информатика": 4.8,
    "Английский язык": 4.0,
    "Русский язык": 3.8,
    "Физика": 4.7,
    "История": 4.3,
}


@app.get("/api/exams")
async def get_exams():
    data = FILE_EXAMS or DEFAULT_EXAMS
    exams = []
    for e in data.get("exams", []):
        subject = e.get("subject", "")
        avg = _SUBJECT_AVERAGES.get(subject, 4.5)
        allowed = avg >= 3.0
        exams.append({
            **e,
            "average": f"{avg:.1f}",
            "access": "Допущен" if allowed else "Не допущен",
            "accessReason": "Средний балл выше 3.0" if allowed else "Средний балл ниже 3.0",
        })
    return {
        "session": data.get("session", "Зимняя сессия 2026/27"),
        "exams": exams,
        "consultations": data.get("consultations", []),
        "retakes": data.get("retakes", ""),
    }


@app.post("/api/subscribe")
async def subscribe(data: dict):
    from push_service import add_subscription
    subscription = data.get("subscription")
    if not subscription:
        raise HTTPException(status_code=400, detail="No subscription")
    add_subscription(subscription)
    return {"ok": True, "message": "Подписка сохранена"}


@app.post("/api/send-push")
async def send_push(data: dict):
    from push_service import send_push_to_subscriptions
    title = data.get("title", "IT Москва Колледж")
    body = data.get("body", "Новое обновление")
    return send_push_to_subscriptions({"title": title, "body": body, "url": "/"})


@app.get("/api/bells")
async def get_bells():
    return FILE_BELLS or DEFAULT_BELLS


@app.get("/api/news")
async def get_news(request: Request):
    news = FILE_NEWS or DEFAULT_NEWS
    identity = _identity(request)
    if not identity or identity["role"] != "student":
        return news
    group = (identity["person"] or {}).get("group", "")
    filtered = [n for n in news if not n.get("groups") or group in n.get("groups", [])]
    return filtered


@app.get("/api/vapid-public-key")
async def get_vapid_public_key():
    from push_service import get_vapid_public_key
    return {"key": get_vapid_public_key()}


@app.post("/api/push/subscribe")
async def push_subscribe(body: PushSubscribeBody, request: Request):
    identity = _identity(request)
    user = (identity or {}).get("person", {}).get("login", "") or body.user
    from push_service import add_subscription
    try:
        add_subscription(dict(body.subscription), user=user)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(body: PushSubscribeBody):
    from push_service import remove_subscription
    try:
        remove_subscription(dict(body.subscription))
        return {"ok": True}
    except Exception:
        return {"ok": True}


_weather_cache = {"ts": 0, "data": None}
_weather_lock = (None,)


async def _fetch_weather():
    import httpx
    now = time.time()
    if _weather_cache["data"] and now - _weather_cache["ts"] < 600:
        return _weather_cache["data"]
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=55.7558&longitude=37.6173"
           "&current=temperature_2m,weather_code,wind_speed_10m,precipitation"
           "&hourly=temperature_2m,precipitation,weather_code"
           "&forecast_days=2&timezone=Europe%2FMoscow")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            j = resp.json()
            cur = j.get("current", {}) or {}
            hourly = j.get("hourly", {}) or {}
            temps = hourly.get("temperature_2m", []) or []
            pops = hourly.get("precipitation", []) or []
            today = temps[:24]
            data = {
                "temp": cur.get("temperature_2m"),
                "code": cur.get("weather_code"),
                "wind": cur.get("wind_speed_10m"),
                "precip": cur.get("precipitation"),
                "min": min(today) if today else None,
                "max": max(today) if today else None,
                "rain_today": sum(1 for p in (pops[:24] if pops else []) if (p or 0) > 0),
                "source": "open-meteo",
            }
            _weather_cache["data"] = data
            _weather_cache["ts"] = now
            return data
    except Exception:
        return _weather_cache["data"]


@app.get("/api/weather")
async def api_weather():
    data = await _fetch_weather()
    if data is None:
        raise HTTPException(status_code=503, detail="Погода временно недоступна")
    return data


@app.get("/api/me/rank")
async def my_rank(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "student":
        raise HTTPException(status_code=403, detail="Только студент")
    group = identity["person"].get("group", "")
    login = identity["person"].get("login", "")
    grades = FILE_GRADES or {}
    studs = (grades.get(group, {}).get("students", {}) or {})
    rows = []
    for s_login, marks in studs.items():
        if not isinstance(marks, list) or not marks:
            continue
        vals = [m.get("value") for m in marks if isinstance(m.get("value"), (int, float))]
        if not vals:
            continue
        rows.append({"login": s_login, "avg": round(sum(vals) / len(vals), 2)})
    rows.sort(key=lambda x: x["avg"], reverse=True)
    place = next((i + 1 for i, r in enumerate(rows) if r["login"] == login), None)
    mine = next((r for r in rows if r["login"] == login), None)
    return {
        "place": place,
        "total": len(rows),
        "average": mine["avg"] if mine else None,
        "above": (place - 1) if place is not None else 0,
    }


@app.get("/api/profile")
async def get_profile(request: Request):
    token = get_bearer_token(request)
    identity = None
    if token:
        try:
            payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            role = payload.get("role", "student")
            if role == "student":
                identity = {"role": role, "person": _student_by_fio(payload.get("sub"))}
            else:
                identity = {"role": role, "person": _staff_by_fio(payload.get("sub"))}
        except Exception:
            identity = None

    if identity and identity["person"]:
        person = identity["person"]
        role = identity["role"]
        if role != "student":
            return {
                "name": person.get("fio", "Сотрудник"),
                "initials": "".join([w[0] for w in person.get("fio", "").split() if w])[:2].upper() or "С",
                "course": "",
                "school": "ГБПОУ ИТ Москвы",
                "advisor": "",
                "advisorPhone": "",
                "group": person.get("group", ""),
                "speciality": "Преподаватель" if role == "teacher" else "Куратор группы",
                "specialityType": "",
                "forma": "",
                "address": "",
                "attendance": 100,
                "homeworkPercent": 0,
                "real": True,
                "role": role,
            }
        name = person.get("fio") or "Пользователь"
        initials = "".join([w[0] for w in name.split() if w])[:2].upper() or "П"
        group = person.get("group") or "—"
        course = "1 курс"
        spec = speciality_info(group)
        curator = group_curator(group)
        att_pct, _ = _compute_attendance(group)
        return {
            "name": name,
            "initials": initials,
            "course": course,
            "school": "ГБПОУ ИТ Москвы",
            "advisor": curator.get("fio") or "—",
            "advisorPhone": curator.get("phone", ""),
            "group": group,
            "speciality": spec["name"],
            "specialityType": spec["type"],
            "forma": person.get("forma") or "Бюджет",
            "address": spec["address"],
            "attendance": att_pct,
            "homeworkPercent": 87,
            "real": True,
            "role": "student",
        }

    return {
        "name": "Иванов Петр",
        "initials": "ИП",
        "course": "2 курс",
        "school": "ГБПОУ ИТ Москвы",
        "advisor": "Сидорова М.В.",
        "advisorPhone": "",
        "group": "ИС-21",
        "speciality": "Информационные системы и программирование",
        "specialityType": "специальность",
        "forma": "Бюджет",
        "address": "ул. Академика Миллионщикова, д. 20",
        "attendance": 94,
        "homeworkPercent": 87,
        "real": False,
        "role": "guest",
    }


_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб"]
_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat"]


def _stable_seed(text: str) -> int:
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0x7FFFFFFF
    return h


def _compute_attendance(group: str):
    file_data = None
    if FILE_ATTENDANCE and isinstance(FILE_ATTENDANCE, dict):
        file_data = FILE_ATTENDANCE.get(group)

    today = datetime.utcnow()
    days = []
    d = today
    while len(days) < 10 and len(days) < 20:
        wd = d.weekday()
        if wd < 6:
            days.append(d)
        d = d - timedelta(days=1)
    days.reverse()

    result_days = []
    total_present = total_lessons = 0

    if file_data:
        for row in file_data:
            for lesson in row.get("lessons", []):
                total_lessons += 1
                if lesson.get("status") == "present":
                    total_present += 1
        result_days = file_data
    else:
        for day in days:
            key = _DAY_KEYS[day.weekday()]
            subjects = schedule_subjects(key, group) or DAY_SUBJECTS_DEFAULT.get(key, [])
            lessons = []
            present = 0
            for subj in subjects:
                seed = _stable_seed(group + "|" + day.strftime("%d.%m") + "|" + subj["subject"])
                r = seed % 100
                status = "present" if r < 94 else ("late" if r < 97 else "absent")
                if status == "present":
                    present += 1
                lessons.append({"subject": subj["subject"], "status": status})
            total_lessons += len(lessons)
            total_present += present
            if lessons:
                result_days.append({
                    "date": day.strftime("%d.%m"),
                    "weekday": _WEEKDAYS[day.weekday()],
                    "present": present,
                    "total": len(lessons),
                    "lessons": lessons,
                })

    percent = round(total_present * 100 / total_lessons) if total_lessons else 0
    return percent, result_days


@app.get("/api/attendance")
async def get_attendance(request: Request):
    student = _student_from_request(request)
    if student:
        group = student.get("group") or ""
    else:
        group = "1ИС-26"

    percent, result_days = _compute_attendance(group)
    return {"group": group, "attendance": percent, "days": result_days}


@app.get("/api/student-card")
async def get_student_card(request: Request):
    student = _student_from_request(request)
    if not student:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    fio = student.get("fio") or "—"
    group = student.get("group") or "—"
    speciality = speciality_info(group)["name"]
    college = "ГБПОУ ИТ Москвы"

    payload = {"name": fio, "group": group, "college": college}
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(json.dumps(payload, ensure_ascii=False))
    qr.make(fit=True)
    img = qr.make_image(image_factory=SvgPathImage)
    svg = img.to_string()
    if isinstance(svg, bytes):
        svg = svg.decode("utf-8")

    return {
        "fio": fio,
        "group": group,
        "speciality": speciality,
        "college": college,
        "svg": svg,
    }


@app.get("/api/admin/data")
async def admin_data(request: Request):
    require_admin(request)
    return {
        "news": FILE_NEWS or [],
        "replacements": FILE_REPLACEMENTS or {"date": "", "items": []},
    }


@app.post("/api/admin/news")
async def admin_add_news(item: NewsItem, request: Request):
    require_admin(request)
    data = list(FILE_NEWS or [])
    it = item.model_dump()
    if not it.get("id"):
        it["id"] = f"n{int(datetime.utcnow().timestamp() * 1000)}"
    data.insert(0, it)
    _save_json(NEWS_FILE, data)
    reload_data_files()
    _log_admin(f"Добавлена новость: {it.get('title', '')[:60]}")
    return {"ok": True, "news": FILE_NEWS}


@app.delete("/api/admin/news/{news_id}")
async def admin_delete_news(news_id: str, request: Request):
    require_admin(request)
    data = [n for n in (FILE_NEWS or []) if n.get("id") != news_id]
    _save_json(NEWS_FILE, data)
    reload_data_files()
    _log_admin(f"Удалена новость: {news_id}")
    return {"ok": True, "news": FILE_NEWS}


@app.post("/api/admin/replacements")
async def admin_set_replacements(body: ReplacementsBody, request: Request):
    require_admin(request)
    data = {"date": body.date or "Ближайшие дни", "items": body.items}
    _save_json(REPLACEMENTS_FILE, data)
    reload_data_files()
    _log_admin(f"Обновлены замены: {data['date']} ({len(body.items)} шт.)")
    if body.items:
        try:
            push_service.send_push({
                "title": "Изменения в расписании",
                "body": f"На {data['date']} — посмотрите замены",
                "url": "/",
            })
        except Exception:
            pass
    return {"ok": True, "replacements": FILE_REPLACEMENTS}


@app.post("/api/admin/reload")
async def admin_reload(request: Request):
    require_admin(request)
    reload_data_files()
    return {"ok": True}


@app.get("/api/tickets")
async def get_my_tickets(request: Request):
    student = _student_from_request(request)
    if not student:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    data = FILE_TICKETS or DEFAULT_TICKETS
    mine = [t for t in data.get("tickets", []) if t.get("login") == student.get("login")]
    mine.sort(key=lambda t: str(t.get("created", "")), reverse=True)
    return {"tickets": mine}


@app.post("/api/tickets")
async def create_ticket(body: TicketCreate, request: Request):
    student = _student_from_request(request)
    if not student:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    data = dict(FILE_TICKETS or DEFAULT_TICKETS)
    tickets = list(data.get("tickets", []))
    ticket = {
        "id": f"t{int(datetime.utcnow().timestamp() * 1000)}",
        "login": student.get("login", ""),
        "fio": student.get("fio", ""),
        "group": student.get("group", ""),
        "topic": body.topic,
        "text": body.text,
        "status": "new",
        "created": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    }
    tickets.insert(0, ticket)
    data["tickets"] = tickets
    _save_json(TICKETS_FILE, data)
    reload_data_files()
    return {"ok": True, "ticket": ticket}


@app.get("/api/admin/tickets")
async def admin_tickets(request: Request):
    require_admin(request)
    data = FILE_TICKETS or DEFAULT_TICKETS
    tickets = sorted(data.get("tickets", []), key=lambda t: str(t.get("created", "")), reverse=True)
    return {"tickets": tickets}


@app.post("/api/admin/tickets/{ticket_id}")
async def admin_set_ticket_status(ticket_id: str, body: TicketStatus, request: Request):
    require_admin(request)
    data = dict(FILE_TICKETS or DEFAULT_TICKETS)
    tickets = list(data.get("tickets", []))
    for t in tickets:
        if t.get("id") == ticket_id:
            t["status"] = body.status
            break
    data["tickets"] = tickets
    _save_json(TICKETS_FILE, data)
    reload_data_files()
    _log_admin(f"Тикет {ticket_id}: статус {body.status}")
    return {"ok": True, "tickets": tickets}


@app.post("/api/admin/reset-password")
async def admin_reset_password(body: ResetPassword, request: Request):
    require_admin(request)
    student = _student_by_login(body.login.strip())
    if not student:
        raise HTTPException(status_code=404, detail="Студент не найден")
    student["password"] = body.password
    _save_json(STUDENTS_FILE, STUDENTS)
    reload_accounts()
    _log_admin(f"Сброс пароля: {body.login}")
    return {"ok": True, "message": f"Пароль для {body.login} обновлён"}


@app.post("/api/admin/announce")
async def admin_announce(body: AnnounceBody, request: Request):
    require_admin(request)
    result = push_service.send_push({
        "title": body.title or "IT Москва Колледж",
        "body": body.body or "",
        "url": body.url or "/",
    }, user=body.login or "")
    target = f" {body.login}" if body.login else ""
    _log_admin(f"Рассылка уведомления{target}: {body.title}")
    return result


@app.get("/api/admin/log")
async def admin_log(request: Request):
    require_admin(request)
    out = []
    if ADMIN_LOG_FILE.exists():
        try:
            with open(ADMIN_LOG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
    return {"log": out[-200:]}


def _log_admin(action: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(ADMIN_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "action": action}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# --- Учебные материалы, кружки, потерянные вещи, FAQ ---

@app.get("/api/materials")
async def get_materials():
    return {"materials": FILE_MATERIALS or DEFAULT_MATERIALS}


@app.get("/api/clubs")
async def get_clubs():
    return {"clubs": FILE_CLUBS or DEFAULT_CLUBS}


@app.get("/api/lost")
async def get_lost():
    return {"lost": FILE_LOST or DEFAULT_LOST}


@app.get("/api/faq")
async def get_faq():
    return {"faq": FILE_FAQ or DEFAULT_FAQ}


# --- Новости: лайки и комментарии ---

def _news_meta() -> dict:
    m = FILE_NEWS_META
    if not isinstance(m, dict):
        m = {}
    m.setdefault("likes", {})
    m.setdefault("comments", {})
    return m


@app.get("/api/news/meta")
async def get_news_meta():
    m = _news_meta()
    return {"likes": m["likes"], "comments": m["comments"]}


@app.post("/api/news/{news_id}/like")
async def like_news(news_id: str, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "student":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    m = _news_meta()
    likes = m["likes"].setdefault(news_id, [])
    if identity["person"]["fio"] not in likes:
        likes.append(identity["person"]["fio"])
    m["likes"][news_id] = sorted(set(likes))
    _save_json(NEWS_META_FILE, m)
    reload_data_files()
    return {"likes": len(m["likes"][news_id]), "liked": True}


@app.delete("/api/news/{news_id}/like")
async def unlike_news(news_id: str, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "student":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    m = _news_meta()
    likes = m["likes"].setdefault(news_id, [])
    if identity["person"]["fio"] in likes:
        likes.remove(identity["person"]["fio"])
    m["likes"][news_id] = list(dict.fromkeys(likes))
    _save_json(NEWS_META_FILE, m)
    reload_data_files()
    return {"likes": len(m["likes"][news_id]), "liked": False}


@app.post("/api/news/{news_id}/comment")
async def comment_news(news_id: str, body: CommentBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "student":
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой комментарий")
    m = _news_meta()
    comments = m["comments"].setdefault(news_id, [])
    comments.append({
        "name": identity["person"]["fio"],
        "text": text[:500],
        "ts": datetime.now().strftime("%d.%m %H:%M"),
    })
    m["comments"][news_id] = comments[-50:]
    _save_json(NEWS_META_FILE, m)
    reload_data_files()
    return {"comments": m["comments"][news_id]}


# --- Свободные аудитории на текущий час ---

@app.get("/api/rooms/free")
async def free_rooms():
    known: set = set()
    entries = list((FILE_SCHEDULE or {}).values()) + [DAY_SUBJECTS_DEFAULT]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for day, subjs in entry.items():
            if not isinstance(subjs, list):
                continue
            for s in subjs:
                room = (s.get("room") or "").strip()
                if room and room not in ("—", "Онлайн"):
                    known.add(room)
    now = datetime.now()
    wd = now.weekday()
    if wd >= 5:
        day_key = None
    else:
        day_key = _DAY_KEYS[wd]
    if day_key is None:
        return {"rooms": sorted(known), "current": "Выходной день — все аудитории свободны", "free_all": True}
    bells = FILE_BELLS or DEFAULT_BELLS
    pairs = bells.get("first", []) + bells.get("second", [])
    if not pairs:
        return {"rooms": sorted(known), "current": "", "free_all": True}
    now_min = now.hour * 60 + now.minute
    current_pair = None
    for p in pairs:
        try:
            sh, sm = [int(x) for x in str(p.get("start", "0:00")).split(":")]
            eh, em = [int(x) for x in str(p.get("end", "0:00")).split(":")]
        except Exception:
            continue
        if sh * 60 + sm <= now_min < eh * 60 + em:
            current_pair = p
            break
    if current_pair is None:
        return {"rooms": sorted(known), "current": "Сейчас перемена — аудитории свободны", "free_all": True}
    occupied: set = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        subjs = entry.get(day_key)
        if not isinstance(subjs, list):
            continue
        for s in subjs:
            room = (s.get("room") or "").strip()
            if room and room not in ("—", "Онлайн"):
                occupied.add(room)
    free = sorted(r for r in known if r not in occupied)
    pair_label = str(current_pair.get("pair", ""))
    return {
        "rooms": free,
        "current": f"{pair_label} пара ({current_pair.get('start','')}–{current_pair.get('end','')})",
        "free_all": False,
    }


# --- Смена пароля самим пользователем ---

@app.post("/api/me/password")
async def change_password(body: ChangePasswordBody, request: Request):
    identity = _identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    person = identity["person"]
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if person.get("password") != body.current:
        raise HTTPException(status_code=400, detail="Текущий пароль неверен")
    if not body.new_password or len(body.new_password) < 4:
        raise HTTPException(status_code=400, detail="Новый пароль слишком короткий")
    person["password"] = body.new_password
    if identity["role"] == "student":
        _save_json(STUDENTS_FILE, STUDENTS)
        reload_accounts()
    else:
        _save_json(STAFF_FILE, FILE_STAFF)
        reload_data_files()
    _log_admin(f"Пользователь сменил пароль: {identity['person']['fio']}")
    return {"ok": True}


# --- Преподаватель: отметка посещаемости, куратор: дашборд ---

@app.get("/api/teacher/attendance")
async def teacher_attendance(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    percent, days = _compute_attendance(group)
    return {"group": group, "attendance": percent, "days": [d["date"] for d in days[-10:]]}


@app.put("/api/teacher/attendance")
async def teacher_attendance_save(body: AttendanceMarkBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    valid = {"present", "late", "absent"}
    lessons = []
    for lesson in body.lessons or []:
        status = str(lesson.get("status", "")).lower()
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Недопустимый статус: {status}")
        lessons.append({"subject": str(lesson.get("subject", "")), "status": status})
    if not lessons:
        raise HTTPException(status_code=400, detail="Нет данных об отметке")
    att = FILE_ATTENDANCE if isinstance(FILE_ATTENDANCE, dict) else {}
    group_att = att.setdefault(group, [])

    date = (body.date or "").strip() or datetime.now().strftime("%d.%m")
    weekday = _rus_weekday(datetime.now().weekday())
    merged = {}
    for lesson in group_att:
        if lesson.get("date") == date:
            merged = {ll.get("subject"): ll.get("status") for ll in lesson.get("lessons", [])}
            break
    for lesson in lessons:
        merged[lesson["subject"]] = lesson["status"]
    row = {"date": date, "weekday": weekday, "lessons": [{"subject": s, "status": st} for s, st in merged.items()]}
    new_rows = [r for r in group_att if r.get("date") != date]
    new_rows.append(row)
    new_rows.sort(key=lambda r: str(r.get("date", "")))
    att[group] = new_rows
    _save_json(ATTENDANCE_FILE, att)
    reload_data_files()
    _log_admin(f"Преподаватель отметил посещаемость группы {group} за {date}")
    return {"ok": True, "date": date, "lessons": row["lessons"]}


def _rus_weekday(wd: int) -> str:
    return ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"][wd] if wd < 6 else ""


@app.get("/api/curator/dashboard")
async def curator_dashboard(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "curator":
        raise HTTPException(status_code=403, detail="Доступ только куратору")
    group = identity["person"].get("group", "")
    percent, days = _compute_attendance(group)
    students_count = sum(1 for s in STUDENTS if s.get("group") == group)
    avg = None
    rating = []
    grades = FILE_GRADES or {}
    if grades.get(group):
        all_vals = []
        for subj in grades[group].get("subjects", []):
            vals = [m.get("value") for m in subj.get("marks", []) if isinstance(m.get("value"), (int, float))]
            all_vals += vals
        for mark_list in (grades[group].get("students", {}) or {}).values():
            all_vals += [m.get("value") for m in mark_list if isinstance(m.get("value"), (int, float))]
        if all_vals:
            avg = round(sum(all_vals) / len(all_vals), 2)
        studs = grades[group].get("students", {}) or {}
        for login, marks in studs.items():
            if not isinstance(marks, list) or not marks:
                continue
            vals = [m.get("value") for m in marks if isinstance(m.get("value"), (int, float))]
            if not vals:
                continue
            person = next((s for s in STUDENTS if s.get("login") == login), {})
            name = person.get("name", login)
            rating.append({"name": name, "login": login, "avg": round(sum(vals)/len(vals), 2)})
        rating.sort(key=lambda x: x["avg"], reverse=True)
    tickets = [t for t in (FILE_TICKETS or {}).get("tickets", []) if t.get("group") == group]
    return {
        "group": group,
        "students": students_count,
        "attendance": percent,
        "days": len(days),
        "average": avg,
        "tickets": tickets[-20:],
        "rating": rating,
    }


# --- Админ: редактор файлов данных, backup/restore ---

VALID_FILE_NAMES = set(DATA_FILES_MAP.keys())


@app.get("/api/admin/file/{name}")
async def admin_get_file(name: str, request: Request):
    require_admin(request)
    if name not in VALID_FILE_NAMES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    m = DATA_FILES_MAP[name]
    if not m.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return {"name": name, "content": _read_json(m, None)}


@app.put("/api/admin/file/{name}")
async def admin_put_file(name: str, body: FilePayload, request: Request):
    require_admin(request)
    if name not in VALID_FILE_NAMES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    content = body.content
    if not isinstance(content, (dict, list)):
        raise HTTPException(status_code=400, detail="Содержимое должно быть JSON-объектом или списком")
    try:
        s = json.dumps(content, ensure_ascii=False)
        json.loads(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный JSON")
    err = _validate_file(name, content)
    if err:
        raise HTTPException(status_code=400, detail=f"Файл не прошёл проверку: {err}")
    _save_json(DATA_FILES_MAP[name], content)
    reload_data_files()
    _log_admin(f"Изменён файл данных: {name}")
    return {"ok": True}


def _validate_file(name, data):
    rules = {
        "news": ("list",),
        "materials": ("list",),
        "clubs": ("list",),
        "lost": ("list",),
        "faq": ("list",),
        "polls": ("list",),
        "birthdays": ("list",),
        "news-meta": ("dict", ("likes", "comments")),
        "replacements": ("dict", ("date", "items")),
        "exams": ("dict", ("exams",)),
        "bells": ("dict", ("first", "second")),
        "homework": ("list",),
        "annual": ("dict", ("semesters",)),
        "canteen": ("dict", ("days",)),
        "attendance": ("dict",),
        "grades": ("dict",),
        "schedule": ("dict",),
        "specialities": ("list",),
        "tickets": ("dict",),
        "portfolio": ("list",),
        "staff": ("dict",),
        "references": ("dict",),
    }
    if not rules.get(name):
        return None
    kind, keys = rules[name][0], rules[name][1] if len(rules[name]) > 1 else ()
    kind_type = {"list": list, "dict": dict}.get(kind)
    if kind_type is None:
        return None
    if not isinstance(data, kind_type):
        return f"ожидается {kind}, получено {type(data).__name__}"
    if kind == "dict" and keys:
        missing = [k for k in keys if k not in data]
        if missing:
            return f"нет ключей: {', '.join(missing)}"
    return None


@app.get("/api/admin/backup")
async def admin_backup(request: Request):
    require_admin(request)
    buffer = _make_backup_zip()
    _log_admin("Создана резервная копия данных")
    filename = f"mesh-backup-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _make_backup_zip() -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in DATA_FILES_MAP.items():
            if path.exists():
                zf.writestr(f"data/{name}.json", path.read_text(encoding="utf-8"))
        extra = {"homework-checks": HOMEWORK_CHECKS_FILE}
        for name, path in extra.items():
            if path.exists():
                zf.writestr(f"data/{name}.json", path.read_text(encoding="utf-8"))
    buffer.seek(0)
    return buffer


BACKUP_DIR = BASE_DIR / "backup"


def _auto_backup_once():
    BACKUP_DIR.mkdir(exist_ok=True)
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        target = BACKUP_DIR / f"auto-{stamp}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, path in DATA_FILES_MAP.items():
                if path.exists():
                    zf.writestr(f"data/{name}.json", path.read_text(encoding="utf-8"))
            if HOMEWORK_CHECKS_FILE.exists():
                zf.writestr("data/homework-checks.json", HOMEWORK_CHECKS_FILE.read_text(encoding="utf-8"))
        old = sorted(BACKUP_DIR.glob("auto-*.zip"))
        limit = int(_read_settings().get("backup_days", 7) or 7)
        while len(old) > max(limit, 1):
            (BACKUP_DIR / old.pop(0)).unlink(missing_ok=True)
    except Exception:
        pass


async def _auto_backup_loop():
    while True:
        try:
            await asyncio.sleep(24 * 3600)
            if _read_settings().get("auto_backup", True):
                _auto_backup_once()
        except Exception:
            pass


@app.post("/api/admin/import/schedule")
async def admin_import_schedule(body: CsvImportBody, request: Request):
    require_admin(request)
    text = (body.csv or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой CSV")
    data = FILE_SCHEDULE if isinstance(FILE_SCHEDULE, dict) else {}
    result = data.copy()
    daymap = {"пн": "mon", "вт": "tue", "ср": "wed", "чт": "thu", "пт": "fri", "сб": "sat",
              "понедельник": "mon", "вторник": "tue", "среда": "wed", "четверг": "thu",
              "пятница": "fri", "суббота": "sat"}
    lines = text.splitlines()
    header = [h.strip().lower() for h in lines[0].split(";")]
    schools = {}
    for raw in lines[1:]:
        row = [c.strip() for c in raw.split(";")]
        if len(row) < 4 or not row[0]:
            continue
        vals = dict(zip(header, row)) if len(header) >= len(row) else {}
        def g(name, default=""):
            idx = header.index(name) if name in header else -1
            return row[idx] if 0 <= idx < len(row) else default
        day = daymap.get(g("day").lower(), "")
        group = g("group") or "default"
        if not day:
            continue
        subj = {
            "subject": g("subject"),
            "teacher": g("teacher", "—"),
            "room": g("room", "—"),
            "type": g("type", "lection") or "lection",
        }
        pair = g("pair", "")
        if pair:
            subj["pair"] = int(pair) if pair.isdigit() else pair
        t_start = g("time_start", "")
        t_end = g("time_end", "")
        if t_start:
            subj["time_start"] = t_start
        if t_end:
            subj["time_end"] = t_end
        grp = schools.setdefault(group, {})
        grp.setdefault(day, []).append(subj)
    if not schools:
        raise HTTPException(status_code=400, detail="Нет валидных строк")
    for group, days in schools.items():
        merged = result.setdefault(group, {}) if isinstance(result, dict) else {}
        merged.update(days)
        result[group] = merged
    _save_json(SCHEDULE_FILE, result)
    reload_data_files()
    _log_admin(f"Импортировано расписание из CSV: групп {len(schools)}")
    return {"ok": True, "groups": list(schools.keys())}


@app.post("/api/admin/restore")
async def admin_restore(body: RestoreBody, request: Request):
    require_admin(request)
    restored = []
    for name, content in (body.files or {}).items():
        if name not in VALID_FILE_NAMES:
            continue
        if not isinstance(content, (dict, list)):
            continue
        _save_json(DATA_FILES_MAP[name], content)
        restored.append(name)
    if restored:
        reload_data_files()
        _log_admin(f"Восстановлено из резервной копии: {', '.join(restored)}")
    return {"ok": True, "restored": restored}


@app.post("/api/admin/restore-zip")
async def admin_restore_zip_upload(request: Request):
    require_admin(request)
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    restored = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename).rsplit(".", 1)[0]
                if base not in DATA_FILES_MAP:
                    continue
                try:
                    data = json.loads(zf.read(info).decode("utf-8"))
                except Exception:
                    continue
                if not isinstance(data, (dict, list)):
                    continue
                _save_json(DATA_FILES_MAP[base], data)
                restored.append(base)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Некорректный архив: {e}")
    if restored:
        reload_data_files()
        _log_admin(f"Полное восстановление из бэкапа: {', '.join(restored)}")
    return {"ok": True, "restored": restored}


@app.get("/api/admin/versions/{name}")
async def admin_versions(name: str, request: Request):
    require_admin(request)
    if name not in VALID_FILE_NAMES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return _file_versions(name)


@app.post("/api/admin/versions/{name}/restore")
async def admin_restore_version(name: str, body: RestoreVersionBody, request: Request):
    require_admin(request)
    if name not in VALID_FILE_NAMES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    content = _restore_version(name, body.version)
    if content is None:
        raise HTTPException(status_code=404, detail="Версия не найдена")
    return {"ok": True, "name": name, "version": body.version, "content": content}


# --- Справочники, дни рождения, опросы, объявления куратора, расписание преподавателя ---

@app.get("/api/references")
async def get_references():
    return FILE_REFERENCES or DEFAULT_REFERENCES


@app.get("/api/birthdays")
async def get_birthdays(request: Request):
    items = FILE_BIRTHDAYS or DEFAULT_BIRTHDAYS
    identity = _identity(request)
    if identity and identity["role"] == "student":
        group = (identity["person"] or {}).get("group", "")
        items = [b for b in items if not b.get("group") or b.get("group") == group]
    return {"birthdays": sorted(items, key=lambda b: str(b.get("date", "")))}


@app.get("/api/polls")
async def get_polls(request: Request):
    polls = FILE_POLLS or DEFAULT_POLLS
    out = []
    for p in polls:
        results = p.get("results", {}) if isinstance(p.get("results", {}), dict) else {}
        counts = []
        for i, opt in enumerate(p.get("options", [])):
            voters = results.get(str(i), []) if isinstance(results.get(str(i), ""), list) else []
            counts.append(len(voters))
        out.append({
            "id": p.get("id", ""),
            "question": p.get("question", ""),
            "options": p.get("options", []),
            "votes": counts,
            "total": sum(counts),
            "closed": bool(p.get("closed")),
            "my": _my_poll_choice(request, p),
        })
    return {"polls": out}


def _my_poll_choice(request, poll):
    identity = _identity(request)
    if not identity:
        return None
    fio = identity["person"].get("fio", "") if identity["person"] else ""
    results = poll.get("results", {}) if isinstance(poll.get("results", {}), dict) else {}
    for idx, voters in results.items():
        if isinstance(voters, list) and fio in voters:
            return int(idx)
    return None


@app.post("/api/polls/{poll_id}/vote")
async def vote_poll(poll_id: str, body: VoteBody, request: Request):
    identity = _identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Требуется вход")
    fio = identity["person"].get("fio", "") if identity["person"] else ""
    if not fio:
        raise HTTPException(status_code=403, detail="Не удалось определить пользователя")
    polls = list(FILE_POLLS or [])
    for p in polls:
        if p.get("id") != poll_id:
            continue
        if p.get("closed"):
            raise HTTPException(status_code=400, detail="Опрос завершён")
        options = p.get("options", [])
        if not 0 <= body.option < len(options):
            raise HTTPException(status_code=400, detail="Недопустимый вариант")
        results = dict(p.get("results", {}) or {})
        for k in results:
            if isinstance(results[k], list):
                results[k] = [v for v in results[k] if v != fio]
        voters = results.get(str(body.option), [])
        if not isinstance(voters, list):
            voters = []
        voters.append(fio)
        results[str(body.option)] = voters
        p["results"] = results
        _save_json(POLLS_FILE, polls)
        reload_data_files()
        return {"ok": True, "id": poll_id, "option": body.option}
    raise HTTPException(status_code=404, detail="Опрос не найден")


@app.post("/api/admin/polls")
async def admin_create_poll(body: PollCreateBody, request: Request):
    require_admin(request)
    if not body.question.strip() or not body.options or len(body.options) < 2:
        raise HTTPException(status_code=400, detail="Нужен вопрос и минимум 2 варианта")
    polls = list(FILE_POLLS or [])
    polls.append({
        "id": f"p{int(datetime.utcnow().timestamp() * 1000)}",
        "question": body.question.strip(),
        "options": [str(o).strip() for o in body.options if str(o).strip()],
        "results": {},
        "closed": bool(body.closed),
    })
    _save_json(POLLS_FILE, polls)
    reload_data_files()
    _log_admin(f"Создан опрос: {body.question[:60]}")
    return {"ok": True, "polls": FILE_POLLS}


@app.post("/api/curator/announce")
async def curator_announce(body: CuratorAnnounceBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "curator":
        raise HTTPException(status_code=403, detail="Доступ только куратору")
    group = identity["person"].get("group", "")
    if not body.title.strip() and not body.body.strip():
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    data = list(FILE_NEWS or [])
    data.insert(0, {
        "id": f"n{int(datetime.utcnow().timestamp() * 1000)}",
        "title": body.title.strip() or "Сообщение куратора",
        "category": f"Куратор группы {group}",
        "date": datetime.now().strftime("%d.%m.%Y"),
        "body": body.body.strip(),
        "groups": [group],
    })
    _save_json(NEWS_FILE, data)
    reload_data_files()
    try:
        push_service.send_push({
            "title": body.title.strip() or "Сообщение куратора",
            "body": body.body.strip()[:80],
            "url": "/",
        })
    except Exception:
        pass
    _log_admin(f"Куратор {group}: объявление «{data[0]['title'][:50]}»")
    return {"ok": True, "news": FILE_NEWS}


@app.get("/api/teacher/schedule")
async def teacher_schedule(request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Доступ только преподавателю")
    group = identity["person"].get("group", "")
    fio = identity["person"].get("fio", "")
    last = (fio.split()[0] if fio else "").lower()
    days = []
    for day_key in ("mon", "tue", "wed", "thu", "fri", "sat"):
        lessons = schedule_subjects(day_key, group) or DAY_SUBJECTS_DEFAULT.get(day_key, [])
        mine = [l for l in (lessons or []) if not last or str(l.get("teacher", "")).lower().startswith(last)]
        if mine:
            days.append({"day": day_key, "lessons": mine})
    return {"group": group, "fio": fio, "days": days}


# --- Логирование ошибок фронтенда ---
FRONTEND_ERRORS: Dict[str, list] = {}


@app.post("/api/log-error")
async def log_frontend_error(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    ip = request.client.host if request.client else ""
    stamp = time.time()
    window = [t for t in FRONTEND_ERRORS.get(ip, []) if stamp - t < 60]
    if len(window) >= 20:
        raise HTTPException(status_code=429, detail="Слишком много ошибок")
    window.append(stamp)
    FRONTEND_ERRORS[ip] = window
    msg = f"[frontend] {str(body.get('message', ''))[:200]}"
    if body.get("stack"):
        msg += " | " + str(body["stack"])[:300]
    _log_admin(msg)
    return {"ok": True}


# --- Облачный профиль, дежурства, чат, ответы куратора, важные новости, импорт/экспорт, статистика ---

@app.get("/api/me/prefs")
async def get_my_prefs(request: Request):
    identity = _identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Требуется вход")
    fio = identity["person"].get("fio", "") if identity["person"] else ""
    return {"prefs": (FILE_PROFILE_SYNC or {}).get(fio, {})}


@app.put("/api/me/prefs")
async def put_my_prefs(body: PrefsBody, request: Request):
    identity = _identity(request)
    if not identity or not identity["person"]:
        raise HTTPException(status_code=401, detail="Требуется вход")
    fio = identity["person"].get("fio", "")
    data = dict(FILE_PROFILE_SYNC or {})
    data[fio] = dict(body.prefs or {})
    _save_json(PROFILE_SYNC_FILE, data)
    reload_data_files()
    return {"ok": True, "prefs": data[fio]}


@app.get("/api/duties")
async def get_duties(request: Request):
    duties = FILE_DUTIES or DEFAULT_DUTIES
    items = (duties.get("list", []) if isinstance(duties, dict) else [])
    weekday = _rus_weekday_lower(datetime.now().weekday())
    today = next((d for d in items if d.get("day", "").lower().startswith(weekday)), None)
    identity = _identity(request)
    group = (identity["person"] or {}).get("group", "") if identity and identity["person"] else ""
    return {"group": group, "today": today, "schedule": items}


def _rus_weekday_lower(wd: int) -> str:
    names = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"]
    return names[wd] if wd < len(names) else ""


@app.get("/api/chat")
async def get_chat(request: Request):
    identity = _identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Требуется вход")
    data = FILE_CHAT or DEFAULT_CHAT
    msgs = (data.get("messages", []) if isinstance(data, dict) else [])[-100:]
    return {"messages": msgs}


@app.post("/api/chat")
async def post_chat(body: ChatPostBody, request: Request):
    identity = _identity(request)
    if not identity or not identity["person"]:
        raise HTTPException(status_code=401, detail="Требуется вход")
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    fio = identity["person"].get("fio", "Студент")
    data = dict(FILE_CHAT or DEFAULT_CHAT)
    messages = list(data.get("messages", []))
    messages.append({
        "id": f"m{int(time.time() * 1000)}",
        "fio": fio,
        "text": text[:500],
        "ts": datetime.now().strftime("%d.%m %H:%M"),
    })
    data["messages"] = messages[-500:]
    _save_json(CHAT_FILE, data)
    reload_data_files()
    return {"ok": True, "messages": data["messages"]}


@app.post("/api/curator/tickets/{ticket_id}")
async def curator_reply_ticket(ticket_id: str, body: TicketReplyBody, request: Request):
    identity = _identity(request)
    if not identity or identity["role"] != "curator":
        raise HTTPException(status_code=403, detail="Доступ только куратору")
    group = identity["person"].get("group", "")
    data = dict(FILE_TICKETS or DEFAULT_TICKETS)
    tickets = list(data.get("tickets", []))
    for t in tickets:
        if t.get("id") == ticket_id and t.get("group") == group:
            t["status"] = body.status
            t["answer"] = body.answer.strip()
            t["answer_ts"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            break
    else:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    data["tickets"] = tickets
    _save_json(TICKETS_FILE, data)
    reload_data_files()
    _log_admin(f"Куратор {group} ответил по тикету {ticket_id}")
    if body.answer.strip():
        try:
            push_service.send_push({
                "title": "Ответ куратора",
                "body": f"Куратор ответил на ваше обращение: {body.answer.strip()[:80]}",
                "url": "/",
            })
        except Exception:
            pass
    return {"ok": True, "tickets": tickets}


@app.post("/api/news/{news_id}/read")
async def mark_news_read(news_id: str, request: Request):
    identity = _identity(request)
    if not identity or not identity["person"]:
        raise HTTPException(status_code=401, detail="Требуется вход")
    fio = identity["person"].get("fio", "")
    meta = dict(FILE_NEWS_META or DEFAULT_NEWS_META)
    reads = dict(meta.get("reads", {}) or {})
    seen = reads.get(news_id, []) if isinstance(reads.get(news_id), list) else []
    if fio and fio not in seen:
        seen.append(fio)
        reads[news_id] = seen[-1000:]
    meta["reads"] = reads
    _save_json(NEWS_META_FILE, meta)
    reload_data_files()
    return {"ok": True, "count": len(seen)}


@app.post("/api/admin/students/import")
async def admin_import_students(body: ImportStudentsBody, request: Request):
    require_admin(request)
    created, skipped = [], 0
    for line in (body.csv or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("login"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        login, password, fio = parts[0], parts[1], parts[2]
        group = parts[3] if len(parts) > 3 else ""
        course = parts[4] if len(parts) > 4 else "1"
        if not login or not password or not fio:
            continue
        if login.lower() in {s.get("login", "").lower() for s in _all_students()}:
            skipped += 1
            continue
        STUDENTS.append({"login": login, "password": password, "fio": fio, "group": group, "course": course})
        created.append(login)
    if created:
        _save_json(STUDENTS_FILE, STUDENTS)
        reload_accounts()
        _log_admin(f"Импорт студентов: +{len(created)}, пропущено {skipped}")
    return {"ok": True, "created": len(created), "skipped": skipped, "logins": created}


def _all_students() -> list:
    values = list(STUDENTS)
    if isinstance(STUDENTS, dict):
        values = list(STUDENTS.values())
    if isinstance(values, list) and values and isinstance(values[0], dict):
        return values
    return []


@app.get("/api/admin/export/{name}")
async def admin_export(name: str, request: Request):
    require_admin(request)
    if name not in VALID_FILE_NAMES:
        raise HTTPException(status_code=404, detail="Файл не найден")
    m = DATA_FILES_MAP[name]
    data = _read_json(m, None)
    if isinstance(data, dict):
        rows = []
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows.extend(v)
            else:
                rows.append({"key": k, "value": v if isinstance(v, (list, dict)) else str(v)})
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    cols = []
    for r in rows:
        if isinstance(r, dict):
            for k in r:
                if k not in cols:
                    cols.append(k)
    def _cell(v):
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            return '"' + json.dumps(v, ensure_ascii=False).replace('"', '""') + '"'
        s = str(v)
        return '"' + s.replace('"', '""') + '"' if any(c in s for c in ',;"\n') else s
    lines = [",".join(cols)]
    for r in rows:
        if isinstance(r, dict):
            lines.append(",".join(_cell(r.get(c, "")) for c in cols))
    csv_text = "\n".join(lines)
    _log_admin(f"Экспорт {name} в CSV")
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@app.get("/api/me/logins")
async def my_logins(request: Request):
    identity = _identity(request)
    if not identity or not identity["person"]:
        raise HTTPException(status_code=401, detail="Требуется вход")
    fio = identity["person"].get("fio", "")
    return {"logins": [l for l in _read_logins() if l.get("fio") == fio][-10:]}


@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    require_admin(request)
    logins = _read_logins()
    today_key = datetime.now().strftime("%Y-%m-%d")
    today = sum(1 for l in logins if str(l.get("ts", "")).startswith(today_key))
    week = sum(1 for l in logins if datetime.strptime(str(l.get("ts", ""))[:10], "%Y-%m-%d") >= (datetime.now() - timedelta(days=7)))
    errors = 0
    if ADMIN_LOG_FILE.exists():
        try:
            with open(ADMIN_LOG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('{"') and "[frontend] " in line:
                        errors += 1
        except Exception:
            pass
    polls_votes = sum(len((p.get("results", {}) or {}).get(str(i), [])) for p in (FILE_POLLS or []) for i in range(len(p.get("options", []))))
    open_tickets = sum(1 for t in (FILE_TICKETS or {}).get("tickets", []) if t.get("status") not in ("done", "closed"))
    students = len(_all_students())
    return {"logins_today": today, "logins_week": week, "frontend_errors": errors,
            "poll_votes": polls_votes, "open_tickets": open_tickets, "students": students}


def _read_settings() -> dict:
    defaults = {"auto_backup": True, "backup_days": 7}
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        pass
    return defaults


class BackupSettingsBody(BaseModel):
    auto_backup: bool = True
    backup_days: int = 7


@app.get("/api/admin/backup-settings")
async def admin_backup_settings(request: Request):
    require_admin(request)
    return _read_settings()


@app.post("/api/admin/backup-settings")
async def admin_set_backup_settings(body: BackupSettingsBody, request: Request):
    require_admin(request)
    days = max(1, min(60, int(body.backup_days)))
    data = {"auto_backup": bool(body.auto_backup), "backup_days": days}
    _save_json(SETTINGS_FILE, data)
    _log_admin(f"Настройки бэкапа: {data}")
    return data


@app.get("/api/admin/top-groups")
async def admin_top_groups(request: Request):
    require_admin(request)
    groups = {}
    if isinstance(FILE_GRADES, dict):
        for group, gd in FILE_GRADES.items():
            students = (gd or {}).get("students", {}) if isinstance(gd, dict) else {}
            avgs = []
            for login, marks in students.items():
                vals = [m.get("value") for m in marks if isinstance(m, dict) and m.get("value")]
                if vals:
                    avgs.append(round(sum(vals) / len(vals), 2))
            groups[group] = {"avg": round(sum(avgs) / len(avgs), 2) if avgs else 0.0,
                             "count": len(avgs)}
    ranked = sorted(groups.items(), key=lambda kv: kv[1]["avg"], reverse=True)
    return {"groups": [{"group": g, "avg": v["avg"], "count": v["count"], "place": i + 1}
                       for i, (g, v) in enumerate(ranked)]}


@app.get("/api/admin/attendance-stats")
async def admin_attendance_stats(request: Request):
    require_admin(request)
    group_names = set()
    if isinstance(FILE_ATTENDANCE, dict):
        group_names.update(str(g) for g in FILE_ATTENDANCE.keys())
    for s in _all_students():
        if s.get("group"):
            group_names.add(str(s["group"]))
    out = []
    for group in sorted(group_names):
        percent, days = _compute_attendance(group)
        absent = late = total = 0
        for day in days:
            for lesson in day.get("lessons", []):
                total += 1
                if lesson.get("status") == "absent":
                    absent += 1
                elif lesson.get("status") == "late":
                    late += 1
        out.append({"group": group, "percent": percent, "absent": absent, "late": late,
                    "total": total,
                    "days": [{"date": d.get("date"), "absent": sum(1 for ll in d.get("lessons", []) if ll.get("status") == "absent"),
                              "total": len(d.get("lessons", []))} for d in days[-10:]]})
    out.sort(key=lambda g: g["absent"], reverse=True)
    return {"groups": out}


@app.get("/api/admin/frontend-errors")
async def admin_frontend_errors(request: Request):
    require_admin(request)
    lines = []
    if ADMIN_LOG_FILE.exists():
        try:
            with open(ADMIN_LOG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "[frontend] " in line:
                        try:
                            item = json.loads(line)
                            lines.append({"ts": item.get("ts", ""),
                                          "msg": item.get("action", "").replace("[frontend] ", "", 1)})
                        except Exception:
                            pass
        except Exception:
            pass
    return {"errors": lines[-50:]}


@app.post("/api/admin/frontend-errors/clear")
async def admin_frontend_errors_clear(request: Request):
    require_admin(request)
    kept = []
    if ADMIN_LOG_FILE.exists():
        try:
            for line in ADMIN_LOG_FILE.read_text(encoding="utf-8").splitlines():
                if line.strip() and "[frontend] " not in line:
                    kept.append(line)
            ADMIN_LOG_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        except Exception:
            pass
    _log_admin("Очистка журнала ошибок фронтенда")
    return {"ok": True}


# --- Вход: загрузка файлов ----------------------------------------------
ALLOWED_UPLOAD_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf",
                      ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv", ".zip"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


@app.post("/api/admin/upload")
async def admin_upload(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    original = ((file.filename or "file").replace("\\", "/").split("/")[-1])
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")
    stem = re.sub(r"[^A-Za-zА-Яа-яЁё0-9._\- ]", "_", Path(original).stem).strip()[:60]
    name = f"{int(time.time() * 1000)}-{stem}{ext}"
    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 20 МБ)")
    (UPLOADS_DIR / name).write_bytes(data)
    _log_admin(f"Загружен файл: {name}")
    return {"ok": True, "url": f"/uploads/{name}", "name": name}


@app.get("/api/admin/uploads")
async def admin_uploads_list(request: Request):
    require_admin(request)
    out = []
    for p in sorted(UPLOADS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file():
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size, "url": "/uploads/" + p.name,
                        "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M")})
    return {"files": out}


@app.delete("/api/admin/uploads/{name}")
async def admin_upload_delete(name: str, request: Request):
    require_admin(request)
    target = (UPLOADS_DIR / name).resolve()
    base = UPLOADS_DIR.resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    target.unlink(missing_ok=True)
    _log_admin(f"Удалён файл: {name}")
    return {"ok": True}


app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# --- Вход: ответы на обращения ------------------------------------------
@app.post("/api/admin/tickets/{ticket_id}/answer")
async def admin_ticket_answer(ticket_id: str, body: TicketReplyBody, request: Request):
    require_admin(request)
    data = dict(FILE_TICKETS or DEFAULT_TICKETS)
    tickets = list(data.get("tickets", []))
    login = ""
    for t in tickets:
        if t.get("id") == ticket_id:
            login = t.get("login", "")
            t["status"] = body.status or "in-progress"
            if body.answer.strip():
                t["answer"] = body.answer.strip()
                t["answer_ts"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            break
    else:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    data["tickets"] = tickets
    _save_json(TICKETS_FILE, data)
    reload_data_files()
    _log_admin(f"Ответ админа по обращению {ticket_id}")
    if body.answer.strip():
        try:
            push_service.send_push({
                "title": "Ответ на обращение",
                "body": f"Администратор ответил: {body.answer.strip()[:80]}",
                "url": "/",
            }, user=login)
        except Exception:
            pass
    return {"ok": True, "tickets": tickets}


# --- Вход: модерация чата ------------------------------------------------
@app.get("/api/admin/chat")
async def admin_chat(request: Request):
    require_admin(request)
    data = dict(FILE_CHAT or DEFAULT_CHAT)
    msgs = list(data.get("messages", []))
    changed = False
    for i, m in enumerate(msgs):
        if not m.get("id"):
            m["id"] = f"m{int(time.time() * 1000)}{i}"
            changed = True
    if changed:
        data["messages"] = msgs
        _save_json(CHAT_FILE, data)
        reload_data_files()
    return {"messages": list(reversed(msgs[-200:]))}


@app.delete("/api/admin/chat/{msg_id}")
async def admin_chat_delete(msg_id: str, request: Request):
    require_admin(request)
    data = dict(FILE_CHAT or DEFAULT_CHAT)
    msgs = list(data.get("messages", []))
    out = [m for m in msgs if m.get("id") != msg_id]
    if len(out) == len(msgs):
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    data["messages"] = out
    _save_json(CHAT_FILE, data)
    reload_data_files()
    _log_admin(f"Удалено сообщение чата {msg_id}")
    return {"ok": True, "messages": list(reversed(out[-200:]))}


# --- Вход: Push-дашборд --------------------------------------------------
@app.get("/api/admin/push")
async def admin_push_dashboard(request: Request):
    require_admin(request)
    subs = push_service.list_subscriptions()
    by_login = {}
    for s in subs:
        login = s.get("login") or ""
        rec = by_login.setdefault(login, {"login": login, "endpoints": 0, "created": ""})
        rec["endpoints"] += 1
        if s.get("created"):
            rec["created"] = s["created"]
    users = sorted(by_login.values(), key=lambda x: -x["endpoints"])
    return {"total": len(subs), "users": users}


@app.delete("/api/admin/push/{login}")
async def admin_push_remove(login: str, request: Request):
    require_admin(request)
    removed = push_service.remove_user_subscriptions(login)
    _log_admin(f"Отписка от push: {login} ({removed})")
    return {"ok": True, "removed": removed, "total": len(push_service.list_subscriptions())}


# --- Вход: отложенные публикации -----------------------------------------
def _read_scheduled() -> list:
    return _read_json(SCHEDULED_POSTS_FILE, [])


def _save_scheduled(items: list):
    _save_json(SCHEDULED_POSTS_FILE, items)


class ScheduledPostBody(BaseModel):
    title: str
    body: str = ""
    category: str = ""
    groups: list[str] = []
    publish_at: str
    announce: bool = False


@app.get("/api/admin/scheduled")
async def admin_scheduled_list(request: Request):
    require_admin(request)
    items = _read_scheduled()
    return {"posts": sorted(items, key=lambda x: str(x.get("publish_at", "")))}


@app.post("/api/admin/scheduled")
async def admin_scheduled_add(body: ScheduledPostBody, request: Request):
    require_admin(request)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите заголовок")
    when = body.publish_at.strip().replace("T", " ")
    if not when:
        raise HTTPException(status_code=400, detail="Укажите время публикации")
    items = _read_scheduled()
    items.append({
        "id": f"s{int(time.time() * 1000)}",
        "title": title,
        "body": body.body.strip(),
        "category": body.category.strip(),
        "groups": body.groups or [],
        "publish_at": when,
        "announce": bool(body.announce),
    })
    _save_scheduled(items)
    _log_admin(f"Запланирована публикация: {title[:50]} на {when}")
    return {"ok": True, "posts": items}


@app.post("/api/admin/scheduled/{sid}/cancel")
async def admin_scheduled_cancel(sid: str, request: Request):
    require_admin(request)
    items = _read_scheduled()
    out = [i for i in items if i.get("id") != sid]
    _save_scheduled(out)
    _log_admin(f"Отменена публикация {sid}")
    return {"ok": True, "posts": out}


def _publish_due_posts():
    items = _read_scheduled()
    if not items:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pending = [i for i in items if str(i.get("publish_at", "")) <= now]
    if not pending:
        return
    rest = [i for i in items if i not in pending]
    news = list(FILE_NEWS or [])
    for p in pending:
        news.insert(0, {
            "id": f"n{int(time.time() * 1000)}",
            "title": p.get("title", ""),
            "category": p.get("category", ""),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "body": p.get("body", ""),
            "groups": p.get("groups", []),
        })
        if p.get("announce"):
            try:
                push_service.send_push({
                    "title": p.get("title", ""),
                    "body": (p.get("body", "") or "")[:80],
                    "url": "/",
                })
            except Exception:
                pass
        _log_admin(f"Опубликована запланированная новость: {p.get('title', '')[:50]}")
    _save_json(NEWS_FILE, news)
    _save_scheduled(rest)
    reload_data_files()


async def _auto_publish_loop():
    await asyncio.sleep(15)
    while True:
        await asyncio.sleep(30)
        try:
            _publish_due_posts()
        except Exception:
            pass


# --- Вход: смена пароля администратора ----------------------------------
class ChangeAdminPasswordBody(BaseModel):
    current: str
    new_password: str


@app.post("/api/admin/change-password")
async def admin_change_password(body: ChangeAdminPasswordBody, request: Request):
    require_admin(request)
    if not _check_admin_token(body.current or ""):
        raise HTTPException(status_code=403, detail="Текущий пароль неверен")
    new = (body.new_password or "").strip()
    if len(new) < 4:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 4 символов")
    salt = secrets.token_hex(8)
    with open(ADMIN_PASS_FILE, "w", encoding="utf-8") as f:
        json.dump({"salt": salt, "hash": _hash_admin_key(new, salt)}, f, ensure_ascii=False)
    _log_admin("Смена пароля администратора")
    return {"ok": True, "token": new}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


app = FastAPI(title="AI Scoring System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class User:
    username: str
    password: str
    role: str


@dataclass
class Question:
    id: str
    title: str
    description: str
    mode: str
    created_by: str


@dataclass
class Submission:
    id: str
    question_id: str
    student: str
    mode: str
    code: str
    score: Optional[float]
    feedback: str
    created_at: str


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = Field(pattern="^(teacher|student)$")


class CreateQuestionRequest(BaseModel):
    title: str
    description: str
    mode: str = Field(pattern="^(exam|practice)$")


class ApiKeyRequest(BaseModel):
    api_key: str


class SubmitRequest(BaseModel):
    question_id: str
    mode: str = Field(pattern="^(exam|practice)$")
    code: str


USERS: Dict[str, User] = {
    "teacher1": User("teacher1", "teacher123", "teacher"),
    "student1": User("student1", "student123", "student"),
    "student2": User("student2", "student123", "student"),
}

TOKENS: Dict[str, str] = {}
QUESTIONS: Dict[str, Question] = {}
SUBMISSIONS: List[Submission] = []
APP_CONFIG = {"openai_api_key": os.getenv("OPENAI_API_KEY", "")}


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _heuristic_score(code: str) -> tuple[float, str]:
    length_score = min(len(code) / 20, 40)
    has_func = 30 if "def " in code or "function " in code else 10
    has_branch = 20 if "if " in code or "switch" in code else 10
    has_loop = 10 if "for " in code or "while " in code else 5
    score = round(min(length_score + has_func + has_branch + has_loop, 100), 2)
    return score, "已使用本地備援規則評分（未設定或未成功呼叫 GPT）。"


def _gpt_score(code: str, api_key: str) -> tuple[float, str]:
    payload = {
        "model": "gpt-4.1-mini",
        "input": [
            {
                "role": "system",
                "content": "你是程式考試評分助教。請只回傳 JSON: {\"score\": number(0-100), \"feedback\": string}。",
            },
            {
                "role": "user",
                "content": f"請評分這段程式碼，重點看正確性、可讀性、邏輯完整度：\n```\n{code}\n```",
            },
        ],
    }
    auth_header = " ".join(["Bearer", api_key])
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": auth_header, "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("output_text", "").strip()
    parsed = json.loads(text)
    score = float(parsed.get("score", 0))
    feedback = str(parsed.get("feedback", "GPT 未提供回饋"))
    return max(0, min(score, 100)), feedback


def score_exam(code: str) -> tuple[float, str]:
    api_key = APP_CONFIG.get("openai_api_key", "")
    if not api_key:
        return _heuristic_score(code)

    try:
        return _gpt_score(code, api_key)
    except Exception as exc:  # noqa: BLE001
        score, fallback = _heuristic_score(code)
        return score, f"{fallback} GPT 錯誤：{exc}"


def get_current_user(x_auth_token: str = Header(default="", alias="X-Auth-Token")) -> User:
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing token")

    token = x_auth_token
    username = TOKENS.get(token)
    if not username or username not in USERS:
        raise HTTPException(status_code=401, detail="Invalid token")
    return USERS[username]


@app.post("/api/login")
def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user.password != req.password or user.role != req.role:
        raise HTTPException(status_code=401, detail="帳號、密碼或角色錯誤")
    token = str(uuid.uuid4())
    TOKENS[token] = user.username
    return {"token": token, "username": user.username, "role": user.role}


@app.post("/api/teacher/questions")
def create_question(req: CreateQuestionRequest, user: User = Depends(get_current_user)):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teacher can create questions")

    q = Question(
        id=str(uuid.uuid4()),
        title=req.title,
        description=req.description,
        mode=req.mode,
        created_by=user.username,
    )
    QUESTIONS[q.id] = q
    return asdict(q)


@app.post("/api/teacher/config")
def set_api_key(req: ApiKeyRequest, user: User = Depends(get_current_user)):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teacher can set API key")

    APP_CONFIG["openai_api_key"] = req.api_key.strip()
    return {"message": "API Key updated"}


@app.get("/api/questions")
def list_questions(mode: Optional[str] = None, user: User = Depends(get_current_user)):
    items = [asdict(q) for q in QUESTIONS.values() if mode is None or q.mode == mode]
    return {"questions": items}


@app.post("/api/student/submissions")
def submit(req: SubmitRequest, user: User = Depends(get_current_user)):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only student can submit")

    q = QUESTIONS.get(req.question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    if q.mode != req.mode:
        raise HTTPException(status_code=400, detail="Question mode mismatch")

    score = None
    feedback = "練習模式已提交，請查看進度。"
    if req.mode == "exam":
        score, feedback = score_exam(req.code)

    record = Submission(
        id=str(uuid.uuid4()),
        question_id=q.id,
        student=user.username,
        mode=req.mode,
        code=req.code,
        score=score,
        feedback=feedback,
        created_at=now_iso(),
    )
    SUBMISSIONS.append(record)
    return asdict(record)


@app.get("/api/student/me")
def student_me(user: User = Depends(get_current_user)):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only student can access this endpoint")

    records = [asdict(s) for s in SUBMISSIONS if s.student == user.username]
    return {"student": user.username, "submissions": records}


@app.get("/api/teacher/dashboard")
def teacher_dashboard(user: User = Depends(get_current_user)):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teacher can access dashboard")

    by_student: Dict[str, Dict[str, int]] = {}
    for s in SUBMISSIONS:
        current = by_student.setdefault(s.student, {"exam_count": 0, "practice_count": 0})
        if s.mode == "exam":
            current["exam_count"] += 1
        else:
            current["practice_count"] += 1

    avg_exam = [s.score for s in SUBMISSIONS if s.mode == "exam" and s.score is not None]
    exam_average = round(sum(avg_exam) / len(avg_exam), 2) if avg_exam else None

    return {
        "students": by_student,
        "exam_average": exam_average,
        "submissions": [asdict(s) for s in SUBMISSIONS],
    }


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

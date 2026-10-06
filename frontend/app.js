const state = { token: "", role: "", questions: [] };

async function api(path, method = "GET", body) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers["X-Auth-Token"] = state.token;
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function byId(id) {
  return document.getElementById(id);
}

function showRoleSections() {
  byId("teacher-section").classList.toggle("hidden", state.role !== "teacher");
  byId("student-section").classList.toggle("hidden", state.role !== "student");
}

byId("login-btn").onclick = async () => {
  try {
    const data = await api("/api/login", "POST", {
      username: byId("username").value,
      password: byId("password").value,
      role: byId("role").value,
    });
    state.token = data.token;
    state.role = data.role;
    byId("login-msg").innerText = `登入成功：${data.username}`;
    showRoleSections();
  } catch (err) {
    byId("login-msg").innerText = err.message;
  }
};

byId("save-key-btn").onclick = async () => {
  try {
    await api("/api/teacher/config", "POST", { api_key: byId("api-key").value });
    alert("API Key 已儲存");
  } catch (err) {
    alert(err.message);
  }
};

byId("create-q-btn").onclick = async () => {
  try {
    await api("/api/teacher/questions", "POST", {
      title: byId("q-title").value,
      description: byId("q-desc").value,
      mode: byId("q-mode").value,
    });
    alert("題目新增成功");
  } catch (err) {
    alert(err.message);
  }
};

byId("refresh-dashboard-btn").onclick = async () => {
  try {
    const data = await api("/api/teacher/dashboard");
    byId("teacher-dashboard").innerText = JSON.stringify(data, null, 2);
  } catch (err) {
    alert(err.message);
  }
};

byId("load-questions-btn").onclick = async () => {
  try {
    const mode = byId("student-mode").value;
    const data = await api(`/api/questions?mode=${mode}`);
    state.questions = data.questions;
    const select = byId("question-select");
    select.innerHTML = "";
    state.questions.forEach((q) => {
      const option = document.createElement("option");
      option.value = q.id;
      option.textContent = `${q.title} (${q.mode})`;
      select.appendChild(option);
    });
  } catch (err) {
    alert(err.message);
  }
};

byId("submit-btn").onclick = async () => {
  try {
    const questionId = byId("question-select").value;
    const mode = byId("student-mode").value;
    if (!questionId) throw new Error("請先選擇題目");
    const data = await api("/api/student/submissions", "POST", {
      question_id: questionId,
      mode,
      code: byId("student-code").value,
    });
    alert(`提交成功。${data.score !== null ? `分數: ${data.score}` : "練習模式無分數"}`);
  } catch (err) {
    alert(err.message);
  }
};

byId("refresh-me-btn").onclick = async () => {
  try {
    const data = await api("/api/student/me");
    byId("student-records").innerText = JSON.stringify(data, null, 2);
  } catch (err) {
    alert(err.message);
  }
};

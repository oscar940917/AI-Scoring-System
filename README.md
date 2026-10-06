# AI-Scoring-System

一個最小可運作的前後端程式考試評分系統：

- 教師/學生登入介面
- 教師可建立考試或練習題目
- 學生可選擇考試或練習並提交程式碼
- 教師可查看學生考試/練習次數、提交紀錄與考試平均分
- 考試模式會優先使用教師設定的 GPT API Key 進行評分；失敗時自動改用本地備援評分

## 啟動方式

```bash
pip install -r requirements.txt
uvicorn backend_app:app --reload
```

開啟瀏覽器進入 `http://127.0.0.1:8000/`

## 測試帳號

- 教師：`teacher1 / teacher123`
- 學生：`student1 / student123`、`student2 / student123`
# Free Fire Like API — A2Z Deploy Guide

## 📁 ফাইল Structure
```
python-services/premiumlike/
├── app.py              ← Flask API (like, dashboard, stats, ping)
├── bot.py              ← Telegram bot (inline buttons)
├── scheduler.py        ← Auto token refresh (7h + 3:30 AM)
├── wsgi.py             ← Entry point (boot refresh + bot + scheduler)
├── config.json         ← 🔑 Bot token & Chat ID (এখানে দিন)
├── uidpass.json        ← UID + Password list
├── tokens.json         ← Generated tokens (auto-saved)
├── templates/
│   └── dashboard.html  ← Web dashboard
└── requirements.txt
```

---

## Step 1 — Telegram Bot তৈরি করুন

1. Telegram এ [@BotFather](https://t.me/BotFather) তে যান
2. `/newbot` পাঠান
3. Bot এর নাম দিন (যেকোনো)
4. Username দিন (শেষে `bot` থাকতে হবে, যেমন: `fflike_bot`)
5. BotFather একটা **Token** দেবে — এটা save করুন

**Chat ID বের করুন:**
- [@userinfobot](https://t.me/userinfobot) তে `/start` পাঠান
- আপনার Chat ID দেখাবে — এটাও save করুন

---

## Step 2 — config.json সেট করুন

`python-services/premiumlike/config.json` ফাইলটা খুলুন:

```json
{
  "bot_token": "1234567890:ABCDefghIJKlmno...",
  "chat_id": "123456789"
}
```

- `bot_token` → BotFather এর Token
- `chat_id` → আপনার Telegram Chat ID

---

## Step 3 — uidpass.json সেট করুন

`python-services/premiumlike/uidpass.json` ফাইলটা খুলুন:

```json
[
  {"uid": "YOURUID1", "password": "YOURPASS1"},
  {"uid": "YOURUID2", "password": "YOURPASS2"}
]
```

---

## Step 4 — GitHub এ Push করুন

Replit Shell খুলুন (Tools → Shell) এবং চালান:

```bash
git add .
git commit -m "FF Like API - config setup done"

# প্রথমবার remote add (username ও repo name বদলান)
git remote add github https://github.com/YOUR_USERNAME/YOUR_REPO.git

git push github main
```

> GitHub password এর বদলে **Personal Access Token** ব্যবহার করুন
> (GitHub → Settings → Developer settings → Personal access tokens → Generate new token)

---

## Step 5 — Render এ Deploy করুন

1. [render.com](https://render.com) এ login করুন
2. **New +** → **Web Service**
3. GitHub repo connect করুন
4. Settings:

| Setting | Value |
|---|---|
| **Root Directory** | `python-services/premiumlike` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --keep-alive 5` |

5. **Create Web Service** → ৩-৫ মিনিট অপেক্ষা করুন
6. ✅ Deploy হলে Telegram এ notification আসবে!

> **কোনো Environment Variable দেওয়ার দরকার নেই** — সব config.json এ আছে।

---

## Step 6 — UptimeRobot দিয়ে Awake রাখুন

Render free tier ১৫ মিনিট idle থাকলে sleep করে:

1. [uptimerobot.com](https://uptimerobot.com) → **Add New Monitor**
2. Settings:

| Setting | Value |
|---|---|
| Monitor Type | HTTP(s) |
| URL | `https://YOUR-APP.onrender.com/ping` |
| Interval | Every 5 minutes |

---

## Telegram Bot Buttons

`/start` পাঠালে এই inline buttons পাবেন:

| Button | কাজ |
|---|---|
| 🔄 Refresh Tokens | নতুন JWT token generate করুন |
| 📊 Stats | সব stats দেখুন |
| 🏓 Ping | API alive কিনা চেক |
| 📋 Token Count | কতটা token আছে |
| 📜 Like History | Like request এর stats |
| ⏰ Schedule Info | Auto refresh schedule |
| ❓ Help | সব button এর help |

Text commands ও কাজ করে: `/start` `/refresh` `/stats` `/ping` `/menu`

---

## API Endpoints

| Endpoint | কাজ |
|---|---|
| `/` | Web dashboard |
| `/ping` | Health check |
| `/like?uid=UID&server_name=IND` | Like পাঠান |
| `/api/stats` | JSON stats |
| `/api/refresh` | Manual token refresh (POST) |

---

## Auto Refresh Schedule

| সময় | কারণ |
|---|---|
| Server start এ | Boot refresh |
| প্রতি ৭ ঘন্টায় | Interval refresh |
| রাত ৩:৩০ AM UTC | Daily cron refresh |

প্রতিটা refresh এর পরে Telegram notification আসবে।

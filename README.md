# SmartClinic — Queue Management SaaS

Multi-tenant clinic queue management for Pakistan.
Patients interact via WhatsApp · Receptionists via web dashboard.

## Project Structure

```
/backend     FastAPI + PostgreSQL
/frontend    Next.js + Tailwind CSS
```

---

## Quick Start (Local)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, WA_ACCESS_TOKEN, WA_VERIFY_TOKEN

alembic upgrade head
uvicorn app.main:app --reload
```

API runs at http://localhost:8000
Swagger docs at http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Edit NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

Dashboard at http://localhost:3000

---

## Deploy to Railway

### Backend service
1. Create a new Railway project
2. Add service → connect GitHub repo → set root to `/backend`
3. Set environment variables (copy from `.env.example`)
4. Add a PostgreSQL plugin → copy DATABASE_URL into env vars
5. Deploy — Railway auto-runs `alembic upgrade head` then starts uvicorn

### Frontend service
1. Add another service in same project → root `/frontend`
2. Set `NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app`
3. Deploy

---

## WhatsApp Setup (Meta Cloud API)

1. Create a Meta Business Account and a WhatsApp Business App
2. Add a phone number per clinic under one WABA
3. Generate a permanent System User Access Token
4. Set webhook URL: `https://your-backend.up.railway.app/api/whatsapp/webhook`
5. Set verify token to match `WA_VERIFY_TOKEN` in your env
6. Subscribe to `messages` field
7. Add each clinic's `wa_phone_number_id` in the dashboard Settings

---

## Bot Flows

| Trigger | Action |
|---|---|
| Any message | Show main menu (3 buttons) |
| Book Appointment | Doctor selection → issue token |
| Check My Status | Lookup by phone → token status |
| Add Complaint | Free-text → saved to DB |

Conversation state expires after **10 minutes** of inactivity.

---

## Daily Reset

APScheduler runs at **00:00 PKT (UTC+5)** daily.
Resets `current_serving = 0` and `total_issued_today = 0` for all clinics.
Receptionists can also manually reset per doctor from the dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Database | PostgreSQL (Supabase/Railway) |
| Frontend | Next.js 14 + Tailwind CSS |
| WhatsApp | Meta Cloud API |
| Auth | JWT (python-jose) |
| Scheduler | APScheduler |
| QR Code | qrcode[pil] |
| Hosting | Railway |

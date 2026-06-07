# CareBank Deployment Guide: Vercel + Render

## Step 1: Backend Setup (Render)

### 1.1 Push Code to GitHub
```bash
# If not already a git repo
git init
git add .
git commit -m "Add deployment configs"
git push origin main
```

### 1.2 Create Render Account & Deploy
1. Go to https://render.com (sign up with GitHub)
2. Click **New +** → **Web Service**
3. Select your **carebank-codex** repository
4. Fill in:
   - **Name**: `carebank-backend`
   - **Runtime**: Docker
   - **Region**: Oregon (or closest to you)
   - **Plan**: Free (starts with 1 shared CPU, 512 MB RAM)

### 1.3 Set Environment Variables in Render
After creating the service, go to **Environment** and add:

| Key | Value |
|-----|-------|
| `APP_ENV` | `production` |
| `REQUIRE_STRICT_SECURITY` | `true` |
| `SUPABASE_URL` | https://your-project.supabase.co |
| `SUPABASE_ANON_KEY` | Get from Supabase → Settings → API Keys |
| `SUPABASE_SERVICE_ROLE_KEY` | Your Supabase service role key |
| `INTERNAL_METRICS_TOKEN` | Strong random token for `/metrics` and internal health |
| `FRONTEND_URL` | `https://yourproject.vercel.app` (update after Vercel deploy) |
| `OPENROUTER_API_KEY` | Get from https://openrouter.ai → API Keys |
| `AI_CATEGORIZATION_ENABLED` | `false` unless you explicitly enable it |
| `LLM_PROVIDER` | openrouter |
| `LLM_BASE_URL` | https://openrouter.ai/api/v1 |
| `LLM_MODEL` | openai/gpt-4o-mini |
| `RATE_LIMIT_ENABLED` | `true` |
| `ENABLE_AUDIT_PERSISTENCE` | `true` |
| `ENABLE_LOCAL_EVENT_FALLBACK` | `false` |
| `ENABLE_SAMPLE_DATA_FALLBACK` | false |
| `ENABLE_WEBSOCKET_DEV_FALLBACK` | `false` |

**Initial Deploy**: Render will auto-deploy from `render.yaml`
- Your backend URL: `https://carebank-backend.onrender.com`

### 1.4 Verify Backend Health
```bash
curl https://carebank-backend.onrender.com/health
# Should return: {"status":"ok"}
```

---

## Step 2: Frontend Setup (Vercel)

### 2.1 Deploy to Vercel
1. Go to https://vercel.com (sign up with GitHub)
2. Click **Add New...** → **Project**
3. Select your **carebank-codex** repository
4. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `carebank-frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### 2.2 Set Environment Variables in Vercel
In Vercel dashboard → **Settings** → **Environment Variables**, add:

| Key | Value | Environment |
|-----|-------|-------------|
| `VITE_API_URL` | `https://carebank-backend.onrender.com` | Production |
| `VITE_SUPABASE_URL` | https://your-project.supabase.co | Production |
| `VITE_SUPABASE_ANON_KEY` | Your Supabase anon key | Production |

### 2.3 Update Backend FRONTEND_URL
After Vercel deploy, go back to Render:
1. Go to **carebank-backend** service
2. Go to **Environment**
3. Update `FRONTEND_URL` to your Vercel URL (e.g., `https://carebank-ai-wellness.vercel.app`)
4. Service will auto-redeploy

### Realtime websocket auth

CareBank uses a short-lived websocket ticket flow in production:

1. The frontend authenticates to `POST /realtime/ws-ticket` with the normal bearer token.
2. The backend returns a one-time ticket with a TTL of 60 seconds or less.
3. The browser opens `wss://.../ws/{user_id}?ticket=...`.
4. The backend consumes the ticket once and rejects reused, expired, or user-mismatched tickets.

---

## Step 3: Get Your API Keys

### Supabase
1. https://supabase.com → New Project
2. Go to **Settings** → **API**
3. Copy:
   - **Project URL**: `SUPABASE_URL`
   - **anon (public) key**: `SUPABASE_ANON_KEY`

### OpenRouter (Cheaper LLM)
1. https://openrouter.ai → Sign up
2. Go to **Keys** → Create Key
3. Copy API key → `OPENROUTER_API_KEY`
4. Fund account (minimal: $5)

**OR** OpenAI (if you prefer):
1. https://platform.openai.com → API Keys
2. Create new key → `OPENAI_API_KEY`

---

## Step 4: Test Production Deployment

### Test Backend
```bash
curl https://carebank-backend.onrender.com/health
curl https://carebank-backend.onrender.com/preferences \
  -H "Authorization: Bearer YOUR_SUPABASE_TOKEN"
```

### Test Frontend
Visit: `https://your-vercel-app.vercel.app`
- Sign up with email/password
- Try uploading transactions
- Test AI chat feature

---

## Step 5: Enable Auto-Redeploy

### Render
✅ Already configured in `render.yaml` with `autoDeploy: true`

### Vercel
✅ Auto-enabled by default - deploys on every `git push` to main

---

## Cost Breakdown (Monthly)

| Service | Free Tier | After Free |
|---------|-----------|-----------|
| Render | 750 hours (1 service free) | ~$7/month |
| Vercel | Unlimited | ~$20/month |
| Supabase | 500MB DB + 1GB storage | $25+ |
| OpenRouter | Pay-as-you-go | ~$0.15 per 1K tokens |
| **Total** | **$0/month** | **~$50/month** |

---

## Troubleshooting

### Backend won't start
```bash
# Check logs in Render dashboard
1. Render → carebank-backend → Logs
2. Look for Python/FastAPI errors
3. Verify all env vars are set
```

### Frontend blank page
```bash
1. Check browser console (F12)
2. Verify VITE_API_URL is correct
3. Check CORS error in Network tab
```

### CORS Error
Add to [carebank-backend/app/main.py](carebank-backend/app/main.py):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

1. ✅ Create GitHub repo (push this code)
2. ✅ Get API keys (Supabase, OpenRouter)
3. ✅ Deploy backend to Render
4. ✅ Deploy frontend to Vercel
5. ✅ Update env vars
6. ✅ Test both services
7. 🚀 Go live!

**Questions?** Check Render or Vercel docs:
- https://docs.render.com/
- https://vercel.com/docs

# YouTube Summary Bot - Deployment Guide

## 🏗️ Architecture Overview

This project uses a **dual-deployment strategy**:

- **Frontend (Streamlit)**: Deployed on Railway
- **Backend (FastAPI)**: Deployed on Heroku

## 🚀 Deployment Instructions

### Backend Deployment (Heroku)

The backend is already deployed and running on Heroku:
- **URL**: `https://yt-bot-backend-8302f5ba3275.herokuapp.com`
- **Status**: ✅ Healthy with automation running

To redeploy the backend:
```bash
./deploy_backend.sh
```

### Frontend Deployment (Railway)

#### Option 1: Auto-Deploy via GitHub (Recommended)
1. **Connect Railway to GitHub**:
   - Go to [Railway.app](https://railway.app)
   - Create new project from GitHub repo
   - Select `yousuf-fahim/YouTubeSummary`
   - Railway will auto-deploy using our configuration files

2. **Configuration Files** (already included):
   - `railway.toml` - Railway-specific deployment settings
   - `nixpacks.toml` - Python 3.11 build configuration
   - `Procfile` - Process definition for Railway
   - `requirements.txt` - Python dependencies
   - `start.sh` - Startup script with Streamlit configuration

#### Option 2: Manual Deploy via CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Deploy
./deploy_frontend.sh
```

### Environment Variables

#### Railway (Frontend)
Set these in Railway dashboard:
```
BACKEND_URL=https://yt-bot-backend-8302f5ba3275.herokuapp.com
```

#### Heroku (Backend)
Already configured with:
```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_KEY=...
DISCORD_*_WEBHOOK=https://discord.com/api/webhooks/...
```

## 🔧 Configuration Details

### Railway Configuration (`railway.toml`)
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "cd frontend && streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "on_failure"

[env]
BACKEND_URL = "https://yt-bot-backend-8302f5ba3275.herokuapp.com"
```

### Nixpacks Configuration (`nixpacks.toml`)
```json
{
  "providers": ["python"],
  "pythonVersion": "3.11",
  "buildCommand": "pip install -r requirements.txt",
  "startCommand": "cd frontend && streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true",
  "staticDir": "frontend/static"
}
```

### Startup Script (`start.sh`)
```bash
#!/bin/bash
cd frontend
pip install --no-cache-dir -r requirements.txt
exec streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
```

## ✅ Verification Steps

### After Railway Deployment:
1. Check Railway dashboard for deployment URL
2. Visit the frontend URL
3. Verify "Backend Online" status in sidebar
4. Test video processing functionality
5. Check channel tracking features

### Health Check Endpoints:
- **Backend**: `https://yt-bot-backend-8302f5ba3275.herokuapp.com/health`
- **Frontend**: Your Railway domain

## 🛠️ Troubleshooting

### Railway Build Failures:
- Ensure `requirements.txt` is at root level
- Check `nixpacks.toml` Python version (3.11)
- Verify `start.sh` is executable (`chmod +x start.sh`)

### Frontend-Backend Connection Issues:
- Verify `BACKEND_URL` environment variable in Railway
- Check CORS settings in backend
- Test backend health endpoint directly

### Backend Issues (Heroku):
- Check Heroku logs: `heroku logs --app yt-bot-backend --tail`
- Verify environment variables in Heroku dashboard
- Redeploy using `./deploy_backend.sh`

## 📊 Monitoring

- **Backend Logs**: `heroku logs --app yt-bot-backend --tail`
- **Railway Logs**: Available in Railway dashboard
- **Health Checks**: Automated via Railway/Heroku health endpoints
- **Automation Status**: Visible in frontend Automation tab

## 🔄 Update Process

1. Make code changes
2. Commit to main branch: `git commit -m "Update message"`
3. Push to GitHub: `git push origin main`
4. Railway auto-deploys frontend
5. Manually deploy backend if needed: `./deploy_backend.sh`

This setup provides a robust, scalable deployment with automatic updates and health monitoring.

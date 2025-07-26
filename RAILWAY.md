# 🚀 Railway Deployment Guide

## Quick Setup Steps

### 1. Create New Railway Service
1. Go to [Railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose `YouTubeSummary` repository

### 2. Configure Environment Variables
Copy the variables from `railway-env.template` to Railway:

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key

**Optional:**
- `SUPABASE_URL` and `SUPABASE_KEY` - For data persistence
- `BACKEND_URL` - If using separate backend service
- Discord webhook URLs - For notifications

### 3. Railway Auto-Detection
Railway will automatically:
- ✅ Detect Python project from `requirements.txt`
- ✅ Use Nixpacks to build the application
- ✅ Execute `./start.sh` as the start command
- ✅ Navigate to `frontend/` and run Streamlit

### 4. Expected Build Process
```
1. Nixpacks detects Python project
2. Installs dependencies from requirements.txt
3. Executes ./start.sh
4. Script navigates to frontend/
5. Streamlit runs app.py (856 lines)
6. App starts on Railway-assigned port
```

### 5. Build Logs Should Show
```bash
🚀 Starting from root directory...
📂 Current directory: /app
📂 Switched to frontend directory: /app/frontend
📊 App.py exists: YES
📊 App.py line count: 856
```

## Troubleshooting

### If Build Fails
- Check that all environment variables are set
- Verify Railway service has enough resources
- Check build logs for specific error messages

### If App Doesn't Start
- Ensure `OPENAI_API_KEY` is set
- Check that port binding is working (Railway handles this)
- Verify Streamlit configuration in `.streamlit/config.toml`

### If Features Don't Work
- Some features require backend service (channel tracking, daily reports)
- Basic video processing works with just OpenAI API key
- Discord integrations require webhook URLs

## Expected Deployment Time
- **Build time:** 2-3 minutes
- **Cold start:** 30-60 seconds
- **Warm response:** < 5 seconds

## Post-Deployment
1. Visit your Railway-provided URL
2. Test with a YouTube URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
3. Verify the 3-tab interface works correctly
4. Check that API key is recognized in settings

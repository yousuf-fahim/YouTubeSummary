# 🚀 YouTube Summary Bot - Quick Deployment Guide

## ⚡ Quick Start Options

### Option 1: Single-Platform Deployment (Railway - Recommended)
Deploy everything on Railway for simplicity:

```bash
# 1. Fork/Clone this repository to your GitHub
# 2. Go to Railway.app and create new project from GitHub
# 3. Select your forked repository 
# 4. Railway will auto-deploy using our railway.toml configuration
```

**✅ Pros:** Simplest setup, auto-deployment from GitHub
**❌ Cons:** Higher resource usage on single platform

### Option 2: Dual-Platform (Current Setup)
- **Frontend**: Railway (Streamlit)
- **Backend**: Heroku (FastAPI)

**✅ Pros:** Optimized resource usage, better separation
**❌ Cons:** Two platforms to manage

## 🔧 Environment Variables Setup

### Required for Full Functionality:
```bash
# AI Summarization
OPENAI_API_KEY=sk-your-key-here

# Database (Optional - has local fallback)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Discord Integration (Optional)
DISCORD_UPLOADS_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_TRANSCRIPTS_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_SUMMARIES_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_DAILY_REPORT_WEBHOOK=https://discord.com/api/webhooks/...

# Backend URL (for Railway frontend)
BACKEND_URL=https://your-heroku-backend.herokuapp.com
```

### Minimal Setup (Testing):
```bash
# Only this is required for basic functionality
OPENAI_API_KEY=sk-your-key-here
```

## 🎯 Step-by-Step Deployment

### Railway Deployment:
1. **Push to GitHub**: Commit all recent changes
2. **Connect Railway**: Import from GitHub repository
3. **Set Environment Variables**: Add OPENAI_API_KEY at minimum
4. **Deploy**: Railway handles the rest automatically

### Health Check:
- ✅ Visit your Railway URL
- ✅ Check "Backend Online" status in sidebar
- ✅ Test video processing with any YouTube URL
- ✅ Verify Discord integration (if configured)

## 🔍 Troubleshooting

### "Backend Offline" in Frontend:
1. Check BACKEND_URL environment variable
2. Verify backend deployment is running
3. Frontend will fall back to local mode gracefully

### Build Failures:
1. Ensure Python 3.11 is specified in nixpacks.toml
2. Check requirements.txt for missing dependencies
3. Verify start command in railway.toml

### Discord Integration Issues:
1. Verify webhook URLs are correct
2. Test webhooks independently
3. Discord features are optional - app works without them

## 📊 Monitoring & Maintenance

- **Logs**: Available in Railway dashboard
- **Health**: Automatic health checks configured
- **Updates**: Auto-deploy on GitHub push
- **Scaling**: Automatic on Railway

## 🎉 Ready to Ship!

Your bot is production-ready with:
- ✅ Robust error handling & fallbacks
- ✅ Multiple deployment options  
- ✅ Environment-based configuration
- ✅ Automated scheduling & monitoring
- ✅ Discord integration
- ✅ Database persistence with local fallback

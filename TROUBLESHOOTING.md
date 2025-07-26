# 🚨 Deployment Troubleshooting Guide

## Common Streamlit Cloud Issues

### 1. ModuleNotFoundError: dotenv
**Issue**: `from dotenv import load_dotenv` fails in Streamlit Cloud
**Solution**: ✅ **FIXED** - Made dotenv import optional, use `st.secrets` instead

### 2. Backend URL Configuration
**Issue**: Frontend can't connect to backend
**Solutions**:
- In Streamlit Cloud secrets, add:
  ```toml
  BACKEND_URL = "https://your-heroku-app.herokuapp.com"
  ```
- Or use the nested format:
  ```toml
  [general]
  backend_url = "https://your-heroku-app.herokuapp.com"
  ```

### 3. Import Path Issues
**Issue**: Can't import shared modules
**Solution**: The app already handles this with:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
```

## Heroku Backend Issues

### 1. Environment Variables Missing
**Check**: Ensure all config vars are set:
```bash
heroku config
```

**Required vars**:
- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `DISCORD_*_WEBHOOK` (all 4)
- `WEBHOOK_AUTH_TOKEN`

### 2. Build Failures
**Check**: Ensure requirements.txt includes all dependencies:
- `fastapi`
- `uvicorn`
- `openai>=1.3.0`
- `python-dotenv`
- `supabase`

## Quick Fixes

### Redeploy Streamlit App
1. Go to your Streamlit Cloud dashboard
2. Click on your app
3. Click "Reboot app" or "Redeploy"

### Check Heroku Logs
```bash
heroku logs --tail
```

### Test Backend API
Visit: `https://your-heroku-app.herokuapp.com/docs`

## Current Status
✅ GitHub repository is secure and clean
✅ Frontend dotenv issues fixed
✅ Environment variable configuration ready
✅ Backend deployment ready

**Next**: Your Streamlit app should now work! Try redeploying it.

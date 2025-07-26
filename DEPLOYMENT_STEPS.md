# YouTube Summary Bot - Step-by-Step Deployment

## Prerequisites

1. **Heroku Account**: Sign up at [heroku.com](https://heroku.com)
2. **Streamlit Cloud Account**: Sign up at [share.streamlit.io](https://share.streamlit.io)
3. **GitHub Repository**: Push your code to GitHub
4. **Heroku CLI**: Install from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)

## Phase 1: Deploy Backend to Heroku

### Step 1: Prepare Backend Files
Your backend is already configured with:
- ✅ `backend/Procfile` - Contains web server command
- ✅ `backend/requirements.txt` - Contains all dependencies
- ✅ CORS enabled for cross-origin requests

### Step 2: Deploy Backend to Heroku

1. **Login to Heroku CLI**:
   ```bash
   heroku login
   ```

2. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

3. **Initialize Git repository** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial backend commit"
   ```

4. **Create Heroku app**:
   ```bash
   heroku create your-youtube-summary-backend
   ```
   Replace `your-youtube-summary-backend` with your preferred app name.

5. **Set environment variables**:
   ```bash
   # Required environment variables
   heroku config:set SUPABASE_URL="your-supabase-url"
   heroku config:set SUPABASE_KEY="your-supabase-anon-key"
   heroku config:set OPENAI_API_KEY="your-openai-api-key"
   
   # Discord webhook URLs
   heroku config:set DISCORD_UPLOADS_WEBHOOK="your-uploads-webhook-url"
   heroku config:set DISCORD_TRANSCRIPTS_WEBHOOK="your-transcripts-webhook-url"
   heroku config:set DISCORD_SUMMARIES_WEBHOOK="your-summaries-webhook-url"
   heroku config:set DISCORD_DAILY_REPORT_WEBHOOK="your-daily-report-webhook-url"
   ```

6. **Deploy to Heroku**:
   ```bash
   git push heroku main
   ```

7. **Scale the web dyno**:
   ```bash
   heroku ps:scale web=1
   ```

8. **Get your backend URL**:
   ```bash
   heroku info
   ```
   Note the "Web URL" - this will be something like `https://your-youtube-summary-backend.herokuapp.com`

### Step 3: Test Backend
Visit `https://your-app-name.herokuapp.com/docs` to see the FastAPI documentation.

## Phase 2: Deploy Frontend to Streamlit Cloud

### Step 1: Prepare Frontend Configuration

1. **Ensure secrets.toml is configured**:
   Your `frontend/.streamlit/secrets.toml` should contain:
   ```toml
   BACKEND_URL = "https://your-youtube-summary-backend.herokuapp.com"
   ```

### Step 2: Push to GitHub

1. **Push entire project to GitHub**:
   ```bash
   cd ..  # Back to project root
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

### Step 3: Deploy to Streamlit Cloud

1. **Go to [share.streamlit.io](https://share.streamlit.io)**
2. **Click "New app"**
3. **Connect your GitHub repository**
4. **Configure deployment**:
   - Repository: `your-username/YouTubeSummary`
   - Branch: `main`
   - Main file path: `frontend/app.py`
   - Python version: `3.9`

5. **Add secrets in Streamlit Cloud**:
   - Click "Advanced settings"
   - In the "Secrets" section, add:
     ```toml
     BACKEND_URL = "https://your-youtube-summary-backend.herokuapp.com"
     ```

6. **Deploy**: Click "Deploy!"

## Phase 3: Configure Production Settings

### Update Discord Webhook for Backend
In your Discord server, update the webhook URL to point to your Heroku backend:
```
https://your-youtube-summary-backend.herokuapp.com/webhook/discord
```

### Verify Environment Variables
Check that all environment variables are set correctly:

**Heroku Backend**:
```bash
heroku config
```

**Streamlit Cloud**: Check in the app settings on share.streamlit.io

## Phase 4: Testing

### Test Backend API
Visit your backend URL and test endpoints:
- `GET /api/status` - Should return "healthy"
- `GET /api/channels/status` - Should return channel tracking info
- `GET /api/scheduler/status` - Should return scheduler info

### Test Frontend
Visit your Streamlit app URL and:
1. Check that all tabs load correctly
2. Try adding a YouTube channel
3. Verify the daily report timer shows up
4. Test manual video processing

### Test Discord Integration
Post a YouTube URL in your Discord channel to verify the webhook works.

## Troubleshooting

### Common Issues

1. **Backend not starting**:
   - Check `heroku logs --tail` for errors
   - Verify all environment variables are set
   - Check requirements.txt for missing dependencies

2. **Frontend can't connect to backend**:
   - Verify BACKEND_URL in Streamlit secrets
   - Check CORS configuration in backend
   - Ensure Heroku app is running

3. **Discord webhook not working**:
   - Verify webhook URL is updated to Heroku backend
   - Check webhook permissions in Discord
   - Check heroku logs for webhook errors

### Monitoring Commands

```bash
# Check backend logs
heroku logs --tail

# Check backend status
heroku ps

# Restart backend if needed
heroku restart
```

## Cost Breakdown

- **Heroku**: Free tier (with some limitations)
- **Streamlit Cloud**: Free for public repositories
- **Supabase**: Free tier (500MB database)
- **OpenAI API**: Pay-per-use (approx $0.002 per summary)

**Total monthly cost**: ~$5-20 depending on usage

## Next Steps

1. Set up monitoring and alerts
2. Configure custom domain (optional)
3. Set up automated backups for your data
4. Add logging and analytics

Your YouTube Summary Bot is now live and ready to use! 🚀

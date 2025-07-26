# 🔒 Security Notice

This project has been secured to prevent credential exposure. **All sensitive data is now stored in environment variables.**

## ⚠️ IMPORTANT: Required Environment Variables

Before running this application, you MUST set these environment variables:

### Required for Backend
```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# AI Service  
OPENAI_API_KEY=sk-proj-your-openai-api-key

# Discord Integrations
DISCORD_UPLOADS_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_TRANSCRIPTS_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_SUMMARIES_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_DAILY_REPORT_WEBHOOK=https://discord.com/api/webhooks/...

# Security
WEBHOOK_AUTH_TOKEN=your-secure-token
```

## 🛡️ Security Features

- ✅ **No credentials in code**: All sensitive data in environment variables
- ✅ **Secure by default**: ConfigService prioritizes env vars over database
- ✅ **Git protection**: .gitignore prevents credential commits  
- ✅ **Production ready**: Environment-based configuration
- ✅ **Heroku compatible**: Uses config vars in production

## 📝 Setup Instructions

1. **Copy environment template**:
   ```bash
   cp .env.template .env
   ```

2. **Fill in your actual values** in `.env` file

3. **For Heroku deployment**, set config vars:
   ```bash
   heroku config:set OPENAI_API_KEY="your-key"
   heroku config:set SUPABASE_URL="your-url"
   # ... etc for all variables
   ```

4. **For Streamlit Cloud**, add to secrets:
   ```toml
   BACKEND_URL = "https://your-heroku-app.herokuapp.com"
   ```

## 🚨 Never Commit

- `.env` files (already in .gitignore)
- Any files containing API keys
- Config files with credentials
- Discord webhook URLs in code

Your secrets are safe! 🛡️

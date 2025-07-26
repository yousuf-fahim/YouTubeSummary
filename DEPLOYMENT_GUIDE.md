# YouTube Summary Bot - Deployment Guide

## 🚀 Deployment Strategy: Backend (Heroku) + Frontend (Streamlit Cloud)

### Why This Approach?
- **Cost Effective**: Only pay for backend (~$7/month)
- **Reliable**: Heroku for API, Streamlit Cloud for UI
- **Scalable**: Both platforms handle scaling automatically
- **Easy**: Streamlit Cloud has simple GitHub integration

---

## 📋 Pre-Deployment Checklist

### ✅ Required Accounts
- [ ] GitHub account (for code repository)
- [ ] Heroku account (for backend deployment)
- [ ] Streamlit Cloud account (free, uses GitHub auth)

### ✅ Required Files
- [ ] Backend requirements.txt
- [ ] Backend Procfile 
- [ ] Frontend requirements.txt
- [ ] Environment variables documented

---

## 🔧 Step 1: Prepare Backend for Heroku

### Update Backend Structure
The backend needs to be deployable as a standalone service.

### Environment Variables Needed
- SUPABASE_URL
- SUPABASE_KEY  
- OPENAI_API_KEY
- DISCORD_*_WEBHOOK (4 webhook URLs)

---

## 🔧 Step 2: Prepare Frontend for Streamlit Cloud

### Frontend will connect to Heroku backend
- Update API endpoints to use Heroku URL
- Add environment variable for backend URL
- Ensure all dependencies are in requirements.txt

---

## 📝 Deployment Commands

### Backend to Heroku:
```bash
# Navigate to backend directory
cd backend

# Initialize git (if not already)
git init
git add .
git commit -m "Initial backend commit"

# Create Heroku app
heroku create your-youtube-bot-api

# Set environment variables
heroku config:set SUPABASE_URL=your_url
heroku config:set SUPABASE_KEY=your_key
# ... (all other env vars)

# Deploy
git push heroku main
```

### Frontend to Streamlit Cloud:
1. Push code to GitHub repository
2. Go to share.streamlit.io
3. Connect GitHub repo
4. Select frontend/app.py
5. Add environment variables in Streamlit Cloud dashboard

---

## 💰 Cost Breakdown

### Monthly Costs:
- **Heroku Backend**: ~$7/month (Eco dyno)
- **Streamlit Cloud**: Free
- **Supabase**: Free tier (up to 50MB database)
- **Total**: ~$7/month

### Free Alternatives:
- **Railway**: 500 hours/month free
- **Render**: 750 hours/month free  
- **Fly.io**: Generous free tier

---

## 🔒 Security Considerations

### Environment Variables:
- Never commit API keys to git
- Use Heroku config vars for backend
- Use Streamlit secrets for frontend
- Rotate webhook tokens periodically

### CORS Setup:
- Configure CORS in FastAPI for Streamlit Cloud domain
- Add allowed origins for production

---

## 📊 Monitoring & Maintenance

### Heroku Features:
- Built-in logging and metrics
- Easy scaling if needed
- Automatic SSL certificates
- Custom domain support

### Streamlit Cloud Features:
- Automatic deploys on git push
- Built-in authentication options
- Usage analytics
- Custom domains (paid)

---

## 🚨 Common Issues & Solutions

### Backend Issues:
- **Port binding**: Use `PORT` env var from Heroku
- **Database connections**: Verify Supabase connectivity
- **API timeouts**: Configure appropriate timeout values

### Frontend Issues:
- **CORS errors**: Update FastAPI CORS settings
- **API connection**: Verify backend URL in frontend
- **Secrets management**: Use Streamlit secrets.toml

---

## 📈 Scaling Options

### When to Scale:
- High API usage (>1000 requests/day)
- Multiple users accessing frontend
- Large number of tracked channels

### Scaling Steps:
1. **Heroku**: Upgrade dyno type or add more dynos
2. **Database**: Upgrade Supabase plan if needed
3. **Frontend**: Streamlit Cloud handles this automatically

---

## 🎯 Next Steps

1. **Prepare files** for deployment
2. **Set up accounts** (Heroku, Streamlit Cloud)
3. **Deploy backend** to Heroku first
4. **Deploy frontend** to Streamlit Cloud
5. **Test end-to-end** functionality
6. **Set up monitoring** and alerts

Would you like me to help you with any specific step?

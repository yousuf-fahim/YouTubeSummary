# 🚂 Railway Environment Variables Setup Guide

## 🚨 Critical Issues Found:

### 1. **Transcription Fixed** ✅
- Fixed transcript processing bug in `shared/transcript.py`
- Now handles different transcript segment formats properly

### 2. **Missing Environment Variables** ❌
Your Railway deployment needs these environment variables:

```bash
# REQUIRED FOR BASIC FUNCTIONALITY
OPENAI_API_KEY=sk-your-openai-key-here

# DISCORD WEBHOOKS (for notifications)
DISCORD_WEBHOOK_UPLOADS=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
DISCORD_WEBHOOK_TRANSCRIPTS=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
DISCORD_WEBHOOK_SUMMARIES=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
DISCORD_WEBHOOK_DAILY_REPORT=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# SUPABASE (for data storage and caching)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# BACKEND (for channel tracking - if you have a separate backend service)
BACKEND_URL=https://your-backend-service.railway.app
```

## 🔧 How to Add Variables to Railway:

### **Step 1: Access Railway Dashboard**
1. Go to https://railway.app/dashboard
2. Find your "YouTubeSummary" project
3. Click on the frontend service

### **Step 2: Add Environment Variables**
1. Click on the **"Variables"** tab
2. For each variable above:
   - Click **"New Variable"**
   - Enter the **Name** (e.g., `OPENAI_API_KEY`)
   - Enter the **Value** (your actual key/URL)
   - Click **"Add"**

### **Step 3: Deploy**
Railway will automatically redeploy when you add variables (takes 2-3 minutes).

## 📋 Priority Order:

### **IMMEDIATE (Required for basic video processing):**
```bash
OPENAI_API_KEY=sk-your-key-here
```

### **HIGH (Required for Discord notifications):**
```bash
DISCORD_WEBHOOK_UPLOADS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_SUMMARIES=https://discord.com/api/webhooks/...
```

### **MEDIUM (For data persistence):**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

### **LOW (For channel tracking - requires separate backend):**
```bash
BACKEND_URL=https://your-backend-service.railway.app
```

## 🎯 **Quick Test After Adding OPENAI_API_KEY:**

1. Add `OPENAI_API_KEY` to Railway
2. Wait 2-3 minutes for redeployment
3. Visit: https://youtubesummary.up.railway.app
4. Try processing: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
5. Should work without page resets or errors!

## 📨 **Discord Webhook Setup:**

### **To get Discord webhook URLs:**
1. Go to your Discord server
2. Right-click on the channel where you want notifications
3. Select **"Edit Channel"**
4. Go to **"Integrations"** → **"Webhooks"**
5. Click **"Create Webhook"**
6. Copy the **"Webhook URL"**
7. Repeat for each channel you want (uploads, summaries, etc.)

## 🗄️ **Supabase Setup (Optional but Recommended):**

### **To get Supabase credentials:**
1. Go to https://supabase.com/dashboard
2. Create a new project or use existing
3. Go to **"Settings"** → **"API"**
4. Copy:
   - **URL**: Project URL
   - **Key**: `anon` `public` key

## 📺 **Backend Service (For Channel Tracking):**

If you want channel tracking, you need to deploy the backend separately:
1. Deploy `backend/` folder as a separate Railway service
2. Set `BACKEND_URL` to point to that service
3. Backend handles scheduling and channel monitoring

---

## 🚀 **After Setup:**

Once you add the environment variables, your app should:
- ✅ Process videos without errors
- ✅ Send Discord notifications (if webhooks configured)
- ✅ Cache transcripts (if Supabase configured)
- ✅ Track channels (if backend configured)

**The page reset issues are already fixed!** 🎉

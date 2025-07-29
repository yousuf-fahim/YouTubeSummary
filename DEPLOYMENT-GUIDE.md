# YouTube Summary Bot - Deployment Guide

## 🚀 Production Deployment Overview

This guide covers deploying the YouTube Summary Bot with enhanced features including:
- Real-time notifications
- Advanced search and filtering
- Video thumbnail previews  
- Discord command integration
- Analytics dashboard
- Bulk video processing

## Architecture

- **Frontend**: Next.js 15 (Deployed on Vercel)
- **Backend**: FastAPI (Deployed on Heroku)
- **Database**: Supabase (PostgreSQL)
- **AI**: OpenAI GPT models
- **Discord Integration**: Webhook-based slash commands

---

## Backend Deployment (Heroku)

### ✅ Already Completed
The backend is successfully deployed at: `https://yt-bot-backend-8302f5ba3275.herokuapp.com`

### Current Features:
- ✅ Video processing endpoints
- ✅ Monitoring and tracking
- ✅ Discord webhook integration
- ✅ Analytics endpoints
- ✅ Bulk processing
- ✅ Daily report generation

### Environment Variables:
- `OPENAI_API_KEY`: OpenAI API key
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `DISCORD_WEBHOOK_URL`: Discord webhook URL
- `DISCORD_APPLICATION_ID`: Discord app ID
- `DISCORD_PUBLIC_KEY`: Discord public key
- `DISCORD_BOT_TOKEN`: Discord bot token

---

## Frontend Deployment (Vercel)

### Prerequisites:
1. Vercel account (free tier sufficient)
2. Repository connected to GitHub/GitLab

### Deployment Steps:

#### Option 1: Vercel CLI (Quick Deploy)
```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to frontend directory
cd frontend-nextjs

# Login to Vercel
vercel login

# Deploy to production
vercel --prod
```

#### Option 2: Vercel Dashboard (Recommended)
1. Visit [vercel.com](https://vercel.com)
2. Connect your GitHub repository
3. Select the `frontend-nextjs` folder as root directory
4. Configure environment variables:
   - `NEXT_PUBLIC_API_URL`: `https://yt-bot-backend-8302f5ba3275.herokuapp.com`
   - `NEXT_PUBLIC_APP_NAME`: `YouTube Summary Bot`
   - `NEXT_PUBLIC_APP_DESCRIPTION`: `AI-powered YouTube video summarization`
5. Deploy

### Environment Configuration:
The project includes:
- `.env.local` - Local development
- `.env.production` - Production settings
- `vercel.json` - Vercel deployment config

---

## Database Setup (Supabase)

### ✅ Already Configured
The database schema is set up with tables:
- `summaries` - Video summaries and metadata
- `tracked_channels` - YouTube channels being monitored
- `transcripts` - Video transcript storage
- `config` - Application configuration

### Required Policies:
```sql
-- Enable RLS and create policies for public access
ALTER TABLE summaries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable read access for all users" ON summaries FOR SELECT USING (true);
CREATE POLICY "Enable insert for all users" ON summaries FOR INSERT WITH CHECK (true);
```

---

## Discord Bot Setup

### Application Setup:
1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application
3. Go to "Bot" section, create bot token
4. Go to "OAuth2" > "URL Generator"
5. Select scopes: `applications.commands`, `bot`
6. Select permissions: `Send Messages`, `Use Slash Commands`

### Slash Commands:
Configure these commands in Discord Developer Portal:
- `/summarize <url>` - Summarize a YouTube video
- `/status` - Check bot status
- `/recent` - Get recent summaries
- `/help` - Show help information

### Environment Variables:
Add to Heroku backend:
```
DISCORD_APPLICATION_ID=your_app_id
DISCORD_PUBLIC_KEY=your_public_key
DISCORD_BOT_TOKEN=your_bot_token
```

---

## Testing Deployment

### Backend Health Check:
```bash
curl https://yt-bot-backend-8302f5ba3275.herokuapp.com/health
```

### Frontend Verification:
1. Visit deployed Vercel URL
2. Test video processing
3. Verify real-time notifications
4. Check analytics dashboard
5. Test advanced search features

### Discord Integration:
1. Invite bot to Discord server
2. Test slash commands
3. Verify webhook responses

---

## Monitoring & Analytics

### Available Endpoints:
- `/analytics/overview` - System statistics
- `/analytics/recent` - Recent activity
- `/monitoring/status` - System health
- `/reports/test` - Generate test report

### Performance Monitoring:
- Heroku metrics dashboard
- Vercel analytics
- Supabase dashboard
- Discord webhook logs

---

## Security Considerations

### API Security:
- ✅ CORS configured for frontend domain
- ✅ Discord signature verification
- ✅ Input validation and sanitization
- ✅ Rate limiting on bulk operations

### Environment Variables:
- Never commit `.env` files
- Use Vercel/Heroku environment variable settings
- Rotate API keys regularly

---

## Scaling Considerations

### Performance Optimization:
- Implement Redis caching for frequent queries
- Use CDN for static assets
- Database connection pooling
- Background job queues for heavy processing

### Resource Limits:
- Heroku: 512MB RAM, 1 dyno (free tier)
- Vercel: 100GB bandwidth, unlimited deployments
- Supabase: 500MB database, 50MB file storage

---

## Troubleshooting

### Common Issues:

1. **CORS Errors**: Verify `NEXT_PUBLIC_API_URL` matches backend URL
2. **Database Connection**: Check Supabase credentials and network access
3. **Discord Commands**: Verify webhook URL and signature verification
4. **Build Failures**: Check Node.js version compatibility (Node 18+)

### Debug Mode:
Set `NEXT_PUBLIC_DEBUG_MODE=true` for additional logging

### Logs Access:
- Heroku: `heroku logs --tail -a your-app-name`
- Vercel: Dashboard > Functions tab
- Supabase: Dashboard > Logs section

---

## Next Steps

### Phase 6 - Advanced Features:
- [ ] Mobile-responsive PWA
- [ ] Offline support with service workers
- [ ] Push notifications
- [ ] Multi-language support
- [ ] Advanced AI features (sentiment analysis, topic extraction)
- [ ] Integration with other platforms (Twitter, Reddit)

### CI/CD Pipeline:
- [ ] GitHub Actions for automated testing
- [ ] Automated deployment on merge to main
- [ ] Database migration scripts
- [ ] Performance monitoring alerts

### Production Readiness:
- [ ] Custom domain setup
- [ ] SSL certificate configuration
- [ ] Backup and disaster recovery
- [ ] User authentication system

---

## Support & Maintenance

### Regular Tasks:
- Monitor API usage and costs
- Update dependencies monthly
- Review and rotate API keys
- Database maintenance and optimization
- Performance monitoring and optimization

### Resource Links:
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Discord Developer Documentation](https://discord.com/developers/docs)
- [Vercel Documentation](https://vercel.com/docs)
- [Heroku Documentation](https://devcenter.heroku.com/)

---

*Last Updated: January 29, 2025*
*YouTube Summary Bot v2.0 - Enhanced Production Deployment*

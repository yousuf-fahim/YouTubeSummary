# YouTube Summary Bot

AI-powered YouTube video summarization with Discord integration and automated monitoring.

## 🚀 Live Deployment

- **Backend (FastAPI)**: `https://yt-bot-backend-8302f5ba3275.herokuapp.com` ✅ Live on Heroku
- **Frontend (Streamlit)**: Auto-deploying to Railway ✅ 
- **Status**: Fully operational with automated YouTube monitoring

## Features

- 🎥 **Automated Monitoring**: Track YouTube channels and process new videos automatically
- 📝 **Transcript Extraction**: Multi-source transcript extraction (YouTube API, fallbacks)
- 🤖 **AI Summarization**: OpenAI-powered intelligent video summaries
- � **Daily Reports**: Automated daily digest of processed videos
- 🎛️ **Web Interface**: Streamlit frontend for configuration and manual processing
- 🗄️ **Cloud Storage**: Supabase integration with local fallback
- 📢 **Discord Integration**: Multi-channel Discord webhook delivery
- ⏰ **Scheduling**: Automated channel monitoring every 30 minutes + daily reports at 18:00 CEST

## Architecture

**Dual-Deployment Strategy:**
- **Frontend**: Streamlit app deployed on Railway
- **Backend**: FastAPI server deployed on Heroku  
- **Database**: Supabase (PostgreSQL) with local JSON fallback
- **AI**: OpenAI GPT for summarization
- **Integration**: Discord webhooks for notifications

## Requirements

- Python 3.11+
- OpenAI API key
- Discord webhook URLs for target channels
- Supabase account (optional, has local fallback)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd yt-discord-bot
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. (Optional) Build the UI:
   ```
   cd ui
   npm install
   npm run build
   cd ..
   ```

## Configuration

You can configure the bot through the web UI or by directly editing `data/config.json`:

```json
{
  "openai_api_key": "your-openai-key",
  "webhooks": {
    "uploads": "discord-webhook-url-for-uploads-channel",
    "transcripts": "discord-webhook-url-for-transcripts-channel",
    "summaries": "discord-webhook-url-for-summaries-channel",
    "report": "discord-webhook-url-for-daily-report-channel"
  }
}
```

### Supabase Setup

1. Create a new project in Supabase
2. Run the SQL in `supabase_schema.sql` in the Supabase SQL editor to create tables
3. Copy your Supabase URL and anon key from the API settings
4. Set up environment variables:

```
# Copy env.example to .env and update values
cp env.example .env
```

Edit the `.env` file with your Supabase credentials:

```
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

## Running the Bot

Start the bot with:

```
python main.py
```

This will:
1. Start a web server on `http://localhost:8000`
2. Begin listening for YouTube links posted to Discord
3. Start the scheduler for daily reports (18:00 CEST)

## Discord Setup

1. Create channels in your Discord server:
   - `#yt-uploads`: Channel where YouTube links will be posted
   - `#yt-transcripts`: Channel for full video transcripts
   - `#yt-summaries`: Channel for AI-generated summaries
   - `#daily-report`: Channel for daily summary reports

2. For each channel, create a webhook:
   - Go to Channel Settings > Integrations > Webhooks
   - Create a new webhook
   - Copy the webhook URL
   - Add it to the bot's configuration

## Data Storage

This application uses two storage options:

1. **Supabase (Recommended for Production)**: 
   - Stores transcripts, summaries, and configuration in PostgreSQL
   - Provides cloud persistence for Heroku and other cloud deployments
   - Eliminates issues with ephemeral filesystems

2. **Local File System (Fallback)**:
   - Used if Supabase is not configured
   - Stores data in the `data/` directory
   - Not recommended for Heroku (files will be lost on dyno restart)

## Deployment

This bot is designed to be deployed to services like Railway, Render, Fly.io or Heroku.

### Heroku Deployment

For Heroku deployment, make sure to set the Supabase environment variables:

```
heroku config:set SUPABASE_URL=https://your-supabase-url.supabase.co
heroku config:set SUPABASE_KEY=your-supabase-anon-key
```

### Railway
```
railway up
```

### Render
Connect your repository to Render and set the build command to:
```
pip install -r requirements.txt && cd ui && npm install && npm run build && cd ..
```

And the start command to:
```
python main.py
```

## License

MIT 
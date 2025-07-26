# YouTube Summary Bot - AI Development Guide

## Architecture Overview

This is a YouTube-to-Discord AI summarization bot with a **3-tier architecture**:

- **`backend/`**: FastAPI server (`main.py`) with REST endpoints, scheduler (`schedule.py`), and Discord webhook handling
- **`frontend/`**: Streamlit web UI (`app.py`) for configuration and manual processing
- **`shared/`**: Common utilities imported by both tiers using relative imports (`.module_name`)

Both backend and frontend are **separate deployable services** with their own `Procfile` and `requirements.txt`.

## Critical Import Pattern

All modules use this path setup pattern:
```python
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from shared.module_name import function_name
```

**Never** use `from module_name import` - always prefix with `shared.` for cross-module imports.

## Data Flow Architecture

1. **Discord Webhook → Backend**: YouTube URLs posted to Discord trigger processing via `shared.discord_listener`
2. **Transcript Extraction**: `shared.transcript.py` uses YouTube Transcript API with Supabase/local fallback storage
3. **AI Summarization**: `shared.summarize.py` chunks content and calls OpenAI API with structured prompts
4. **Storage**: Dual-mode storage via `shared.supabase_utils.py` (Supabase preferred, local JSON fallback)
5. **Discord Output**: Formatted summaries sent to different Discord channels via `shared.discord_utils.py`

## Essential Development Commands

### Run Both Services Locally
```bash
# Backend (FastAPI on :8000)
cd backend && python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Streamlit on :8501)  
cd frontend && python3 -m streamlit run app.py --server.port 8501
```

### Deploy to Heroku (Separate Apps)
```bash
# Backend deployment
cd backend && git init && git add . && git commit -m "Backend"
heroku create your-backend-app && git push heroku main

# Frontend deployment  
cd frontend && git init && git add . && git commit -m "Frontend"
heroku create your-frontend-app && git push heroku main
```

## Configuration Patterns

### Environment Variables (`.env` file)
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
OPENAI_API_KEY=sk-...
DISCORD_*_WEBHOOK=https://discord.com/api/webhooks/...
```

### Storage Hierarchy
1. **Supabase** (preferred): PostgreSQL tables defined in `shared/supabase_schema.sql`
2. **Local fallback**: JSON files in `shared/data/` (transcripts/, summaries/, config.json)

The system automatically falls back to local storage if Supabase is unavailable.

## Key Integration Points

### Discord Webhooks (4 separate channels)
- `DISCORD_UPLOADS_WEBHOOK`: Original YouTube links
- `DISCORD_TRANSCRIPTS_WEBHOOK`: Full transcripts  
- `DISCORD_SUMMARIES_WEBHOOK`: AI summaries
- `DISCORD_DAILY_REPORT_WEBHOOK`: Scheduled daily reports

### AI Summarization (OpenAI)
Uses structured prompts in `shared.summarize.py`:
- `DEFAULT_SUMMARY_PROMPT`: Extracts key points, mentions, verdict
- `DEFAULT_DAILY_REPORT_PROMPT`: Aggregates multiple summaries
- Content is chunked for long videos (>4000 chars)

### Scheduling
Backend runs APScheduler with CEST timezone for daily reports at 18:00.

## File Structure Patterns

```
├── backend/           # FastAPI service
│   ├── main.py       # API endpoints + Discord webhook handling
│   ├── schedule.py   # APScheduler for daily reports
│   └── Procfile      # Heroku: uvicorn main:app
├── frontend/         # Streamlit service  
│   ├── app.py        # Web UI for config + manual processing
│   └── Procfile      # Heroku: streamlit run app.py
└── shared/           # Cross-service utilities
    ├── discord_*.py  # Discord integrations
    ├── transcript.py # YouTube API + storage
    ├── summarize.py  # OpenAI integration
    └── supabase_*.py # Database layer
```

## Debugging Common Issues

- **Import errors**: Check `sys.path.append` pattern and `shared.` prefixes
- **Storage failures**: Verify Supabase credentials or check `shared/data/` permissions
- **Discord webhook 404s**: Verify webhook URLs haven't expired
- **YouTube transcript fails**: API returns various error types handled in `transcript.py`
- **OpenAI rate limits**: Summarization includes retry logic with exponential backoff

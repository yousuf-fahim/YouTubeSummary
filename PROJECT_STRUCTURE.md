# YouTube Summary Project Structure

This project has been restructured for Heroku deployment with separate backend and frontend components.

## Directory Structure

```
YouTubeSummary/
├── backend/              # FastAPI server
│   ├── main.py          # FastAPI application entry point
│   ├── start_server.py  # Server startup script
│   ├── schedule.py      # Scheduler for periodic tasks
│   ├── requirements.txt # Backend dependencies
│   ├── Procfile         # Heroku deployment config for backend
│   └── env.example      # Environment variables example
├── frontend/            # Streamlit application
│   ├── app.py          # Streamlit app entry point
│   ├── stop_server.py  # Server stop utility
│   ├── requirements.txt # Frontend dependencies
│   └── Procfile        # Heroku deployment config for frontend
├── shared/             # Common utilities and modules
│   ├── __init__.py     # Python package initialization
│   ├── transcript.py   # YouTube transcript handling
│   ├── summarize.py    # Content summarization
│   ├── supabase_utils.py # Supabase database utilities
│   ├── youtube_tracker.py # YouTube channel tracking
│   ├── discord_utils.py # Discord messaging utilities
│   ├── discord_listener.py # Discord bot functionality
│   ├── supabase_schema.sql # Database schema
│   └── data/           # Shared data files
│       ├── config.json
│       ├── summaries.json
│       ├── tracked_channels.json
│       ├── summaries/
│       └── transcripts/
└── README.md           # This file
```

## Deployment

### Backend (FastAPI)
Deploy the `backend/` directory to Heroku with:
```bash
cd backend
git init
git add .
git commit -m "Initial backend commit"
heroku create your-backend-app
git push heroku main
```

### Frontend (Streamlit)
Deploy the `frontend/` directory to Heroku with:
```bash
cd frontend
git init
git add .
git commit -m "Initial frontend commit"
heroku create your-frontend-app
git push heroku main
```

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Environment Variables

Copy `backend/env.example` to `backend/.env` and `frontend/.env` and configure:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OPENAI_API_KEY`
- Discord webhook URLs

## Notes

- Both applications need access to the `shared/` directory
- Make sure to install dependencies from the respective `requirements.txt` files
- The shared modules are imported using relative imports within the project structure

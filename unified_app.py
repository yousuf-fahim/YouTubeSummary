"""
Unified App: FastAPI Backend + Streamlit Frontend on Heroku
This combines both services into a single Heroku deployment
"""
import os
import sys
import subprocess
import threading
import time
import uvicorn
from pathlib import Path

# Add shared modules to path
sys.path.append(str(Path(__file__).parent / "shared"))

def run_backend():
    """Run FastAPI backend server"""
    print("🚀 Starting FastAPI backend...")
    from backend.main import app
    
    # Run on a different port than the main web port
    backend_port = int(os.environ.get("BACKEND_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=backend_port, log_level="info")

def run_frontend():
    """Run Streamlit frontend"""
    print("🎨 Starting Streamlit frontend...")
    
    # Set backend URL to local backend
    os.environ["BACKEND_URL"] = f"http://localhost:{os.environ.get('BACKEND_PORT', '8001')}"
    
    # Get Heroku port
    port = int(os.environ.get("PORT", "8501"))
    
    # Run Streamlit
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "frontend/app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ])

if __name__ == "__main__":
    print("🏗️ Starting YouTube Summary Bot - Unified Deployment")
    
    # Start backend in a separate thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # Give backend time to start
    time.sleep(3)
    
    # Start frontend (this will block)
    run_frontend()

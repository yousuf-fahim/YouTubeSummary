#!/usr/bin/env python3
"""
Helper script to start the YouTube Summary backend server and Streamlit frontend.
This script is used for Heroku deployment to run both components.
"""

import os
import sys
import time
import signal
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("server_starter")

def is_server_running():
    """Check if the server is already running on port 8000"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        return result == 0  # Return True if port is open (result is 0)
    except:
        return False

def start_server():
    """Start the FastAPI server from main.py and the Streamlit frontend"""
    logger.info("Starting YouTube Summary backend server...")
    
    # Find Python executable
    python_exec = sys.executable
    
    # Get the directory of this script
    script_dir = Path(__file__).parent.absolute()
    
    # Construct the main.py path
    main_path = script_dir / "main.py"
    app_path = script_dir / "app.py"
    
    if not main_path.exists():
        logger.error(f"Server script not found at {main_path}")
        return False
        
    if not app_path.exists():
        logger.error(f"Streamlit app script not found at {app_path}")
        return False
    
    # Get port from environment (Heroku sets PORT env var)
    port = int(os.environ.get("PORT", "8000"))
    streamlit_port = port + 1 if port != 8501 else 8502  # Use different port for Streamlit
    
    # Create a .streamlit/config.toml file to configure Streamlit
    streamlit_config_dir = script_dir / ".streamlit"
    os.makedirs(streamlit_config_dir, exist_ok=True)
    
    with open(streamlit_config_dir / "config.toml", "w") as f:
        f.write(f"""
[server]
port = {streamlit_port}
enableCORS = false
enableXsrfProtection = false

[browser]
serverPort = {streamlit_port}
serverAddress = "0.0.0.0"
""")
    
    try:
        # Launch FastAPI server with uvicorn
        fastapi_cmd = [python_exec, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
        
        # Launch Streamlit app
        streamlit_cmd = [python_exec, "-m", "streamlit", "run", str(app_path), "--server.port", str(streamlit_port), "--server.address", "0.0.0.0"]
        
        # Log commands
        logger.info(f"Running FastAPI command: {' '.join(fastapi_cmd)}")
        logger.info(f"Running Streamlit command: {' '.join(streamlit_cmd)}")
        
        # For Heroku, we need to run FastAPI in the background and Streamlit in the foreground
        # Start FastAPI in the background
        if os.name == 'nt':  # Windows
            fastapi_process = subprocess.Popen(
                fastapi_cmd,
                cwd=script_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:  # Unix/Linux/Mac
            fastapi_process = subprocess.Popen(
                fastapi_cmd,
                cwd=script_dir,
                start_new_session=True
            )
            
        # Wait a moment to allow the server to start
        time.sleep(3)
        
        # Check if FastAPI server is running
        if is_server_running():
            logger.info("FastAPI server started successfully!")
            
            # Run Streamlit in the foreground (this will keep the process running)
            logger.info("Starting Streamlit frontend...")
            
            # On Heroku, we need to exec the Streamlit process (replace current process)
            if "DYNO" in os.environ:
                logger.info("Running on Heroku, using exec to start Streamlit")
                os.execvp(python_exec, [python_exec, "-m", "streamlit", "run", str(app_path), 
                                      "--server.port", str(streamlit_port), 
                                      "--server.address", "0.0.0.0",
                                      "--browser.serverPort", str(streamlit_port),
                                      "--server.enableCORS", "false"])
            else:
                # For local development, just start Streamlit normally
                subprocess.run(streamlit_cmd)
            
            return True
        else:
            logger.error("FastAPI server failed to start properly.")
            return False
        
    except Exception as e:
        logger.error(f"Failed to start servers: {e}")
        return False

if __name__ == "__main__":
    # Check if server is already running
    if is_server_running():
        logger.info("Server is already running on port 8000.")
        sys.exit(0)
    
    # Start the servers
    if start_server():
        logger.info("YouTube Summary backend and frontend are now running.")
        
        # Display helpful message
        print("\n" + "=" * 80)
        print("YouTube Summary is now running!")
        print("The Discord bot is now online and will process new videos automatically.")
        port = int(os.environ.get("PORT", "8000"))
        streamlit_port = port + 1 if port != 8501 else 8502
        print(f"You can access the API at: http://localhost:{port}")
        print(f"You can access the UI at: http://localhost:{streamlit_port}")
        print("=" * 80 + "\n")
    else:
        logger.error("Failed to start services.")
        sys.exit(1) 
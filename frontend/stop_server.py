#!/usr/bin/env python3
"""
Helper script to stop the YouTube Summary backend server.
This script finds and stops the FastAPI server running on port 8000.
"""

import os
import sys
import logging
import subprocess
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("server_stopper")

def is_server_running():
    """Check if the server is running on port 8000"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        return result == 0  # Return True if port is open (result is 0)
    except:
        return False

def find_and_kill_server():
    """Find and kill the server process on port 8000"""
    try:
        if os.name == 'nt':  # Windows
            # Find process using port 8000 on Windows
            try:
                netstat_output = subprocess.check_output(
                    'netstat -ano | findstr :8000', 
                    shell=True
                ).decode()
                
                if netstat_output:
                    # Extract PID from netstat output
                    lines = netstat_output.strip().split('\n')
                    for line in lines:
                        if 'LISTENING' in line:
                            pid = line.strip().split()[-1]
                            try:
                                logger.info(f"Killing process with PID {pid}")
                                subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                                return True
                            except:
                                pass
            except:
                pass
                
            logger.error("Could not find server process on Windows.")
            return False
            
        else:  # Unix/Linux/Mac
            # Find process using port 8000 on Unix-like systems
            try:
                if sys.platform == 'darwin':  # macOS
                    cmd = "lsof -i :8000 | grep LISTEN | awk '{print $2}'"
                else:  # Linux and other Unix
                    cmd = "netstat -tulpn | grep :8000 | awk '{print $7}' | cut -d'/' -f1"
                    
                output = subprocess.check_output(cmd, shell=True).decode().strip()
                
                if output:
                    # Extract PIDs from output
                    pids = [pid.strip() for pid in output.split('\n') if pid.strip()]
                    
                    for pid in pids:
                        try:
                            logger.info(f"Killing process with PID {pid}")
                            os.kill(int(pid), signal.SIGTERM)
                        except:
                            logger.error(f"Failed to kill process with PID {pid}, trying SIGKILL")
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                            except Exception as e:
                                logger.error(f"Failed to kill process: {e}")
                    return True
            except Exception as e:
                logger.error(f"Error finding or killing processes: {e}")
                
            # As a fallback, try using killall or pkill
            try:
                logger.info("Trying to kill processes using pkill/killall")
                if sys.platform == 'darwin':  # macOS
                    subprocess.call("pkill -f 'uvicorn main:app'", shell=True)
                else:
                    subprocess.call("killall uvicorn", shell=True)
                return True
            except:
                pass
                
            logger.error("Could not find or kill server process on Unix.")
            return False
            
    except Exception as e:
        logger.error(f"Error stopping server: {e}")
        return False

if __name__ == "__main__":
    if not is_server_running():
        logger.info("Server is not running on port 8000.")
        sys.exit(0)
    
    logger.info("Stopping YouTube Summary backend server...")
    
    if find_and_kill_server():
        # Verify server was stopped
        if not is_server_running():
            logger.info("Server stopped successfully.")
        else:
            logger.warning("Server process killed, but port 8000 is still in use.")
    else:
        logger.error("Failed to stop server automatically.")
        
        # Provide manual instructions
        print("\n" + "=" * 80)
        print("Could not automatically stop the server.")
        print("To manually stop the server, try one of these methods:")
        print("1. Find the terminal running the server and press Ctrl+C")
        print("2. Find the process using port 8000 and kill it manually:")
        if os.name == 'nt':  # Windows
            print("   - Open Task Manager and find the Python process")
            print("   - Or run: netstat -ano | findstr :8000")
            print("     Then: taskkill /F /PID <PID>")
        else:  # Unix/Linux/Mac
            print("   - Run: lsof -i :8000")
            print("     Then: kill <PID>")
        print("=" * 80 + "\n") 
"""
Centralized authentication service for webhook validation.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import Request, HTTPException
from .config_service import ConfigService
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """Centralized authentication service for webhooks."""
    
    @staticmethod
    async def verify_webhook_token(request: Request) -> bool:
        """
        Verify webhook authentication token from request headers.
        
        Args:
            request: FastAPI Request object
            
        Returns:
            bool: True if authentication is valid
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Get the configured auth token
            auth_token = await ConfigService.get_webhook_auth_token()
            
            if not auth_token:
                logger.error("Webhook authentication token not configured")
                raise HTTPException(status_code=500, detail="Webhook authentication not configured")
            
            # Get token from Authorization header
            token = request.headers.get("Authorization")
            if not token:
                logger.warning("No Authorization header provided")
                raise HTTPException(status_code=401, detail="Authorization header required")
            
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Verify token matches
            if token != auth_token:
                logger.warning("Invalid authentication token provided")
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            
            logger.debug("Webhook authentication successful")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(status_code=500, detail="Authentication error")
    
    @staticmethod
    async def get_auth_headers() -> dict:
        """
        Get headers with authentication token for outgoing requests.
        
        Returns:
            dict: Headers with Authorization token
        """
        auth_token = await ConfigService.get_webhook_auth_token()
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

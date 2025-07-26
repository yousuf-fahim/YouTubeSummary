"""
Centralized configuration service for the YouTube Summary Bot.
Provides a single interface for configuration management across all services.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from .supabase_utils import get_config as get_supabase_config, save_config as save_supabase_config
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigService:
    """Centralized configuration management service."""
    
    _cached_config: Optional[Dict[str, Any]] = None
    
    @classmethod
    async def get_config(cls) -> Dict[str, Any]:
        """
        Get configuration with caching.
        Returns the cached config if available, otherwise fetches from Supabase.
        """
        if cls._cached_config is None:
            try:
                cls._cached_config = get_supabase_config()  # This is sync
                logger.info("Configuration loaded from Supabase")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                # Return default config structure
                cls._cached_config = cls._get_default_config()
        
        return cls._cached_config.copy()
    
    @classmethod
    async def save_config(cls, config: Dict[str, Any]) -> bool:
        """
        Save configuration and update cache.
        """
        try:
            success = save_supabase_config(config)  # This is sync
            if success:
                cls._cached_config = config.copy()
                logger.info("Configuration saved successfully")
            return success
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    @classmethod
    def invalidate_cache(cls):
        """Clear the cached configuration to force a fresh load."""
        cls._cached_config = None
        logger.info("Configuration cache invalidated")
    
    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """Return default configuration structure."""
        return {
            "openai_api_key": "",
            "webhooks": {
                "yt_uploads": "",
                "yt_transcripts": "",
                "yt_summaries": "",
                "daily_report": ""
            },
            "prompts": {
                "summary_prompt": "",
                "daily_report_prompt": ""
            },
            "webhook_auth_token": os.urandom(16).hex()
        }
    
    @classmethod
    async def get_webhook_auth_token(cls) -> str:
        """Get the webhook authentication token."""
        config = await cls.get_config()
        return config.get("webhook_auth_token", "")
    
    @classmethod
    async def get_openai_api_key(cls) -> str:
        """Get the OpenAI API key."""
        config = await cls.get_config()
        return config.get("openai_api_key", "")
    
    @classmethod
    async def get_webhooks(cls) -> Dict[str, str]:
        """Get all webhook URLs."""
        config = await cls.get_config()
        return config.get("webhooks", {})

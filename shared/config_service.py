"""
Secure centralized configuration service for the YouTube Summary Bot.
Prioritizes environment variables over database storage for security.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigService:
    """Secure configuration management service - Environment variables first, Supabase fallback."""
    
    def __init__(self):
        self.supabase = None
        try:
            from .supabase_utils import get_client
            self.supabase = get_client()
        except Exception as e:
            logger.warning(f"Could not connect to Supabase for config: {e}")
    
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key from environment variables (most secure)"""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            return api_key
        
        # Fallback to Supabase only if env var not set
        if self.supabase:
            try:
                from .supabase_utils import get_config as get_supabase_config
                config = get_supabase_config()
                if config and config.get('openai_api_key'):
                    logger.warning("Using OpenAI API key from Supabase - consider using environment variable instead")
                    return config['openai_api_key']
            except Exception as e:
                logger.error(f"Could not fetch OpenAI API key from Supabase: {e}")
        
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
    
    def get_discord_webhook(self, webhook_type: str) -> Optional[str]:
        """Get Discord webhook URL from environment variables"""
        env_map = {
            'yt_uploads': 'DISCORD_UPLOADS_WEBHOOK',
            'yt_transcripts': 'DISCORD_TRANSCRIPTS_WEBHOOK', 
            'yt_summaries': 'DISCORD_SUMMARIES_WEBHOOK',
            'daily_report': 'DISCORD_DAILY_REPORT_WEBHOOK'
        }
        
        env_var = env_map.get(webhook_type)
        if env_var:
            webhook_url = os.getenv(env_var)
            if webhook_url:
                return webhook_url
        
        # Fallback to Supabase only if env var not set
        if self.supabase:
            try:
                from .supabase_utils import get_config as get_supabase_config
                config = get_supabase_config()
                if config and config.get('webhooks', {}).get(webhook_type):
                    logger.warning(f"Using Discord webhook {webhook_type} from Supabase - consider using environment variable instead")
                    return config['webhooks'][webhook_type]
            except Exception as e:
                logger.error(f"Could not fetch Discord webhook {webhook_type} from Supabase: {e}")
        
        logger.warning(f"Discord webhook {webhook_type} not found in environment variables or Supabase")
        return None
    
    def get_webhook_auth_token(self) -> str:
        """Get webhook authentication token"""
        token = os.getenv('WEBHOOK_AUTH_TOKEN')
        if token:
            return token
            
        # Fallback to Supabase
        if self.supabase:
            try:
                from .supabase_utils import get_config as get_supabase_config
                config = get_supabase_config()
                if config and config.get('webhook_auth_token'):
                    return config['webhook_auth_token']
            except Exception as e:
                logger.error(f"Could not fetch webhook auth token from Supabase: {e}")
        
        # Generate a secure default for development
        logger.warning("No webhook auth token found. Using generated token for development.")
        return os.urandom(16).hex()
    
    def get_prompt(self, prompt_type: str) -> str:
        """Get AI prompt from environment or return default"""
        # Check for environment variable override
        env_var = f"PROMPT_{prompt_type.upper()}"
        prompt = os.getenv(env_var)
        if prompt:
            return prompt
        
        # Try Supabase
        if self.supabase:
            try:
                from .supabase_utils import get_config as get_supabase_config
                config = get_supabase_config()
                if config and config.get('prompts', {}).get(f'{prompt_type}_prompt'):
                    return config['prompts'][f'{prompt_type}_prompt']
            except Exception as e:
                logger.error(f"Could not fetch prompt {prompt_type} from Supabase: {e}")
        
        # Return hardcoded defaults
        return self._get_default_prompt(prompt_type)
    
    def _get_default_prompt(self, prompt_type: str) -> str:
        """Get default prompts"""
        if prompt_type == 'summary':
            return """You're an advanced content summarizer.
Your task is to analyze the transcript of a YouTube video and return a concise summary in JSON format only.
Include the video's topic, key points, and any noteworthy mentions.
Do not include anything outside of the JSON block. Be accurate, structured, and informative.

Format your response like this:

{
  "title": "Insert video title here",
  "points": [
    "Key point 1",
    "Key point 2", 
    "Key point 3"
  ],
  "summary": "A concise paragraph summarizing the main content",
  "noteworthy_mentions": [
    "Person, project, or tool name if mentioned",
    "Important reference or example"
  ],
  "verdict": "Brief 1-line overall takeaway"
}"""
        
        elif prompt_type == 'daily_report':
            return """You are an expert content analyst creating daily summaries for YouTube videos.
Given a list of video summaries from the last 24 hours, your job is to create a concise, informative daily report.

Include the following sections in your report:
1. **Highlights** - Brief overview of the day's most important videos
2. **Top Videos** - Rate the top 2-3 videos on a scale of 1-10 and explain why they're worth watching
3. **Key Topics** - Identify 3-5 main topics or themes across all videos
4. **Takeaways** - List 3-5 key insights or lessons from today's videos
5. **Recommendations** - Suggest which video(s) viewers should prioritize watching

FORMAT YOUR REPORT:
- Use proper Discord markdown format with headers and bullet points
- Keep paragraphs short for easy reading on mobile
- Make your report engaging and informative
- Write in a neutral, professional tone

The report will be shared in a Discord channel, so format it accordingly using markdown for structure."""
        
        else:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
    
    def store_config_in_supabase(self, key: str, value: str) -> bool:
        """Store configuration value in Supabase (for non-sensitive data only)"""
        if not self.supabase:
            logger.warning("Supabase not available for storing config")
            return False
        
        try:
            from .supabase_utils import save_config as save_supabase_config
            # Only store non-sensitive configuration
            if key in ['openai_api_key', 'webhook_auth_token'] or 'webhook' in key.lower():
                logger.error(f"Attempted to store sensitive data {key} in Supabase. Use environment variables instead!")
                return False
            
            # For now, just log that we would store this
            logger.info(f"Would store non-sensitive config key: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store config in Supabase: {e}")
            return False

# Legacy async wrapper for backward compatibility
class AsyncConfigService:
    """Async wrapper for backward compatibility"""
    
    def __init__(self):
        self.config_service = ConfigService()
    
    async def get_config(self) -> Dict[str, Any]:
        """Get configuration in async context"""
        return {
            "openai_api_key": self.config_service.get_openai_api_key(),
            "webhooks": {
                "yt_uploads": self.config_service.get_discord_webhook('yt_uploads'),
                "yt_transcripts": self.config_service.get_discord_webhook('yt_transcripts'),
                "yt_summaries": self.config_service.get_discord_webhook('yt_summaries'),
                "daily_report": self.config_service.get_discord_webhook('daily_report')
            },
            "webhook_auth_token": self.config_service.get_webhook_auth_token()
        }
    
    async def get_openai_api_key(self) -> str:
        return self.config_service.get_openai_api_key()
    
    async def get_webhooks(self) -> Dict[str, str]:
        return {
            "yt_uploads": self.config_service.get_discord_webhook('yt_uploads'),
            "yt_transcripts": self.config_service.get_discord_webhook('yt_transcripts'),
            "yt_summaries": self.config_service.get_discord_webhook('yt_summaries'),
            "daily_report": self.config_service.get_discord_webhook('daily_report')
        }
    
    async def get_webhook_auth_token(self) -> str:
        return self.config_service.get_webhook_auth_token()

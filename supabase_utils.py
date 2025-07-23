import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from supabase import create_client, Client

# Function to get Supabase client
def get_supabase_client() -> Client:
    """Create and return a Supabase client instance."""
    # Get environment variables or use from config file
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        
        # If environment variables are not set, try loading from config file
        if not supabase_url or not supabase_key:
            config_path = Path("data/config.json")
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)
                    supabase_url = config.get("supabase_url")
                    supabase_key = config.get("supabase_key")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL and key must be provided via environment variables or config file")
        
        # Create Supabase client
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Error creating Supabase client: {e}")
        raise

# Transcript operations
def save_transcript(video_id: str, transcript_text: str, title: str, channel: str) -> Dict:
    """Save transcript to Supabase."""
    try:
        client = get_supabase_client()
        response = client.table("transcripts").insert({
            "video_id": video_id,
            "transcript_text": transcript_text,
            "title": title,
            "channel": channel,
            "created_at": "now()"
        }).execute()
        return response.data[0]
    except Exception as e:
        print(f"Error saving transcript: {e}")
        raise

def get_transcript(video_id: str) -> Optional[Dict]:
    """Get transcript from Supabase by video ID."""
    try:
        client = get_supabase_client()
        response = client.table("transcripts").select("*").eq("video_id", video_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting transcript: {e}")
        return None

# Summary operations
def save_summary(video_id: str, summary_text: str) -> Dict:
    """Save summary to Supabase."""
    try:
        client = get_supabase_client()
        response = client.table("summaries").insert({
            "video_id": video_id,
            "summary_text": summary_text,
            "created_at": "now()"
        }).execute()
        return response.data[0]
    except Exception as e:
        print(f"Error saving summary: {e}")
        raise

def get_summary(video_id: str) -> Optional[Dict]:
    """Get summary from Supabase by video ID."""
    try:
        client = get_supabase_client()
        response = client.table("summaries").select("*").eq("video_id", video_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting summary: {e}")
        return None

def get_all_summaries() -> List[Dict]:
    """Get all summaries from Supabase."""
    try:
        client = get_supabase_client()
        response = client.table("summaries").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error getting all summaries: {e}")
        return []

# Config operations
def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to Supabase."""
    try:
        client = get_supabase_client()
        # First check if config exists
        response = client.table("config").select("*").execute()
        
        if response.data:
            # Update existing config
            client.table("config").update(config).eq("id", response.data[0]["id"]).execute()
        else:
            # Insert new config
            client.table("config").insert(config).execute()
    except Exception as e:
        print(f"Error saving config: {e}")
        raise

def get_config() -> Dict[str, Any]:
    """Get configuration from Supabase."""
    try:
        client = get_supabase_client()
        response = client.table("config").select("*").execute()
        if response.data:
            # Remove id field
            config_data = response.data[0]
            if "id" in config_data:
                del config_data["id"]
            return config_data
        return {}
    except Exception as e:
        print(f"Error getting config: {e}")
        return {} 
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

def get_tracked_channels() -> Dict[str, Any]:
    """Get tracked channels data from Supabase or local storage"""
    try:
        client = get_supabase_client()
        response = client.table("tracked_channels").select("*").execute()
        if response.data:
            # Convert to the expected format
            tracked_channels = []
            last_videos = {}
            for row in response.data:
                # Handle both possible column names for backward compatibility
                channel_name = row.get("channel") or row.get("channel_id")
                if channel_name:
                    tracked_channels.append(channel_name)
                    if row.get("last_video_id"):
                        last_videos[channel_name] = {
                            "id": row["last_video_id"],
                            "title": row.get("last_video_title", ""),
                            "published": row.get("last_video_published", "")
                        }
            return {
                "tracked_channels": tracked_channels,
                "last_videos": last_videos
            }
        return {"tracked_channels": [], "last_videos": {}}
    except Exception as e:
        print(f"Error getting tracked channels from Supabase: {e}")
        # Fall back to local storage
        import json
        import os
        try:
            data_path = os.path.join(os.path.dirname(__file__), "data", "tracked_channels.json")
            if os.path.exists(data_path):
                with open(data_path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"tracked_channels": [], "last_videos": {}}

def save_tracked_channel(channel: str) -> bool:
    """Add a channel to tracking"""
    try:
        client = get_supabase_client()
        # Check if channel already exists (try both column names)
        existing = None
        try:
            existing = client.table("tracked_channels").select("*").eq("channel", channel).execute()
        except:
            # If 'channel' column doesn't exist, try 'channel_id'
            try:
                existing = client.table("tracked_channels").select("*").eq("channel_id", channel).execute()
            except:
                pass
        
        if not existing or not existing.data:
            # Insert new channel (try with 'channel' first, then 'channel_id')
            try:
                client.table("tracked_channels").insert({
                    "channel": channel,
                    "last_video_id": None,
                    "last_video_title": None
                }).execute()
            except:
                # If 'channel' column doesn't exist, try 'channel_id'
                client.table("tracked_channels").insert({
                    "channel_id": channel,
                    "last_video_id": None,
                    "last_video_title": None
                }).execute()
        return True
    except Exception as e:
        print(f"Error saving tracked channel to Supabase: {e}")
        # Fall back to local storage
        import json
        import os
        try:
            data_path = os.path.join(os.path.dirname(__file__), "data", "tracked_channels.json")
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            
            # Load existing data
            tracking_data = {"tracked_channels": [], "last_videos": {}}
            if os.path.exists(data_path):
                with open(data_path, "r") as f:
                    tracking_data = json.load(f)
            
            # Add channel if not already tracked
            if channel not in tracking_data["tracked_channels"]:
                tracking_data["tracked_channels"].append(channel)
                
            # Save back
            with open(data_path, "w") as f:
                json.dump(tracking_data, f, indent=2)
            return True
        except Exception:
            return False

def delete_tracked_channel(channel: str) -> bool:
    """Remove a channel from tracking"""
    try:
        client = get_supabase_client()
        # Try both column names for deletion
        try:
            client.table("tracked_channels").delete().eq("channel", channel).execute()
        except:
            # If 'channel' column doesn't exist, try 'channel_id'
            client.table("tracked_channels").delete().eq("channel_id", channel).execute()
        return True
    except Exception as e:
        print(f"Error deleting tracked channel from Supabase: {e}")
        # Fall back to local storage
        import json
        import os
        try:
            data_path = os.path.join(os.path.dirname(__file__), "data", "tracked_channels.json")
            if os.path.exists(data_path):
                with open(data_path, "r") as f:
                    tracking_data = json.load(f)
                
                # Remove channel
                if channel in tracking_data["tracked_channels"]:
                    tracking_data["tracked_channels"].remove(channel)
                if channel in tracking_data["last_videos"]:
                    del tracking_data["last_videos"][channel]
                
                # Save back
                with open(data_path, "w") as f:
                    json.dump(tracking_data, f, indent=2)
                return True
        except Exception:
            pass
        return False

def update_last_video(channel: str, video_id: str, title: str, published: str) -> bool:
    """Update the last video for a tracked channel"""
    try:
        client = get_supabase_client()
        client.table("tracked_channels").update({
            "last_video_id": video_id,
            "last_video_title": title,
            "last_video_published": published
        }).eq("channel", channel).execute()
        return True
    except Exception as e:
        print(f"Error updating last video in Supabase: {e}")
        # Fall back to local storage
        import json
        import os
        try:
            data_path = os.path.join(os.path.dirname(__file__), "data", "tracked_channels.json")
            tracking_data = {"tracked_channels": [], "last_videos": {}}
            if os.path.exists(data_path):
                with open(data_path, "r") as f:
                    tracking_data = json.load(f)
            
            # Update last video
            tracking_data["last_videos"][channel] = {
                "id": video_id,
                "title": title,
                "published": published
            }
            
            # Save back
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            with open(data_path, "w") as f:
                json.dump(tracking_data, f, indent=2)
            return True
        except Exception:
            return False 
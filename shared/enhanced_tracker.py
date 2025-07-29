"""
Enhanced YouTube Channel Tracker with Latest Video Information
Optimized channel add/remove and tracking features
"""

import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("enhanced_tracker")

class EnhancedYouTubeTracker:
    """Enhanced YouTube channel tracker with optimized video information retrieval"""
    
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.channels_file = os.path.join(self.data_dir, "enhanced_channels.json")
        
    def extract_channel_id(self, channel_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract channel ID and name from various input formats
        Returns: (channel_id, channel_name)
        """
        try:
            channel_input = channel_input.strip()
            
            # Handle direct channel URLs
            if 'youtube.com/' in channel_input:
                # Extract from different URL formats
                patterns = [
                    (r'youtube\.com/@([^/?]+)', 'handle'),  # @username format
                    (r'youtube\.com/channel/([^/?]+)', 'id'),  # channel/ID format
                    (r'youtube\.com/c/([^/?]+)', 'custom'),  # c/name format
                    (r'youtube\.com/user/([^/?]+)', 'user')  # user/name format
                ]
                
                for pattern, type_info in patterns:
                    match = re.search(pattern, channel_input)
                    if match:
                        extracted = match.group(1)
                        if type_info == 'handle':
                            return self._resolve_handle_to_id(f"@{extracted}")
                        elif type_info == 'id':
                            return extracted, self._get_channel_name(extracted)
                        else:
                            return self._resolve_custom_to_id(extracted)
            
            # Handle @username format
            elif channel_input.startswith('@'):
                return self._resolve_handle_to_id(channel_input)
            
            # Handle direct channel ID (UC...)
            elif channel_input.startswith('UC') and len(channel_input) == 24:
                return channel_input, self._get_channel_name(channel_input)
            
            # Assume it's a username and try to resolve
            else:
                return self._resolve_custom_to_id(channel_input)
                
        except Exception as e:
            logger.error(f"Error extracting channel info: {e}")
            return None, None
    
    def _resolve_handle_to_id(self, handle: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve @username to channel ID and name"""
        try:
            # Remove @ if present
            username = handle.replace('@', '')
            
            # Try multiple approaches to resolve handle
            # Approach 1: Try RSS feed with different formats
            possible_feeds = [
                f"https://www.youtube.com/feeds/videos.xml?user={username}",
                f"https://www.youtube.com/@{username}",
            ]
            
            for feed_url in possible_feeds:
                try:
                    if "feeds/videos.xml" in feed_url:
                        response = requests.get(feed_url, timeout=10)
                        if response.status_code == 200:
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(response.content)
                            
                            # Extract channel ID from RSS
                            for elem in root.iter():
                                if 'channelId' in elem.tag or 'channel_id' in elem.tag:
                                    channel_id = elem.text
                                    if channel_id and channel_id.startswith('UC'):
                                        channel_name = self._get_channel_name(channel_id) or f"@{username}"
                                        return channel_id, channel_name
                    else:
                        # Try oEmbed approach
                        return self._resolve_via_oembed(feed_url)
                except Exception as e:
                    logger.debug(f"Failed approach with {feed_url}: {e}")
                    continue
            
            # Approach 2: Try to access channel page and extract ID
            try:
                channel_url = f"https://www.youtube.com/@{username}"
                response = requests.get(channel_url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    # Look for channel ID in the page source
                    import re
                    content = response.text
                    
                    # Try to find channel ID in various formats
                    patterns = [
                        r'"channelId":"(UC[^"]+)"',
                        r'"externalId":"(UC[^"]+)"',
                        r'channel/(UC[^/"]+)',
                        r'"webCommandMetadata":{"url":"/channel/(UC[^"]+)"'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, content)
                        if match:
                            channel_id = match.group(1)
                            if channel_id.startswith('UC') and len(channel_id) == 24:
                                channel_name = self._extract_channel_name_from_page(content) or f"@{username}"
                                return channel_id, channel_name
            except Exception as e:
                logger.debug(f"Failed to extract from page: {e}")
            
            # Approach 3: Try common variations
            variations = [username, username.lower(), username.upper()]
            for variation in variations:
                try:
                    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/@{variation}&format=json"
                    response = requests.get(oembed_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        author_url = data.get('author_url', '')
                        if '/channel/' in author_url:
                            channel_id = author_url.split('/channel/')[-1].split('/')[0]
                            if channel_id.startswith('UC'):
                                return channel_id, data.get('author_name', f"@{username}")
                except Exception as e:
                    logger.debug(f"Failed oembed for {variation}: {e}")
                    continue
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error resolving handle {handle}: {e}")
            return None, None
    
    def _extract_channel_name_from_page(self, content: str) -> Optional[str]:
        """Extract channel name from YouTube page content"""
        try:
            import re
            # Try to find channel name in page title or metadata
            patterns = [
                r'"title":"([^"]+)"',
                r'<title>([^<]+)</title>',
                r'"channelMetadataRenderer":{"title":"([^"]+)"'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    title = match.group(1)
                    if title and not title.startswith('http') and 'YouTube' not in title:
                        return title.strip()
            
            return None
        except Exception as e:
            logger.debug(f"Error extracting channel name: {e}")
            return None
    
    def _resolve_custom_to_id(self, custom_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolve custom channel name to ID"""
        try:
            # Try different URL formats
            possible_urls = [
                f"https://www.youtube.com/c/{custom_name}",
                f"https://www.youtube.com/user/{custom_name}",
                f"https://www.youtube.com/@{custom_name}"
            ]
            
            for url in possible_urls:
                result = self._resolve_via_oembed(url)
                if result[0]:
                    return result
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error resolving custom name {custom_name}: {e}")
            return None, None
    
    def _resolve_via_oembed(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Use oEmbed API to resolve channel info"""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            response = requests.get(oembed_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                author_url = data.get('author_url', '')
                author_name = data.get('author_name', '')
                
                # Extract channel ID from author_url
                if '/channel/' in author_url:
                    channel_id = author_url.split('/channel/')[-1]
                    return channel_id, author_name
            
            return None, None
            
        except Exception as e:
            logger.error(f"Error with oEmbed for {url}: {e}")
            return None, None
    
    def _get_channel_name(self, channel_id: str) -> Optional[str]:
        """Get channel name from channel ID"""
        try:
            # Use RSS feed to get channel name
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            response = requests.get(rss_url, timeout=10)
            
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.content)
                
                # Find channel title in RSS feed
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                
                # Try to find the channel title
                title_elem = root.find('.//atom:title', ns)
                if title_elem is not None and title_elem.text:
                    return title_elem.text.strip()
                
                # Fallback: look for any title element
                for elem in root.iter():
                    if 'title' in elem.tag.lower() and elem.text:
                        title = elem.text.strip()
                        # Skip video titles (they usually contain http or are longer)
                        if not title.startswith('http') and len(title) < 100:
                            return title
            
            # Fallback: try oEmbed with a dummy video URL structure
            try:
                # This might not work for all channels, but worth trying
                oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/channel/{channel_id}&format=json"
                response = requests.get(oembed_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('author_name')
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting channel name for {channel_id}: {e}")
            return None
    
    def get_latest_videos(self, channel_id: str, limit: int = 3) -> List[Dict]:
        """Get latest videos from a channel with enhanced information"""
        try:
            # Use RSS feed for latest videos
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            response = requests.get(rss_url, timeout=10)
            
            if response.status_code != 200:
                return []
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            videos = []
            entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for entry in entries[:limit]:
                try:
                    # Extract basic video info
                    video_id = entry.find('.//{http://www.youtube.com/xml/schemas/2015}videoId').text
                    title = entry.find('.//{http://www.w3.org/2005/Atom}title').text
                    published = entry.find('.//{http://www.w3.org/2005/Atom}published').text
                    
                    # Format publication date
                    pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                    time_ago = self._time_ago(pub_date)
                    
                    # Get additional metadata via oEmbed
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    metadata = self._get_video_metadata(video_url)
                    
                    video_info = {
                        'id': video_id,
                        'title': title,
                        'url': video_url,
                        'published': published,
                        'published_ago': time_ago,
                        'thumbnail': metadata.get('thumbnail_url', ''),
                        'duration': metadata.get('duration', 'Unknown'),
                        'view_count': metadata.get('view_count', 'Unknown')
                    }
                    
                    videos.append(video_info)
                    
                except Exception as e:
                    logger.error(f"Error parsing video entry: {e}")
                    continue
            
            return videos
            
        except Exception as e:
            logger.error(f"Error getting latest videos for {channel_id}: {e}")
            return []
    
    def _get_video_metadata(self, video_url: str) -> Dict:
        """Get additional video metadata via oEmbed"""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
            response = requests.get(oembed_url, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting video metadata: {e}")
            return {}
    
    def _time_ago(self, pub_date: datetime) -> str:
        """Convert datetime to human-readable time ago"""
        now = datetime.now(pub_date.tzinfo)
        diff = now - pub_date
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    
    def load_channels(self) -> Dict:
        """Load tracked channels from storage"""
        try:
            if os.path.exists(self.channels_file):
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"channels": {}, "last_updated": None}
        except Exception as e:
            logger.error(f"Error loading channels: {e}")
            return {"channels": {}, "last_updated": None}
    
    def save_channels(self, data: Dict) -> bool:
        """Save tracked channels to storage"""
        try:
            data["last_updated"] = datetime.now().isoformat()
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving channels: {e}")
            return False
    
    def add_channel(self, channel_input: str) -> Dict:
        """Add a channel to tracking with enhanced validation"""
        try:
            # Extract and validate channel info
            channel_id, channel_name = self.extract_channel_id(channel_input)
            
            if not channel_id:
                return {
                    "success": False,
                    "error": "Could not resolve channel ID from input. Please check the URL or channel name."
                }
            
            # Load current channels
            data = self.load_channels()
            
            # Check if already tracked
            if channel_id in data["channels"]:
                return {
                    "success": False,
                    "error": f"Channel '{channel_name or channel_id}' is already being tracked."
                }
            
            # Get latest videos to verify channel exists and is accessible
            latest_videos = self.get_latest_videos(channel_id, limit=3)
            
            if not latest_videos:
                return {
                    "success": False,
                    "error": "Could not access channel videos. The channel might be private or not exist."
                }
            
            # Add channel to tracking
            data["channels"][channel_id] = {
                "name": channel_name or channel_id,
                "added_date": datetime.now().isoformat(),
                "latest_videos": latest_videos,
                "last_checked": datetime.now().isoformat()
            }
            
            # Save data
            if self.save_channels(data):
                return {
                    "success": True,
                    "message": f"Successfully added '{channel_name or channel_id}' to tracking.",
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "latest_videos": latest_videos
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save channel data."
                }
                
        except Exception as e:
            logger.error(f"Error adding channel {channel_input}: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def remove_channel(self, channel_id: str) -> Dict:
        """Remove a channel from tracking"""
        try:
            data = self.load_channels()
            
            if channel_id not in data["channels"]:
                return {
                    "success": False,
                    "error": "Channel not found in tracking list."
                }
            
            channel_name = data["channels"][channel_id].get("name", channel_id)
            del data["channels"][channel_id]
            
            if self.save_channels(data):
                return {
                    "success": True,
                    "message": f"Successfully removed '{channel_name}' from tracking."
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save changes."
                }
                
        except Exception as e:
            logger.error(f"Error removing channel {channel_id}: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def get_tracked_channels(self) -> Dict:
        """Get all tracked channels with latest video info"""
        try:
            data = self.load_channels()
            return {
                "success": True,
                "channels": data["channels"],
                "count": len(data["channels"]),
                "last_updated": data.get("last_updated")
            }
        except Exception as e:
            logger.error(f"Error getting tracked channels: {e}")
            return {
                "success": False,
                "error": str(e),
                "channels": {},
                "count": 0
            }
    
    def refresh_channel_videos(self, channel_id: str = None) -> Dict:
        """Refresh latest videos for one or all channels"""
        try:
            data = self.load_channels()
            channels_to_update = [channel_id] if channel_id else list(data["channels"].keys())
            updated_count = 0
            
            for cid in channels_to_update:
                if cid in data["channels"]:
                    try:
                        latest_videos = self.get_latest_videos(cid, limit=3)
                        if latest_videos:
                            data["channels"][cid]["latest_videos"] = latest_videos
                            data["channels"][cid]["last_checked"] = datetime.now().isoformat()
                            updated_count += 1
                    except Exception as e:
                        logger.error(f"Error updating channel {cid}: {e}")
            
            if self.save_channels(data):
                return {
                    "success": True,
                    "message": f"Updated {updated_count} channel(s)",
                    "updated_count": updated_count
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save updates"
                }
                
        except Exception as e:
            logger.error(f"Error refreshing channel videos: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
enhanced_tracker = EnhancedYouTubeTracker()

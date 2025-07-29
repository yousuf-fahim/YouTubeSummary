import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("youtube_tracker")

# Import Supabase utilities
try:
    from .supabase_utils import get_tracked_channels, save_tracked_channel, delete_tracked_channel, update_last_video
    HAS_SUPABASE = True
except (ImportError, Exception) as e:
    logger.warning(f"Supabase utils not available, using local storage: {e}")
    HAS_SUPABASE = False

def extract_channel_id(channel_handle_or_id: str) -> Optional[str]:
    """
    Extract channel ID from handle or URL
    
    Args:
        channel_handle_or_id (str): Channel handle (@Username), channel ID, or URL
        
    Returns:
        str: Extracted channel ID or None if extraction failed
    """
    try:
        # Clean up channel ID/handle
        channel_id = channel_handle_or_id
        
        # Handle YouTube URLs
        if 'youtube.com/' in channel_handle_or_id:
            # Try to extract handle or ID from URL
            patterns = [
                r'youtube\.com/(@[^/]+)',  # @Username format
                r'youtube\.com/channel/([^/]+)',  # channel/ID format
                r'youtube\.com/c/([^/]+)'  # c/name format
            ]
            
            for pattern in patterns:
                match = re.search(pattern, channel_handle_or_id)
                if match:
                    channel_id = match.group(1)
                    logger.info(f"Extracted '{channel_id}' from URL")
                    break
        
        # Handle @ format - need to fetch the channel page to get actual ID
        if channel_id.startswith('@'):
            try:
                url = f"https://www.youtube.com/{channel_id}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    # Try to extract channel ID from the page
                    match = re.search(r'channel_id=([^"&]+)', response.text)
                    if match:
                        actual_channel_id = match.group(1)
                        logger.info(f"Found channel ID: {actual_channel_id} for {channel_id}")
                        return actual_channel_id
            except Exception as e:
                logger.error(f"Error getting channel ID from handle: {e}")
                # Continue with the handle, it might work with the RSS feed
        
        return channel_id
    except Exception as e:
        logger.error(f"Error extracting channel ID: {e}")
        return None

def get_latest_videos_from_channel(channel_handle_or_id: str, exclude_shorts: bool = True, exclude_live: bool = True) -> Optional[Dict]:
    """
    Get latest videos from a YouTube channel
    
    Args:
        channel_handle_or_id (str): Channel handle (e.g., '@MrBeast') or ID
        exclude_shorts (bool): Whether to exclude shorts
        exclude_live (bool): Whether to exclude live streams
        
    Returns:
        dict: Latest video info (id, title, etc.) or None if failed
    """
    # First, extract the channel ID if it's a handle
    channel_id = extract_channel_id(channel_handle_or_id)
    if not channel_id:
        logger.error(f"Could not extract channel ID for {channel_handle_or_id}")
        return None
    
    # Try to get videos via RSS feed first (more reliable and more structured)
    video = get_latest_videos_via_rss(channel_handle_or_id)
    
    # Process the video if found
    if video:
        # Check if it's a short and exclude if needed
        is_short = False
        
        # Check for shorts in URL
        if '/shorts/' in video['url'].lower():
            is_short = True
            
        # Check for shorts in title
        if '#shorts' in video['title'].lower() or '#short' in video['title'].lower():
            is_short = True
            
        # Check for shorts in description (if available)
        if video.get('description') and ('#shorts' in video['description'].lower() or '#short' in video['description'].lower()):
            is_short = True
            
        # Try to check video dimensions if available in the RSS feed
        if not is_short:
            try:
                # Use oembed to check video metadata for shorts characteristics
                import requests
                metadata_url = f"https://www.youtube.com/oembed?url={video['url']}&format=json"
                response = requests.get(metadata_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    # Shorts typically have vertical dimensions (height > width)
                    if 'height' in data and 'width' in data and data['height'] > data['width']:
                        is_short = True
            except Exception as e:
                logger.error(f"Error checking video dimensions: {e}")
            
        if exclude_shorts and is_short:
            logger.info(f"Skipping short via RSS: {video['title']} ({video['id']})")
            # Try to get the next non-short video by falling back to HTML scraping
            return get_latest_videos_via_html(channel_handle_or_id, exclude_shorts, exclude_live)
        
        # Check if it's a livestream and exclude if needed
        if exclude_live:
            live_indicators = ['🔴', 'live now', 'live stream', 'streaming now', 'premieres']
            if any(indicator.lower() in video['title'].lower() for indicator in live_indicators):
                logger.info(f"Skipping livestream via RSS: {video['title']} ({video['id']})")
                # Try to get the next non-livestream video by falling back to HTML scraping
                return get_latest_videos_via_html(channel_handle_or_id, exclude_shorts, exclude_live)
        
        return video
    
    # Fall back to HTML scraping if RSS fails
    logger.info(f"RSS feed method failed for {channel_handle_or_id}, falling back to HTML scraping")
    return get_latest_videos_via_html(channel_handle_or_id, exclude_shorts, exclude_live)

def get_latest_videos_via_rss(channel_handle_or_id: str) -> Optional[Dict]:
    """
    Get latest videos from a YouTube channel using RSS feed
    
    Args:
        channel_handle_or_id (str): Channel handle or ID
        
    Returns:
        dict: Latest video info or None if failed
    """
    try:
        # Clean up channel ID/handle from URL if needed
        if 'youtube.com/' in channel_handle_or_id:
            # Extract handle from URL
            match = re.search(r'youtube\.com/(@[^/]+)', channel_handle_or_id)
            if match:
                channel_handle_or_id = match.group(1)
                logger.info(f"Extracted channel handle: {channel_handle_or_id} from URL")
        
        # Clean up channel ID
        channel_id = channel_handle_or_id
        
        # Handle different formats
        if channel_handle_or_id.startswith('@'):
            # Need to get the channel ID first by visiting the channel page
            try:
                # First try to get the channel ID from the @ handle
                url = f"https://www.youtube.com/{channel_handle_or_id}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    # Extract the canonical channel ID
                    match = re.search(r'channel_id=([^"&]+)', response.text)
                    if match:
                        channel_id = match.group(1)
                        logger.info(f"Found channel ID: {channel_id} for {channel_handle_or_id}")
            except Exception as e:
                logger.warning(f"Error getting channel ID from handle: {e}")
        
        # YouTube RSS feed URL
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        logger.info(f"Fetching RSS feed from {rss_url}")
        
        # Request RSS feed
        response = requests.get(rss_url, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch RSS feed: HTTP {response.status_code}")
            return None
            
        # Save the XML for debugging
        debug_path = "data/debug"
        os.makedirs(debug_path, exist_ok=True)
        debug_file = os.path.join(debug_path, f"rss_feed_{int(time.time())}.xml")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        # Parse XML
        try:
            root = ET.fromstring(response.text)
            
            # YouTube RSS uses the Atom format
            # Find the namespace
            namespace = ""
            if '}' in root.tag:
                namespace = root.tag.split('}')[0].strip('{')
                ns = {"atom": namespace}
                
                # Extract channel name
                channel_name_elem = root.find("atom:title", ns)
                channel_name = channel_name_elem.text if channel_name_elem is not None else channel_handle_or_id
                
                # Get the first entry (most recent video)
                entry = root.find("atom:entry", ns)
                if entry is not None:
                    # Find video link
                    link = None
                    for link_elem in entry.findall("atom:link", ns):
                        if link_elem.get("rel") == "alternate":
                            link = link_elem
                            break
                    
                    if link is None or "href" not in link.attrib:
                        logger.error("Could not find video link in RSS entry")
                        return None
                        
                    video_url = link.get("href")
                    video_id = None
                    
                    # Extract video ID from URL
                    if "v=" in video_url:
                        video_id = video_url.split("v=")[1].split("&")[0]
                    elif "/shorts/" in video_url:
                        # Handle YouTube shorts URLs
                        video_id = video_url.split("/shorts/")[1].split("?")[0]
                    else:
                        logger.error(f"Could not extract video ID from URL: {video_url}")
                        return None
                    
                    # Get title
                    title_elem = entry.find("atom:title", ns)
                    title = title_elem.text if title_elem is not None else f"Video from {channel_name}"
                    
                    # Get published date
                    published_elem = entry.find("atom:published", ns)
                    published = published_elem.text if published_elem is not None else "Recent"
                    
                    logger.info(f"Found video via RSS: {title} ({video_id})")
                    
                    return {
                        'id': video_id,
                        'title': title,
                        'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                        'channel_name': channel_name,
                        'publish_time': published,
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    }
                else:
                    logger.warning("No entries found in RSS feed")
                    return None
            else:
                logger.error("Could not determine XML namespace")
                return None
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to get videos via RSS: {e}")
        return None

def get_latest_videos_via_html(channel_handle_or_id: str, exclude_shorts: bool = True, exclude_live: bool = True) -> Optional[Dict]:
    """
    Get latest videos from a YouTube channel by scraping HTML
    
    Args:
        channel_handle_or_id (str): Channel handle (e.g., '@MrBeast') or ID
        exclude_shorts (bool): Whether to exclude shorts
        exclude_live (bool): Whether to exclude live streams
        
    Returns:
        dict: Latest video info (id, title, etc.) or None if failed
    """
    try:
        # Handle different channel formats
        if channel_handle_or_id.startswith('@'):
            # @Username format
            channel_url = f"https://www.youtube.com/{channel_handle_or_id}/videos"
        elif channel_handle_or_id.startswith('channel/'):
            # channel/ID format
            channel_url = f"https://www.youtube.com/{channel_handle_or_id}/videos"
        elif channel_handle_or_id.startswith('c/'):
            # c/custom_name format
            channel_url = f"https://www.youtube.com/{channel_handle_or_id}/videos"
        elif 'youtube.com/' in channel_handle_or_id:
            # Full URL - keep as is if it already contains /videos, otherwise add it
            if '/videos' in channel_handle_or_id:
                channel_url = channel_handle_or_id
            else:
                channel_url = f"{channel_handle_or_id.rstrip('/')}/videos"
        else:
            # Assume it's a channel ID
            channel_url = f"https://www.youtube.com/channel/{channel_handle_or_id}/videos"
        
        logger.info(f"Fetching videos from {channel_url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Try using a simpler approach - direct HTML parsing
        response = requests.get(channel_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch channel: HTTP {response.status_code}")
            return None
            
        # Save the HTML for debugging if needed
        debug_path = "data/debug"
        os.makedirs(debug_path, exist_ok=True)
        debug_file = os.path.join(debug_path, f"channel_page_raw_{int(time.time())}.html")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract channel name
        channel_name = channel_handle_or_id
        try:
            # Try to find the channel name in various elements
            meta_name = soup.find('meta', property='og:title')
            if meta_name:
                channel_name = meta_name.get('content', '').replace(' - YouTube', '')
        except Exception as e:
            logger.warning(f"Couldn't extract channel name: {e}")
        
        # New simplified approach: Look for video links directly in the HTML
        videos = []
        video_items = soup.select('a#video-title-link, a#video-title')
        
        if not video_items:
            video_items = soup.select('a.yt-simple-endpoint.style-scope.ytd-grid-video-renderer')
        
        if not video_items:
            # Try to find any links that might be videos
            logger.warning("Couldn't find standard video elements, trying alternate method")
            video_items = [a for a in soup.find_all('a') if 'watch?v=' in a.get('href', '')]
        
        logger.info(f"Found {len(video_items)} potential video items")
        
        for item in video_items:
            try:
                href = item.get('href', '')
                if 'watch?v=' not in href:
                    continue
                
                # Extract video ID
                video_id = href.split('watch?v=')[1].split('&')[0]
                
                # Extract title
                title = item.get('title', '')
                if not title and item.text:
                    title = item.text.strip()
                
                # Skip shorts if requested
                if exclude_shorts and ('/shorts/' in href or 'shorts' in title.lower()):
                    logger.info(f"Skipping short: {title}")
                    continue
                    
                # Skip livestreams if requested (harder to detect without API)
                if exclude_live and ('live' in title.lower() or 'streaming' in title.lower()):
                    logger.info(f"Skipping possible livestream: {title}")
                    continue
                
                # Get thumbnail
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                
                # Get publish time (harder without API, might be unavailable)
                publish_time = "Recent"
                
                videos.append({
                    'id': video_id,
                    'title': title,
                    'thumbnail': thumbnail,
                    'channel_name': channel_name,
                    'publish_time': publish_time,
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                })
            except Exception as e:
                logger.error(f"Error parsing video item: {e}")
        
        # Return the latest video (first in the list)
        if videos:
            logger.info(f"Found {len(videos)} videos, latest: {videos[0]['title']} ({videos[0]['id']})")
            return videos[0]
        else:
            logger.warning(f"No videos found for channel {channel_handle_or_id}")
            
            # As a last resort, try to find any video link on the page
            try:
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '')
                    if 'watch?v=' in href:
                        video_id = href.split('watch?v=')[1].split('&')[0]
                        logger.info(f"Found fallback video: {video_id}")
                        return {
                            'id': video_id,
                            'title': f"Video from {channel_name}",
                            'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                            'channel_name': channel_name,
                            'publish_time': 'Unknown',
                            'url': f"https://www.youtube.com/watch?v={video_id}"
                        }
            except Exception as e:
                logger.error(f"Error in fallback video search: {e}")
                
            return None
            
    except Exception as e:
        logger.error(f"Failed to get videos from {channel_handle_or_id} via HTML: {e}")
        return None

def process_new_video(video_info: Dict, process_func) -> bool:
    """
    Process a newly found video
    
    Args:
        video_info (Dict): Video information dictionary
        process_func: Function to call to process the video
        
    Returns:
        bool: True if processed successfully, False otherwise
    """
    try:
        video_id = video_info['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        channel_name = video_info['channel_name']
        
        # Create notification message in the format expected by the processor
        # Format matches exactly: "MrBeast just posted a new video! youtu.be/pzBi1nwDn8U"
        notification = f"{channel_name} just posted a new video!\nyoutu.be/{video_id}"
        
        # Call the process function
        logger.info(f"Processing new video: {video_info['title']} ({video_id})")
        
        try:
            result = process_func(notification)
            if result:
                logger.info(f"Successfully processed video {video_id}")
                return True
            else:
                logger.error(f"Process function returned False for video {video_id}")
                return False
        except Exception as e:
            logger.error(f"Exception in process function for video {video_id}: {e}")
            return False
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return False

def load_tracking_data() -> Dict:
    """
    Load tracked channels and last videos from Supabase or JSON file
    
    Returns:
        Dict: Dictionary containing tracking data
    """
    # Try to load from Supabase first if available
    if HAS_SUPABASE:
        try:
            tracking_data = get_tracked_channels()
            if tracking_data:
                logger.info(f"Loaded {len(tracking_data.get('tracked_channels', []))} channels from Supabase")
                return tracking_data
        except Exception as e:
            logger.error(f"Error loading tracked channels from Supabase: {e}")
    
    # Fall back to local JSON file if Supabase failed or not available
    tracking_file = Path("data/tracked_channels.json")
    
    if not tracking_file.exists():
        return {
            "tracked_channels": [],
            "last_videos": {}
        }
        
    try:
        with open(tracking_file, "r") as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data.get('tracked_channels', []))} channels from local file")
            return data
    except Exception as e:
        logger.error(f"Failed to load tracking data from file: {e}")
        return {
            "tracked_channels": [],
            "last_videos": {}
        }

def save_tracking_data(data: Dict) -> bool:
    """
    Save tracked channels and last videos to Supabase or JSON file
    
    Args:
        data (Dict): Dictionary containing tracking data
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    # Try to save to Supabase first if available
    if HAS_SUPABASE:
        try:
            # Get current channels from Supabase
            current_data = get_tracked_channels()
            current_channels = set(current_data.get("tracked_channels", []))
            new_channels = set(data.get("tracked_channels", []))
            
            # Channels to add
            for channel in new_channels - current_channels:
                save_tracked_channel(channel)
            
            # Channels to remove
            for channel in current_channels - new_channels:
                delete_tracked_channel(channel)
            
            # Update last videos
            for channel, video_id in data.get("last_videos", {}).items():
                if channel in new_channels:
                    update_last_video(channel, video_id)
            
            logger.info(f"Saved {len(new_channels)} channels to Supabase")
            return True
        except Exception as e:
            logger.error(f"Error saving tracked channels to Supabase: {e}")
    
    # Fall back to local JSON file if Supabase failed or not available
    tracking_file = Path("data/tracked_channels.json")
    
    # Ensure directory exists
    os.makedirs(tracking_file.parent, exist_ok=True)
    
    try:
        with open(tracking_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data.get('tracked_channels', []))} channels to local file")
        return True
    except Exception as e:
        logger.error(f"Failed to save tracking data to file: {e}")
        return False

def check_tracked_channels(process_func):
    """
    Check all tracked channels for new videos and process them
    
    Args:
        process_func: Function to call to process new videos
        
    Returns:
        int: Number of new videos processed
    """
    logger.info("Checking tracked channels for new videos...")
    tracking_data = load_tracking_data()
    tracked_channels = tracking_data.get("tracked_channels", [])
    last_videos = tracking_data.get("last_videos", {})
    
    if not tracked_channels:
        logger.info("No channels are being tracked")
        return 0
        
    logger.info(f"Found {len(tracked_channels)} tracked channels to check")
    
    new_videos_count = 0
    
    for channel in tracked_channels:
        try:
            logger.info(f"Checking channel: {channel}")
            latest = get_latest_videos_from_channel(channel)
            
            if not latest:
                logger.warning(f"No latest video found for {channel}")
                continue
                
            video_id = latest['id']
            video_title = latest.get('title', 'Unknown title')
            
            logger.info(f"Latest video for {channel}: {video_id} - {video_title}")
            
            # Check if this is a new video
            if channel in last_videos and last_videos[channel] == video_id:
                logger.info(f"No new videos for {channel}, latest remains {video_id}")
                continue
                
            logger.info(f"New video detected from {channel}: {latest['title']} ({video_id})")
            
            # Process the video
            logger.info(f"Processing video: {video_id}")
            if process_new_video(latest, process_func):
                # Update the last video ID only if processing succeeded
                last_videos[channel] = video_id
                new_videos_count += 1
                
                # Save after each successful processing to prevent duplicates
                tracking_data["last_videos"] = last_videos
                success = save_tracking_data(tracking_data)
                logger.info(f"Saved tracking data: {'Success' if success else 'Failed'}")
            else:
                logger.error(f"Failed to process video {video_id} for channel {channel}")
            
        except Exception as e:
            logger.error(f"Error checking {channel}: {e}")
    
    logger.info(f"Channel check complete. Processed {new_videos_count} new videos.")
    return new_videos_count 


class YouTubeTracker:
    """Class to manage YouTube channel tracking and monitoring."""
    
    def __init__(self):
        """Initialize the YouTubeTracker."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("YouTubeTracker initialized")
    
    def add_channel(self, channel_id: str, channel_name: str) -> bool:
        """Add a channel to tracking.
        
        Args:
            channel_id (str): YouTube channel ID or handle
            channel_name (str): Display name for the channel
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            tracking_data = load_tracking_data()
            tracked_channels = tracking_data.get("tracked_channels", [])
            
            if channel_id not in tracked_channels:
                tracked_channels.append(channel_id)
                tracking_data["tracked_channels"] = tracked_channels
                
                success = save_tracking_data(tracking_data)
                if success:
                    self.logger.info(f"Added channel {channel_name} ({channel_id}) to tracking")
                    return True
                else:
                    self.logger.error(f"Failed to save tracking data for channel {channel_id}")
                    return False
            else:
                self.logger.info(f"Channel {channel_id} is already being tracked")
                return True
                
        except Exception as e:
            self.logger.error(f"Error adding channel {channel_id}: {e}")
            return False
    
    def remove_channel(self, channel_id: str) -> bool:
        """Remove a channel from tracking.
        
        Args:
            channel_id (str): YouTube channel ID or handle to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        try:
            tracking_data = load_tracking_data()
            tracked_channels = tracking_data.get("tracked_channels", [])
            last_videos = tracking_data.get("last_videos", {})
            
            if channel_id in tracked_channels:
                tracked_channels.remove(channel_id)
                tracking_data["tracked_channels"] = tracked_channels
                
                # Also remove from last_videos
                if channel_id in last_videos:
                    del last_videos[channel_id]
                    tracking_data["last_videos"] = last_videos
                
                success = save_tracking_data(tracking_data)
                if success:
                    self.logger.info(f"Removed channel {channel_id} from tracking")
                    return True
                else:
                    self.logger.error(f"Failed to save tracking data after removing channel {channel_id}")
                    return False
            else:
                self.logger.warning(f"Channel {channel_id} was not being tracked")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing channel {channel_id}: {e}")
            return False
    
    def get_tracked_channels(self) -> Dict:
        """Get all tracked channels.
        
        Returns:
            Dict: Dictionary with channel IDs as keys and channel info as values
        """
        try:
            tracking_data = load_tracking_data()
            tracked_channels = tracking_data.get("tracked_channels", [])
            
            # Convert list to dict format expected by main.py
            channels_dict = {}
            for channel_id in tracked_channels:
                channels_dict[channel_id] = {
                    "name": channel_id,  # Use channel_id as name for now
                    "id": channel_id
                }
            
            return channels_dict
            
        except Exception as e:
            self.logger.error(f"Error getting tracked channels: {e}")
            return {}
    
    async def check_for_new_videos(self, channel_id: str) -> List[Dict]:
        """Check for new videos from a specific channel.
        
        Args:
            channel_id (str): YouTube channel ID or handle
            
        Returns:
            List[Dict]: List of new videos found
        """
        try:
            tracking_data = load_tracking_data()
            last_videos = tracking_data.get("last_videos", {})
            
            # Get latest video from channel
            latest_video = get_latest_videos_from_channel(channel_id)
            
            if not latest_video:
                self.logger.warning(f"No videos found for channel {channel_id}")
                return []
            
            video_id = latest_video['id']
            
            # Check if this is a new video
            if channel_id in last_videos and last_videos[channel_id] == video_id:
                self.logger.info(f"No new videos for {channel_id}")
                return []
            
            # Update last video ID
            last_videos[channel_id] = video_id
            tracking_data["last_videos"] = last_videos
            save_tracking_data(tracking_data)
            
            self.logger.info(f"Found new video from {channel_id}: {latest_video['title']}")
            return [latest_video]
            
        except Exception as e:
            self.logger.error(f"Error checking for new videos from {channel_id}: {e}")
            return []
    
    async def get_latest_video_info(self, channel_id: str) -> Optional[Dict]:
        """Get the latest video information from a channel.
        
        Args:
            channel_id (str): YouTube channel ID or handle
            
        Returns:
            Optional[Dict]: Latest video info or None if not found
        """
        try:
            # Extract the real channel ID from handle if needed
            real_channel_id = extract_channel_id(channel_id)
            if not real_channel_id:
                self.logger.error(f"Failed to extract channel ID from {channel_id}")
                return None
            
            # Get RSS feed URL
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={real_channel_id}"
            
            self.logger.info(f"Fetching latest video from {channel_id} (ID: {real_channel_id})")
            
            # Fetch RSS feed
            response = requests.get(rss_url, timeout=10)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Extract namespace
            namespace = {'atom': 'http://www.w3.org/2005/Atom', 
                        'yt': 'http://www.youtube.com/xml/schemas/2015',
                        'media': 'http://search.yahoo.com/mrss/'}
            
            # Find the first (latest) video entry
            entry = root.find('.//atom:entry', namespace)
            if entry is None:
                self.logger.warning(f"No video entries found for channel {channel_id}")
                return None
            
            # Extract video information
            video_id = entry.find('.//yt:videoId', namespace).text
            title = entry.find('.//atom:title', namespace).text
            published = entry.find('.//atom:published', namespace).text
            author = entry.find('.//atom:author/atom:name', namespace).text
            
            # Get video URL
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            video_info = {
                'id': video_id,
                'title': title,
                'url': video_url,
                'published': published,
                'author': author,
                'channel_id': real_channel_id
            }
            
            self.logger.info(f"Latest video from {channel_id}: {title}")
            return video_info
            
        except Exception as e:
            self.logger.error(f"Error getting latest video from {channel_id}: {e}")
            return None
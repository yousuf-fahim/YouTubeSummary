"""
Enhanced Channel Tracking UI Components
Optimized interface for channel add/remove and video display
"""

import streamlit as st
import requests
from datetime import datetime
import json
import os

def display_enhanced_channel_tracking():
    """Enhanced channel tracking interface with latest video info"""
    
    st.header("📺 Enhanced Channel Tracking")
    st.markdown("Monitor YouTube channels and get the latest video information automatically.")
    
    # Add refresh button and auto-refresh toggle
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh All", help="Update latest videos for all channels"):
            refresh_all_channels()
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=False, help="Automatically refresh every 30 seconds")
    
    with col3:
        if auto_refresh:
            st.rerun()
    
    # Channel stats
    channels_data = get_enhanced_channels_data()
    if channels_data.get("success"):
        channels = channels_data.get("channels", {})
        
        # Display stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Tracked Channels", len(channels))
        with col2:
            total_videos = sum(len(ch.get("latest_videos", [])) for ch in channels.values())
            st.metric("🎥 Latest Videos", total_videos)
        with col3:
            last_updated = channels_data.get("last_updated")
            if last_updated:
                try:
                    update_time = datetime.fromisoformat(last_updated)
                    st.metric("⏰ Last Updated", update_time.strftime("%H:%M:%S"))
                except:
                    st.metric("⏰ Last Updated", "Unknown")
        
        st.markdown("---")
        
        # Enhanced channel display
        if channels:
            display_enhanced_channels(channels)
        else:
            st.info("📭 No channels currently tracked. Add your first channel below!")
    else:
        st.error(f"❌ Error loading channels: {channels_data.get('error', 'Unknown error')}")
    
    st.markdown("---")
    
    # Enhanced add channel section
    display_enhanced_add_channel()

def display_enhanced_channels(channels):
    """Display channels with enhanced video information"""
    
    # Search and filter
    search_term = st.text_input("🔍 Search channels", placeholder="Search by channel name...")
    
    # Filter channels based on search
    if search_term:
        filtered_channels = {
            cid: data for cid, data in channels.items()
            if search_term.lower() in data.get("name", "").lower()
        }
    else:
        filtered_channels = channels
    
    if not filtered_channels:
        st.warning("No channels match your search.")
        return
    
    # Pagination
    channels_per_page = 5
    if 'enhanced_page' not in st.session_state:
        st.session_state.enhanced_page = 0
    
    channel_items = list(filtered_channels.items())
    total_pages = (len(channel_items) - 1) // channels_per_page + 1
    start_idx = st.session_state.enhanced_page * channels_per_page
    end_idx = start_idx + channels_per_page
    current_items = channel_items[start_idx:end_idx]
    
    # Pagination controls
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Previous", disabled=st.session_state.enhanced_page == 0):
                st.session_state.enhanced_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"<div style='text-align: center;'>Page {st.session_state.enhanced_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Next ➡️", disabled=st.session_state.enhanced_page >= total_pages - 1):
                st.session_state.enhanced_page += 1
                st.rerun()
    
    # Display channels
    for channel_id, channel_data in current_items:
        display_enhanced_channel_card(channel_id, channel_data)

def display_enhanced_channel_card(channel_id, channel_data):
    """Display an enhanced channel card with video information"""
    
    channel_name = channel_data.get("name", channel_id)
    latest_videos = channel_data.get("latest_videos", [])
    last_checked = channel_data.get("last_checked")
    
    with st.container():
        # Channel header
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"### 📺 {channel_name}")
            if last_checked:
                try:
                    check_time = datetime.fromisoformat(last_checked)
                    st.caption(f"Last checked: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    st.caption("Last checked: Unknown")
        
        with col2:
            col_refresh, col_remove = st.columns(2)
            with col_refresh:
                if st.button("🔄", key=f"refresh_{channel_id}", help="Refresh this channel"):
                    refresh_single_channel(channel_id)
            with col_remove:
                if st.button("🗑️", key=f"remove_{channel_id}", help="Remove channel"):
                    remove_enhanced_channel(channel_id, channel_name)
        
        # Latest videos
        if latest_videos:
            st.markdown("**Latest Videos:**")
            
            for i, video in enumerate(latest_videos[:3]):  # Show max 3 videos
                with st.expander(f"🎥 {video.get('title', 'Unknown Title')}", expanded=i==0):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Title:** {video.get('title', 'Unknown')}")
                        st.markdown(f"**Published:** {video.get('published_ago', 'Unknown time ago')}")
                        if video.get('duration'):
                            st.markdown(f"**Duration:** {video.get('duration')}")
                        if video.get('view_count'):
                            st.markdown(f"**Views:** {video.get('view_count')}")
                    
                    with col2:
                        if video.get('thumbnail'):
                            st.image(video['thumbnail'], width=150)
                        
                        video_url = video.get('url')
                        if video_url:
                            st.markdown(f"[🔗 Watch Video]({video_url})")
                            if st.button("📄 Summarize", key=f"summarize_{video.get('id')}"):
                                summarize_video(video_url, video.get('title'))
        else:
            st.info("📭 No recent videos found")
        
        st.markdown("---")

def display_enhanced_add_channel():
    """Enhanced add channel interface with validation"""
    
    st.subheader("➕ Add New Channel")
    st.markdown("Enter a YouTube channel URL, @username, or channel ID")
    
    with st.form("enhanced_add_channel", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            channel_input = st.text_input(
                "Channel Information:",
                placeholder="https://youtube.com/@channelname, @username, or UC...",
                help="Supported formats:\n• https://youtube.com/@username\n• https://youtube.com/channel/UC...\n• @username\n• Channel ID starting with UC"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            submitted = st.form_submit_button("Add Channel", type="primary", use_container_width=True)
        
        if submitted and channel_input:
            add_enhanced_channel(channel_input)

def get_enhanced_channels_data():
    """Get channels data from enhanced tracker"""
    try:
        # Try backend first
        backend_url = get_backend_url()
        if backend_url:
            response = requests.get(f"{backend_url}/enhanced/channels", timeout=10)
            if response.status_code == 200:
                return response.json()
        
        # Fallback to local enhanced tracker
        from shared.enhanced_tracker import enhanced_tracker
        return enhanced_tracker.get_tracked_channels()
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def add_enhanced_channel(channel_input):
    """Add channel using enhanced tracker"""
    with st.spinner("🔍 Validating and adding channel..."):
        try:
            # Try backend first
            backend_url = get_backend_url()
            if backend_url:
                response = requests.post(f"{backend_url}/enhanced/channels/add", 
                                       json={"channel_input": channel_input}, 
                                       timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    handle_add_result(result)
                    return
            
            # Fallback to local enhanced tracker
            from shared.enhanced_tracker import enhanced_tracker
            result = enhanced_tracker.add_channel(channel_input)
            handle_add_result(result)
            
        except Exception as e:
            st.error(f"❌ Error adding channel: {str(e)}")

def remove_enhanced_channel(channel_id, channel_name):
    """Remove channel using enhanced tracker"""
    if st.session_state.get(f"confirm_remove_{channel_id}"):
        with st.spinner(f"Removing {channel_name}..."):
            try:
                # Try backend first
                backend_url = get_backend_url()
                if backend_url:
                    response = requests.delete(f"{backend_url}/enhanced/channels/{channel_id}", timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        handle_remove_result(result, channel_name)
                        return
                
                # Fallback to local enhanced tracker
                from shared.enhanced_tracker import enhanced_tracker
                result = enhanced_tracker.remove_channel(channel_id)
                handle_remove_result(result, channel_name)
                
            except Exception as e:
                st.error(f"❌ Error removing channel: {str(e)}")
        
        # Reset confirmation
        del st.session_state[f"confirm_remove_{channel_id}"]
    else:
        st.warning(f"⚠️ Are you sure you want to remove '{channel_name}'?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Remove", key=f"confirm_yes_{channel_id}"):
                st.session_state[f"confirm_remove_{channel_id}"] = True
                st.rerun()
        with col2:
            if st.button("Cancel", key=f"confirm_no_{channel_id}"):
                pass  # Do nothing

def refresh_single_channel(channel_id):
    """Refresh videos for a single channel"""
    with st.spinner("Refreshing channel videos..."):
        try:
            # Try backend first
            backend_url = get_backend_url()
            if backend_url:
                response = requests.post(f"{backend_url}/enhanced/channels/{channel_id}/refresh", timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        st.success("✅ Channel refreshed successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('error', 'Refresh failed')}")
                    return
            
            # Fallback to local enhanced tracker
            from shared.enhanced_tracker import enhanced_tracker
            result = enhanced_tracker.refresh_channel_videos(channel_id)
            
            if result.get("success"):
                st.success("✅ Channel refreshed successfully!")
                st.rerun()
            else:
                st.error(f"❌ {result.get('error', 'Refresh failed')}")
                
        except Exception as e:
            st.error(f"❌ Error refreshing channel: {str(e)}")

def refresh_all_channels():
    """Refresh videos for all channels"""
    with st.spinner("Refreshing all channels..."):
        try:
            # Try backend first
            backend_url = get_backend_url()
            if backend_url:
                response = requests.post(f"{backend_url}/enhanced/channels/refresh", timeout=60)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        st.success(f"✅ Updated {result.get('updated_count', 0)} channels!")
                        st.rerun()
                    else:
                        st.error(f"❌ {result.get('error', 'Refresh failed')}")
                    return
            
            # Fallback to local enhanced tracker
            from shared.enhanced_tracker import enhanced_tracker
            result = enhanced_tracker.refresh_channel_videos()
            
            if result.get("success"):
                st.success(f"✅ Updated {result.get('updated_count', 0)} channels!")
                st.rerun()
            else:
                st.error(f"❌ {result.get('error', 'Refresh failed')}")
                
        except Exception as e:
            st.error(f"❌ Error refreshing channels: {str(e)}")

def summarize_video(video_url, video_title):
    """Summarize a video using the existing processing pipeline"""
    with st.spinner(f"Summarizing: {video_title}..."):
        try:
            # Use existing video processing function
            from local_functions import test_video_processing
            result = test_video_processing(video_url)
            
            if result and result.get("success"):
                st.success("✅ Video summarized successfully!")
                # You could display the summary here or redirect to the process tab
            else:
                st.error(f"❌ Summarization failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            st.error(f"❌ Error summarizing video: {str(e)}")

def handle_add_result(result):
    """Handle the result of adding a channel"""
    if result.get("success"):
        st.success(f"✅ {result.get('message', 'Channel added successfully!')}")
        
        # Show preview of latest videos
        latest_videos = result.get("latest_videos", [])
        if latest_videos:
            st.markdown("**Latest videos from this channel:**")
            for video in latest_videos[:2]:  # Show first 2 videos
                st.markdown(f"• 🎥 {video.get('title', 'Unknown title')} ({video.get('published_ago', 'Unknown time')})")
        
        st.rerun()
    else:
        st.error(f"❌ {result.get('error', 'Failed to add channel')}")

def handle_remove_result(result, channel_name):
    """Handle the result of removing a channel"""
    if result.get("success"):
        st.success(f"✅ Successfully removed '{channel_name}'")
        st.rerun()
    else:
        st.error(f"❌ {result.get('error', 'Failed to remove channel')}")

def get_backend_url():
    """Get backend URL"""
    return os.getenv("BACKEND_URL", "https://yt-bot-backend-8302f5ba3275.herokuapp.com")

import aiohttp
import json
import asyncio
import os
import io
import ssl
from datetime import datetime

# Create a context that doesn't verify certificates (for development only)
# In production, you should use proper certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def send_discord_message(webhook_url, content=None, title=None, description=None, fields=None, color=None, thumbnail=None):
    """
    Send a message to a Discord webhook
    
    Args:
        webhook_url (str): Discord webhook URL
        content (str, optional): Message content
        title (str, optional): Embed title
        description (str, optional): Embed description
        fields (list, optional): List of field dicts with name and value
        color (int, optional): Embed color (decimal, not hex)
        thumbnail (str, optional): URL for the thumbnail image
    """
    if not webhook_url:
        print("No webhook URL provided")
        return False
    
    # Create the payload
    payload = {}
    
    if content:
        payload["content"] = content
    
    # Create embed if any embed data is provided
    if title or description or fields or color or thumbnail:
        embed = {}
        
        if title:
            embed["title"] = title
            
        if description:
            embed["description"] = description
            
        if fields:
            embed["fields"] = []
            for field in fields:
                # Format the field value to ensure it fits within Discord's limits
                value = field.get("value", "")
                if isinstance(value, str) and len(value) > 1024:
                    value = value[:1021] + "..."
                
                embed_field = {
                    "name": field.get("name", "Field"),
                    "value": value
                }
                
                # Add inline property if specified
                if "inline" in field:
                    embed_field["inline"] = field["inline"]
                    
                embed["fields"].append(embed_field)
        
        # Add thumbnail if provided
        if thumbnail:
            embed["thumbnail"] = {"url": thumbnail}
                
        if color:
            embed["color"] = color
        else:
            # Default color (blue)
            embed["color"] = 3447003
            
        # Add timestamp
        embed["timestamp"] = datetime.utcnow().isoformat()
        
        payload["embeds"] = [embed]
    
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                webhook_url,
                json=payload
            ) as response:
                if response.status == 204:
                    print(f"Message sent successfully to Discord webhook")
                    return True
                else:
                    error_text = await response.text()
                    print(f"Discord API error: {response.status}")
                    print(f"Error details: {error_text}")
                    return False
    except Exception as e:
        print(f"Error sending Discord message: {e}")
        return False

async def send_file_to_discord(webhook_url, file_content, filename, content=None):
    """
    Send a file to a Discord webhook
    
    Args:
        webhook_url (str): Discord webhook URL
        file_content (str): Content of the file to send
        filename (str): Name of the file
        content (str, optional): Message content to send with the file
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not webhook_url:
        print("No webhook URL provided")
        return False
    
    try:
        # Convert the file content to bytes if it's not already
        if isinstance(file_content, str):
            file_content_bytes = file_content.encode('utf-8')
        else:
            file_content_bytes = file_content
        
        # Create form data
        form_data = aiohttp.FormData()
        
        # Add the message content if provided
        payload = {}
        if content:
            payload["content"] = content
        
        # Add the payload as part of the form data
        form_data.add_field('payload_json', json.dumps(payload))
        
        # Add the file
        form_data.add_field('file', 
                            io.BytesIO(file_content_bytes),
                            filename=filename,
                            content_type='text/plain')
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(webhook_url, data=form_data) as response:
                if response.status in (200, 204):
                    print(f"File {filename} sent successfully to Discord")
                    return True
                else:
                    error_text = await response.text()
                    print(f"Discord API error: {response.status}")
                    print(f"Error details: {error_text}")
                    return False
    except Exception as e:
        print(f"Error sending file to Discord: {e}")
        return False 
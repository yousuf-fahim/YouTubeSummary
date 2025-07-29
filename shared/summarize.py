import json
import asyncio
import aiohttp
import ssl
import time
import re
import os
from .supabase_utils import get_config as get_supabase_config, get_summary as get_supabase_summary, save_summary as save_supabase_summary

# Create a context that doesn't verify certificates (for development only)
# In production, you should use proper certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Default prompt templates that can be overridden by configuration
DEFAULT_SUMMARY_PROMPT = """You're an advanced content summarizer.
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

DEFAULT_DAILY_REPORT_PROMPT = """You are an expert content analyst creating daily summaries for YouTube videos.
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

def load_config():
    """Load configuration from Supabase"""
    try:
        supabase_config = get_supabase_config()
        if supabase_config:
            return supabase_config
    except Exception:
        pass
    return {}

def get_summary_prompt():
    """Get the summary prompt from config or use default"""
    config = load_config()
    return config.get("prompts", {}).get("summary_prompt", DEFAULT_SUMMARY_PROMPT)

def get_daily_report_prompt():
    """Get the daily report prompt from config or use default"""
    config = load_config()
    return config.get("prompts", {}).get("daily_report_prompt", DEFAULT_DAILY_REPORT_PROMPT)

async def chunk_and_summarize(transcript, api_key, video_id=None):
    """
    Break a long transcript into chunks and summarize each chunk,
    then combine the summaries into a single coherent summary.
    
    Args:
        transcript (str): The full transcript text
        api_key (str): OpenAI API key
        video_id (str, optional): YouTube video ID for saving to Supabase
        
    Returns:
        dict: Combined summary with title, points and summary text
    """
    # Check if summary exists in Supabase if video_id is provided
    if video_id:
        existing_summary = get_supabase_summary(video_id)
        if existing_summary:
            print(f"Summary found in Supabase for video ID: {video_id}")
            # Format the summary properly for the application
            summary_data = {
                "title": existing_summary.get("title", "Video Summary"),
                "points": existing_summary.get("points", []),
                "summary": existing_summary.get("summary_text", ""),
                "noteworthy_mentions": existing_summary.get("noteworthy_mentions", []),
                "verdict": existing_summary.get("verdict", "")
            }
            return summary_data
    
    # Define chunk size and overlap
    chunk_size = 8000
    overlap = 500
    
    # If transcript is short enough, just summarize it directly
    if len(transcript) <= chunk_size:
        summary = await generate_summary(transcript, api_key)
        
        # Save to Supabase if video_id is provided and summary was generated
        if video_id and summary:
            save_supabase_summary(video_id, summary.get("summary", ""))
            
        return summary
    
    print(f"Transcript too long ({len(transcript)} chars), breaking into chunks")
    
    # Break transcript into chunks
    chunks = []
    start = 0
    while start < len(transcript):
        end = min(start + chunk_size, len(transcript))
        
        # Try to find a good break point (end of sentence)
        if end < len(transcript):
            # Look for a period, question mark, or exclamation point followed by space or newline
            search_start = max(end - overlap, 0)
            search_text = transcript[search_start:end]
            break_matches = list(re.finditer(r'[.!?][\s\n]', search_text))
            
            if break_matches:
                # Use the last sentence break
                last_match = break_matches[-1]
                end = search_start + last_match.end()
        
        # Get the chunk and append to list
        chunk = transcript[start:end]
        chunks.append(chunk)
        
        # Move start position (with overlap if not at the end)
        if end == len(transcript):
            break
            
        start = max(0, end - overlap)
    
    print(f"Split transcript into {len(chunks)} chunks")
    
    # Process each chunk
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}")
        
        # Define functions for section summary
        section_functions = [
            {
                "name": "create_section_summary",
                "description": "Create a summary for a section of a transcript",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section_title": {
                            "type": "string",
                            "description": "A descriptive title for this section of the transcript"
                        },
                        "key_points": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Key points from this section (3-5 points)"
                        },
                        "section_summary": {
                            "type": "string",
                            "description": "A concise paragraph summarizing this section"
                        }
                    },
                    "required": ["section_title", "key_points", "section_summary"]
                }
            }
        ]
        
        summary = await generate_summary_with_functions(
            chunk, 
            api_key,
            f"You are summarizing part {i+1} of {len(chunks)} of a longer transcript.",
            section_functions,
            "create_section_summary"
        )
        
        if summary:
            chunk_summaries.append(summary)
    
    # If we couldn't generate any summaries, return a fallback
    if not chunk_summaries:
        return fallback_summary()
        
    # Combine the chunk summaries
    combined_summary_prompt = json.dumps({
        "sections": chunk_summaries
    }, indent=2)
    
    print("Generating final combined summary")
    
    # Get the custom prompt from config
    summary_prompt = get_summary_prompt()
    system_message = summary_prompt
    
    # Define functions for final summary - customized to match our format expectations
    final_functions = [
        {
            "name": "create_final_summary",
            "description": "Create a final summary from multiple section summaries",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Overall title for the video based on all sections"
                    },
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "The most important key points from across all sections"
                    },
                    "summary": {
                        "type": "string", 
                        "description": "A concise paragraph summarizing the entire content"
                    },
                    "noteworthy_mentions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "People, projects, tools, or important references mentioned"
                    },
                    "verdict": {
                        "type": "string",
                        "description": "Brief 1-line overall takeaway from the video"
                    }
                },
                "required": ["title", "points", "summary", "verdict"]
            }
        }
    ]
    
    # Generate final summary from the chunk summaries
    final_summary = await generate_summary_with_functions(
        combined_summary_prompt,
        api_key,
        system_message,
        final_functions,
        "create_final_summary"
    )
    
    if final_summary:
        # Save to Supabase if video_id is provided
        if video_id:
            save_supabase_summary(video_id, final_summary.get("summary", ""))
        return final_summary
    
    # If combination fails, create a summary from the individual chunks
    title = chunk_summaries[0].get("section_title", "Video Summary") if chunk_summaries else "Video Summary"
    
    # Collect all points and choose the most important ones
    all_points = []
    for chunk in chunk_summaries:
        all_points.extend(chunk.get("key_points", []))
    
    # Take the first 5 points or create generic ones if none exist
    points = all_points[:5] if all_points else ["No specific points could be extracted from the transcript"]
    
    # Combine the summary texts
    combined_text = " ".join([chunk.get("section_summary", "") for chunk in chunk_summaries])
    
    summary_result = {
        "title": title,
        "points": points,
        "summary": combined_text[:500] + "..." if len(combined_text) > 500 else combined_text,
        "noteworthy_mentions": [],
        "verdict": "Summary generation partially succeeded."
    }
    
    # Save to Supabase if video_id is provided
    if video_id:
        save_supabase_summary(video_id, summary_result.get("summary", ""))
    
    return summary_result

def fallback_summary():
    """Return a fallback summary when generation fails"""
    return {
        "title": "Video Summary (Generated)",
        "points": [
            "The AI model could not generate specific points from this video",
            "The transcript was processed but summary generation failed",
            "Check the console logs for more information about the error",
            "You can try again with a shorter video",
            "Or check your OpenAI API key and quota"
        ],
        "summary": "The AI model was unable to generate a proper summary of this video. This could be due to issues with the transcript length, the API key configuration, or rate limits.",
        "noteworthy_mentions": [],
        "verdict": "Summary generation failed."
    }

async def generate_summary_with_functions(transcript, api_key, system_message, functions, function_name):
    """
    Generate a summary using OpenAI's function calling to ensure structured output
    
    Args:
        transcript (str): The transcript text
        api_key (str): OpenAI API key
        system_message (str): System message for the model
        functions (list): List of function definitions
        function_name (str): Name of function to call
        
    Returns:
        dict: Structured summary
    """
    if not api_key or not transcript or len(transcript) < 50:
        return None
        
    # Limit transcript length
    max_transcript_length = 10000
    if len(transcript) > max_transcript_length:
        print(f"Truncating transcript from {len(transcript)} to {max_transcript_length} characters")
        transcript = transcript[:max_transcript_length] + "..."
    
    # Call OpenAI API with retry logic
    print("Calling OpenAI API for summary generation with function calling...")
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                payload = {
                    "model": "gpt-3.5-turbo-0125",  # Model with function calling support
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": transcript}
                    ],
                    "functions": functions,
                    "function_call": {"name": function_name},
                    "temperature": 0.3
                }
                
                print(f"Request to OpenAI API: model={payload['model']}, function={function_name}")
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                ) as response:
                    response_text = await response.text()
                    print(f"OpenAI API response status: {response.status}")
                    
                    if response.status == 200:
                        result = json.loads(response_text)
                        try:
                            # Extract function call arguments
                            function_call = result["choices"][0]["message"]["function_call"]
                            if function_call and function_call["name"] == function_name:
                                function_args = json.loads(function_call["arguments"])
                                print(f"Successfully called function: {function_name}")
                                return function_args
                            else:
                                print(f"Expected function {function_name} was not called")
                        except (KeyError, json.JSONDecodeError) as e:
                            print(f"Failed to parse function call: {e}")
                    elif response.status == 429:  # Rate limit error
                        print(f"Rate limit reached. Retrying after delay. Attempt {attempt+1}/{max_retries}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                            continue
                    else:
                        print(f"OpenAI API error: {response.status}")
                        print(f"Error body: {response_text}")
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying... Attempt {attempt+1}/{max_retries}")
                await asyncio.sleep(retry_delay)
                continue
        
        break
    
    return None

async def generate_summary(transcript, api_key, system_prompt=None):
    """
    Generate a summary using the regular OpenAI chat completion API.
    This is a fallback for the function calling approach.
    
    Args:
        transcript (str): The transcript text
        api_key (str): OpenAI API key
        system_prompt (str, optional): Custom system prompt
        
    Returns:
        dict: Summary with title, points, and summary text
    """
    # Get custom prompt from config
    if not system_prompt:
        system_prompt = get_summary_prompt()
    
    # Define functions for summary creation - updated to match our new format
    functions = [
        {
            "name": "create_summary",
            "description": "Create a summary of a transcript",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the video inferred from transcript"
                    },
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Key points that represent the most important information"
                    },
                    "summary": {
                        "type": "string",
                        "description": "A concise paragraph summarizing the main content"
                    },
                    "noteworthy_mentions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "People, projects, tools, or important references mentioned"
                    },
                    "verdict": {
                        "type": "string",
                        "description": "Brief 1-line overall takeaway from the video"
                    }
                },
                "required": ["title", "points", "summary", "verdict"]
            }
        }
    ]
    
    return await generate_summary_with_functions(transcript, api_key, system_prompt, functions, "create_summary")

async def generate_daily_report(summaries, api_key):
    """
    Generate a daily report from a list of video summaries.
    
    Args:
        summaries (list): List of video summaries
        api_key (str): OpenAI API key
        
    Returns:
        str: The daily report text
    """
    if not summaries:
        print("No summaries provided for daily report")
        return "No new videos summarized today."
    
    # Ensure summaries is a list
    if summaries is None:
        print("Summaries is None, returning default message")
        return "No new videos summarized today."
    
    if not api_key:
        print("OpenAI API key not provided for daily report")
        return "Unable to generate report: OpenAI API key not provided."
    
    # Create the input for the report
    print(f"Generating daily report for {len(summaries)} summaries")
    print(f"Debug: summaries data = {summaries}")
    summaries_text = []
    for i, summary in enumerate(summaries, 1):
        title = summary.get("title", f"Video {i}")
        points = summary.get("points", [])
        # Ensure points is iterable
        if points is None:
            points = []
        points_text = "\n".join([f"- {point}" for point in points])
        summary_text = summary.get("summary", "No summary available")
        url = summary.get("url", "")
        verdict = summary.get("verdict", "")
        noteworthy_mentions_list = summary.get("noteworthy_mentions", [])
        # Ensure noteworthy_mentions is iterable
        if noteworthy_mentions_list is None:
            noteworthy_mentions_list = []
        noteworthy_mentions = ", ".join(noteworthy_mentions_list)
        
        entry = f"Video: {title}\nURL: {url}\n"
        if verdict:
            entry += f"Verdict: {verdict}\n"
        entry += f"Key Points:\n{points_text}\n"
        if noteworthy_mentions:
            entry += f"Noteworthy Mentions: {noteworthy_mentions}\n"
        entry += f"Summary: {summary_text}\n"
        
        summaries_text.append(entry)
    
    all_summaries = "\n---\n".join(summaries_text)
    
    # Define functions for report generation
    functions = [
        {
            "name": "create_daily_report",
            "description": "Create a daily report from video summaries",
            "parameters": {
                "type": "object",
                "properties": {
                    "report": {
                        "type": "string",
                        "description": "A comprehensive daily report covering all videos"
                    }
                },
                "required": ["report"]
            }
        }
    ]
    
    # Get custom daily report prompt
    daily_report_prompt = get_daily_report_prompt()
    
    # Generate the report using function calling
    print("Calling OpenAI API for daily report generation...")
    report_data = await generate_summary_with_functions(
        all_summaries,
        api_key,
        daily_report_prompt,
        functions,
        "create_daily_report"
    )
    
    if report_data and isinstance(report_data, dict) and "report" in report_data:
        # Format the report for Discord with proper line breaks and formatting
        report = report_data["report"]
        
        # Format sections with better Discord markdown
        # Replace section headers with bold formatting
        report = re.sub(r'^(#+)\s+(.+)$', r'**\2**', report, flags=re.MULTILINE)
        
        # Add emojis to common section names for visual appeal
        report = report.replace("**Summary**", "**📋 Summary**")
        report = report.replace("**Top Videos**", "**🏆 Top Videos**")
        report = report.replace("**Trending Topics**", "**📈 Trending Topics**")
        report = report.replace("**Key Takeaways**", "**💡 Key Takeaways**")
        report = report.replace("**Recommendations**", "**👍 Recommendations**")
        
        # Ensure proper spacing between sections
        report = re.sub(r'\n{3,}', '\n\n', report)
        
        # Make sure bullet points use Discord-friendly format
        report = re.sub(r'^[-*]\s+', '• ', report, flags=re.MULTILINE)
        
        # Format any links for better visibility
        report = re.sub(r'(?<!\[)(https?://\S+)(?!\))', r'<\1>', report)
        
        return report
    
    return "Failed to generate daily report. Please check the logs for details." 


# Wrapper functions for backward compatibility with main.py
async def summarize_content(transcript: str, title: str = "Unknown Title", url: str = "") -> str:
    """Wrapper function to summarize video content.
    
    Args:
        transcript (str): Video transcript text
        title (str): Video title
        url (str): Video URL
        
    Returns:
        str: Generated summary or None if failed
    """
    try:
        # Get OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("No OpenAI API key found")
            return None
        
        # Generate summary using existing function
        summary = await generate_summary(transcript, api_key)
        
        if summary:
            # Try to parse JSON and format for Discord
            try:
                summary_data = json.loads(summary)
                
                # Format for Discord
                formatted_summary = f"**📹 {summary_data.get('title', title)}**\n\n"
                formatted_summary += f"**Summary:** {summary_data.get('summary', 'No summary available')}\n\n"
                
                if summary_data.get('points'):
                    formatted_summary += "**Key Points:**\n"
                    for point in summary_data['points']:
                        formatted_summary += f"• {point}\n"
                    formatted_summary += "\n"
                
                if summary_data.get('noteworthy_mentions'):
                    formatted_summary += "**Notable Mentions:**\n"
                    for mention in summary_data['noteworthy_mentions']:
                        formatted_summary += f"• {mention}\n"
                    formatted_summary += "\n"
                
                if summary_data.get('verdict'):
                    formatted_summary += f"**Verdict:** {summary_data['verdict']}\n\n"
                
                if url:
                    formatted_summary += f"**🔗 Watch:** {url}"
                
                return formatted_summary
                
            except json.JSONDecodeError:
                # If not JSON, return the raw summary
                return f"**📹 {title}**\n\n{summary}\n\n**🔗 Watch:** {url}" if url else f"**📹 {title}**\n\n{summary}"
        
        return None
        
    except Exception as e:
        print(f"Error in summarize_content: {e}")
        return None


async def generate_daily_report_wrapper(summaries: list) -> str:
    """Wrapper function to generate daily report from summaries.
    
    Args:
        summaries (list): List of summary data from database
        
    Returns:
        str: Generated daily report
    """
    try:
        # Get OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("No OpenAI API key found")
            return "Daily report generation failed: No OpenAI API key configured"
        
        # Use existing function
        return await generate_daily_report(summaries, api_key)
        
    except Exception as e:
        print(f"Error in generate_daily_report wrapper: {e}")
        return "Daily report generation failed due to an error"
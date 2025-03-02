"""Utility functions for narrative generation."""
import re
import json
from typing import List, Dict, Any, Tuple, Optional, Set
import aiofiles
import os
import logging
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_json_string(json_string: str) -> str:
    """Clean a JSON string from extra characters to ensure valid parsing.
    
    Args:
        json_string: The potentially malformed JSON string
        
    Returns:
        A cleaned JSON string
    """
    # Extract JSON content if it's wrapped in ```json ... ``` or similar
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_string)
    if json_match:
        json_string = json_match.group(1)
    
    # Remove any trailing commas in arrays or objects
    json_string = re.sub(r',\s*}', '}', json_string)
    json_string = re.sub(r',\s*]', ']', json_string)
    
    return json_string

def extract_keywords(text: str, max_keywords: int = 20) -> List[str]:
    """Extract important keywords from a text.
    
    Args:
        text: The text to extract keywords from
        max_keywords: Maximum number of keywords to extract
        
    Returns:
        List of keywords
    """
    # Simple implementation - split by spaces and take unique words
    words = text.lower().split()
    # Remove common stop words, punctuation, and short words
    stop_words = {"the", "a", "an", "and", "in", "on", "at", "to", "for", "with", 
                  "of", "by", "as", "is", "are", "was", "were", "be", "been", "being"}
    
    keywords = []
    for word in words:
        # Clean the word of punctuation
        word = re.sub(r'[^\w\s]', '', word)
        if (word and len(word) > 2 and word not in stop_words and 
            not word.isdigit() and word not in keywords):
            keywords.append(word)
    
    # Return at most max_keywords
    return keywords[:max_keywords]

async def save_debug_info(batch_id: str, data: Any, debug_dir: str = "debug_output") -> None:
    """Save debug information to a file.
    
    Args:
        batch_id: Identifier for the batch
        data: Data to save (will be converted to JSON)
        debug_dir: Directory to save debug files
    """
    try:
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{debug_dir}/{batch_id}_{timestamp}.json"
        
        async with aiofiles.open(filename, "w") as f:
            if isinstance(data, str):
                await f.write(data)
            else:
                await f.write(json.dumps(data, indent=2))
        logger.info(f"Debug info saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save debug info: {e}")

def format_date_for_prompt(date_str: Optional[str]) -> str:
    """Format a date string for inclusion in a prompt.
    
    Args:
        date_str: Date string in format YYYY-MM-DD or timestamp
        
    Returns:
        Formatted date string or empty string if input is None
    """
    if not date_str:
        return ""
    
    try:
        # Handle potential float timestamp values
        if isinstance(date_str, (int, float)):
            try:
                date_obj = datetime.fromtimestamp(date_str)
                return date_obj.strftime("%B %d, %Y")
            except (ValueError, TypeError, OverflowError):
                # If we can't parse as timestamp, continue to string parsing
                pass
        
        # Parse as string in format YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d, %Y")
    except (ValueError, TypeError):
        # If date is invalid, return the original string
        if isinstance(date_str, (int, float)):
            return str(date_str)
        return date_str 
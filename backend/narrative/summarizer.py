"""Summarization functions for narrative generation."""
from typing import List, Dict, Any, Optional
import json
import logging

from .openai_client import OpenAIClient
from .utils import clean_json_string, extract_keywords

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NarrativeSummarizer:
    """Handles the summarization of photo batches and meta-summarization."""
    
    def __init__(self, openai_client: OpenAIClient):
        """Initialize the summarizer.
        
        Args:
            openai_client: OpenAIClient instance for API calls
        """
        self.openai_client = openai_client
    
    async def summarize_batch(
        self, 
        batch_photos: List[Dict[str, Any]], 
        model: str,
        include_meta_summary: bool = True
    ) -> Dict[str, Any]:
        """Generate a summary for a batch of photos.
        
        Args:
            batch_photos: List of photo objects with metadata
            model: The OpenAI model to use
            include_meta_summary: Whether to include meta-summary
            
        Returns:
            Dictionary with batch summary information
        """
        logger.info(f"Summarizing batch of {len(batch_photos)} photos")
        
        # Prepare the prompt for the summarization
        messages = self._prepare_batch_summary_prompt(batch_photos)
        
        # Make the API call
        response = await self.openai_client.call_with_retry(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=1000
        )
        
        # Process the response
        summary_text = response.choices[0].message.content
        cleaned_json = clean_json_string(summary_text)
        
        try:
            summary_data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch summary JSON: {e}")
            logger.error(f"Received content: {summary_text}")
            # Return a minimal valid structure if parsing fails
            summary_data = {
                "summary": "Failed to generate summary due to an error.",
                "topics": [],
                "people": [],
                "locations": []
            }
        
        # Extract keywords from the summary for better consolidation
        keywords = extract_keywords(summary_data.get("summary", ""))
        summary_data["keywords"] = keywords
        
        # Add meta-summary if requested
        if include_meta_summary and len(batch_photos) > 1:
            meta_summary = await self._generate_meta_summary(summary_data, model)
            summary_data["meta_summary"] = meta_summary
        
        return summary_data
    
    async def consolidate_summaries(
        self, 
        batch_summaries: List[Dict[str, Any]], 
        model: str
    ) -> Dict[str, Any]:
        """Generate a consolidated narrative from multiple batch summaries.
        
        Args:
            batch_summaries: List of batch summary dictionaries
            model: The OpenAI model to use
            
        Returns:
            Dictionary with consolidated narrative
        """
        logger.info(f"Consolidating {len(batch_summaries)} batch summaries")
        
        # Prepare the prompt for consolidation
        messages = self._prepare_consolidation_prompt(batch_summaries)
        
        # Make the API call
        response = await self.openai_client.call_with_retry(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=2000
        )
        
        # Process the response
        narrative_text = response.choices[0].message.content
        cleaned_json = clean_json_string(narrative_text)
        
        try:
            narrative_data = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse consolidated narrative JSON: {e}")
            logger.error(f"Received content: {narrative_text}")
            # Return a minimal valid structure if parsing fails
            narrative_data = {
                "title": "Photo Collection",
                "narrative": "This is a collection of photos.",
                "themes": [],
                "timeline": []
            }
        
        return narrative_data
    
    async def _generate_meta_summary(
        self, 
        batch_summary: Dict[str, Any], 
        model: str
    ) -> str:
        """Generate a meta-summary for a batch summary.
        
        Args:
            batch_summary: Batch summary dictionary
            model: The OpenAI model to use
            
        Returns:
            Meta-summary string
        """
        # Prepare the prompt for meta-summary
        messages = [
            {"role": "system", "content": "You are an expert at distilling information into concise summaries."},
            {"role": "user", "content": f"""Given the following summary information about a set of photos, 
             create a very concise 1-2 sentence description capturing the essence of this batch:
             
             {json.dumps(batch_summary, indent=2)}
             
             Respond with just the meta-summary text, no JSON formatting."""}
        ]
        
        # Make the API call
        response = await self.openai_client.call_with_retry(
            model=model,
            messages=messages,
            response_format={"type": "text"},
            max_completion_tokens=100
        )
        
        # Return the meta-summary text
        return response.choices[0].message.content.strip()
    
    def _prepare_batch_summary_prompt(self, batch_photos: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Prepare the prompt for batch summarization.
        
        Args:
            batch_photos: List of photo objects with metadata
            
        Returns:
            List of message objects for the API call
        """
        # Create a formatted string of all photo descriptions in the batch
        photo_descriptions = []
        
        for i, photo in enumerate(batch_photos):
            caption = photo.get("caption", "")
            date = photo.get("date", "")
            location = photo.get("location", "")
            
            description = f"Photo {i+1}:"
            if caption:
                description += f" Caption: {caption}."
            if date:
                description += f" Date: {date}."
            if location:
                description += f" Location: {location}."
                
            photo_descriptions.append(description)
        
        photos_text = "\n".join(photo_descriptions)
        
        # Create the messages array
        messages = [
            {"role": "system", "content": """You are an AI expert at analyzing photo collections and creating meaningful summaries.
             Given a set of photos with captions and metadata, create a cohesive summary that captures the key themes,
             people, and locations."""},
            {"role": "user", "content": f"""Analyze the following set of photos and create a JSON summary:

             {photos_text}
             
             Please provide a JSON response with the following structure:
             {{
                 "summary": "A paragraph summarizing the contents and meaning of these photos",
                 "topics": ["topic1", "topic2"],
                 "people": ["person1", "person2"],
                 "locations": ["location1", "location2"]
             }}
             """}
        ]
        
        return messages
    
    def _prepare_consolidation_prompt(self, batch_summaries: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Prepare the prompt for consolidating batch summaries.
        
        Args:
            batch_summaries: List of batch summary dictionaries
            
        Returns:
            List of message objects for the API call
        """
        # Format the batch summaries
        summaries_text = []
        
        for i, summary in enumerate(batch_summaries):
            summary_text = f"Batch {i+1} Summary:\n"
            summary_text += f"Summary: {summary.get('summary', '')}\n"
            
            if "topics" in summary and summary["topics"]:
                summary_text += f"Topics: {', '.join(summary['topics'])}\n"
            
            if "people" in summary and summary["people"]:
                summary_text += f"People: {', '.join(summary['people'])}\n"
                
            if "locations" in summary and summary["locations"]:
                summary_text += f"Locations: {', '.join(summary['locations'])}\n"
                
            if "meta_summary" in summary and summary["meta_summary"]:
                summary_text += f"Meta-Summary: {summary['meta_summary']}\n"
                
            summaries_text.append(summary_text)
        
        all_summaries = "\n\n".join(summaries_text)
        
        # Create the messages array
        messages = [
            {"role": "system", "content": """You are an AI expert at creating cohesive narratives from collections of photos.
             Given summaries of multiple batches of photos, create a consolidated narrative that tells a story."""},
            {"role": "user", "content": f"""Based on the following batch summaries, create a consolidated narrative:

             {all_summaries}
             
             Please provide a JSON response with the following structure:
             {{
                 "title": "An evocative title for the entire collection",
                 "narrative": "A cohesive narrative that tells the story of these photos",
                 "themes": ["theme1", "theme2"],
                 "timeline": [
                     {{ "period": "description of time period", "events": ["event1", "event2"] }}
                 ]
             }}
             """}
        ]
        
        return messages 
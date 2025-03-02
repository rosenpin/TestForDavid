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
        include_meta_summary: bool = True,
        batch_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a summary for a batch of photos.
        
        Args:
            batch_photos: List of photo objects with metadata
            model: The OpenAI model to use
            include_meta_summary: Whether to include meta-summary
            batch_context: Optional context about how the batch was created
            
        Returns:
            Dictionary with batch summary information, or None if summary generation fails
        """
        logger.info(f"Summarizing batch of {len(batch_photos)} photos")
        
        # Extract batch theme if available (for semantic batches)
        batch_theme = self._detect_batch_theme(batch_photos)
        
        # Prepare the prompt for the summarization
        messages = self._prepare_batch_summary_prompt(batch_photos, batch_theme)
        
        try:
            # Make the API call
            response = await self.openai_client.call_with_retry(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=2000
            )
            
            # Process the response
            summary_text = response.choices[0].message.content
            cleaned_json = clean_json_string(summary_text)
            
            summary_data = json.loads(cleaned_json)
            
            # Validate that we have a proper summary
            if summary_data.get("summary") == "Failed to generate summary due to an error.":
                logger.error("Summary generation failed with default error message")
                return None
            
            # Extract keywords from the summary for better consolidation
            keywords = extract_keywords(summary_data.get("summary", ""))
            summary_data["keywords"] = keywords
            
            # If we detected a theme, include it in the summary
            if batch_theme:
                summary_data["detected_theme"] = batch_theme
            
            # Add meta-summary if requested
            if include_meta_summary and len(batch_photos) > 1:
                meta_summary = await self._generate_meta_summary(summary_data, model)
                summary_data["meta_summary"] = meta_summary
            
            return summary_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch summary JSON: {e}")
            logger.error(f"Received content: {summary_text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during summary generation: {str(e)}")
            return None
    
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
            max_completion_tokens=4000
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
    
    def _detect_batch_theme(self, batch_photos: List[Dict[str, Any]]) -> Optional[str]:
        """Detect the theme of a batch based on metadata without AI calls.
        
        Args:
            batch_photos: List of photo objects with metadata
            
        Returns:
            Detected theme or None if no clear theme
        """
        # Check if all photos share the same location
        locations = set()
        for photo in batch_photos:
            location = photo.get("location", {})
            if location and isinstance(location, dict):
                if location.get("city"):
                    locations.add(location.get("city"))
                elif location.get("country"):
                    locations.add(location.get("country"))
                elif location.get("formatted"):
                    locations.add(location.get("formatted"))
        
        if len(locations) == 1:
            location = next(iter(locations))
            return f"Location: {location}"
            
        # Check time proximity
        if len(batch_photos) > 1:
            timestamps = []
            for photo in batch_photos:
                timestamp = photo.get("timestamp")
                if timestamp:
                    try:
                        timestamps.append(float(timestamp))
                    except (ValueError, TypeError):
                        pass
            
            if timestamps and max(timestamps) - min(timestamps) < 24 * 60 * 60:
                return "Event: Single day event"
            
        # Look for common keywords in descriptions
        common_themes = {
            "vacation": 0, "holiday": 0, "travel": 0, "trip": 0,
            "wedding": 0, "celebration": 0, "party": 0, "birthday": 0,
            "family": 0, "friends": 0, "beach": 0, "mountain": 0, 
            "city": 0, "food": 0, "dinner": 0, "lunch": 0
        }
        
        total_photos = len(batch_photos)
        for photo in batch_photos:
            description = photo.get("description", "").lower()
            for theme in common_themes:
                if theme in description:
                    common_themes[theme] += 1
        
        # Find themes that appear in at least 30% of photos
        threshold = total_photos * 0.3
        dominant_themes = [theme for theme, count in common_themes.items() 
                           if count >= threshold]
        
        if dominant_themes:
            return f"Theme: {', '.join(dominant_themes)}"
        
        return None
    
    def _prepare_batch_summary_prompt(
        self, 
        batch_photos: List[Dict[str, Any]],
        batch_theme: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Prepare the prompt for batch summarization.
        
        Args:
            batch_photos: List of photo objects with metadata
            batch_theme: Detected theme of the batch, if any
            
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
        
        # Create theme context if available
        theme_context = ""
        if batch_theme:
            theme_context = f"\nThese photos appear to be related by: {batch_theme}."
        
        # Create the messages array
        messages = [
            {"role": "system", "content": """You are an AI expert at analyzing photo collections and creating meaningful summaries.
             Given a set of photos with captions and metadata, create a cohesive summary that captures the key themes,
             people, and locations."""},
            {"role": "user", "content": f"""Analyze the following set of photos and create a JSON summary:{theme_context}

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
    
    def _prepare_consolidation_prompt(
        self, 
        batch_summaries: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Prepare the prompt for consolidating batch summaries.
        
        Args:
            batch_summaries: List of batch summary dictionaries
            
        Returns:
            List of message objects for the API call
        """
        # Format the batch summaries
        summaries_text = []
        
        # Extract the main theme if available from the first summary
        theme = None
        for summary in batch_summaries:
            if "detected_theme" in summary:
                theme = summary["detected_theme"]
                break
        
        theme_instruction = ""
        if theme:
            # Extract the theme category and value
            theme_parts = theme.split(": ", 1)
            if len(theme_parts) > 1:
                theme_category = theme_parts[0].lower()
                theme_value = theme_parts[1]
                theme_instruction = f"These summaries all relate to the {theme_category} '{theme_value}'. "
            else:
                theme_instruction = f"These summaries all relate to {theme}. "
        
        for i, summary in enumerate(batch_summaries):
            summary_text = f"Batch {i+1} Summary:\n"
            
            # Add detected theme if available
            if "detected_theme" in summary:
                summary_text += f"Theme: {summary['detected_theme']}\n"
                
            summary_text += f"Summary: {summary.get('summary', '')}\n"
            
            if "topics" in summary and summary["topics"]:
                summary_text += f"Topics: {', '.join(summary['topics'])}\n"
            
            if "people" in summary and summary["people"]:
                summary_text += f"People: {', '.join(summary['people'])}\n"
                
            if "locations" in summary and summary["locations"]:
                summary_text += f"Locations: {', '.join(summary['locations'])}\n"
                
            if "meta_summary" in summary and summary["meta_summary"]:
                summary_text += f"Meta-Summary: {summary['meta_summary']}\n"
                
            if "date_range" in summary:
                date_range = summary["date_range"]
                summary_text += f"Date Range: {date_range.get('start', '')} to {date_range.get('end', '')}\n"
                
            summaries_text.append(summary_text)
        
        all_summaries = "\n\n".join(summaries_text)
        
        # Create the messages array
        messages = [
            {"role": "system", "content": """You are an AI expert at creating cohesive narratives from collections of photos.
             Given summaries of multiple batches of photos, create a consolidated narrative that tells a story."""},
            {"role": "user", "content": f"""Based on the following batch summaries, create a focused, themed narrative:

             {theme_instruction}Focus on creating a cohesive narrative that highlights the connections between these 
             specific photos rather than attempting to create an all-encompassing story.
             
             {all_summaries}
             
             Please provide a JSON response with the following structure:
             {{
                 "title": "An evocative title for this themed collection",
                 "narrative": "A cohesive narrative that tells the story of these specific photos",
                 "themes": ["theme1", "theme2"],
                 "timeline": [
                     {{ "period": "description of time period", "events": ["event1", "event2"] }}
                 ]
             }}
             """}
        ]
        
        return messages 
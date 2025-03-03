"""Main narrative generator module for photo collections."""
from typing import List, Dict, Any, Optional
import logging
import asyncio
import time
import json
from datetime import datetime
from openai import AsyncOpenAI
from collections import defaultdict
import traceback

from .openai_client import OpenAIClient
from .batch_processor import BatchProcessor
from .summarizer import NarrativeSummarizer
from .utils import save_debug_info, format_date_for_prompt

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NarrativeGenerator:
    """Main class for generating narratives from photo collections."""
    
    def __init__(
        self, 
        api_key: str,
        model: str = "o1",
        batch_size: int = 100,
        max_concurrent_batches: int = 5,
        debug_mode: bool = False
    ):
        """Initialize the narrative generator.
        
        Args:
            api_key: OpenAI API key
            model: The OpenAI model to use (default: "o1")
            batch_size: Number of photos per batch
            max_concurrent_batches: Maximum number of concurrent batch processing tasks
            debug_mode: Whether to save debug information
        """
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.debug_mode = debug_mode
        
        # Initialize the OpenAI client
        openai_client = AsyncOpenAI(api_key=api_key)
        self.client = OpenAIClient(openai_client)
        
        # Initialize components
        self.summarizer = NarrativeSummarizer(self.client)
        self.batch_processor = BatchProcessor(
            self.summarizer,
            batch_size=batch_size,
            debug_mode=debug_mode
        )
    
    async def generate_narratives(
        self, 
        photos: List[Dict[str, Any]],
        collection_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate multiple themed narratives for a collection of photos.
        
        Args:
            photos: List of photo metadata dictionaries
            collection_metadata: Optional metadata about the collection
            
        Returns:
            List of narratives
        """
        start_time = time.time()
        logger.info(f"Starting narrative generation for {len(photos)} photos")
        
        try:
            # Skip generation if no photos provided
            if not photos:
                logger.warning("No photos provided for narrative generation")
                return []
                
            # Process photos in batches
            batch_summaries = await self._process_photo_batches(photos)
            
            if not batch_summaries:
                logger.warning("No valid batch summaries generated")
                return []
                
            # Group summaries by theme
            theme_groups = await self._group_summaries_by_theme(batch_summaries)
            
            if not theme_groups:
                logger.warning("No theme groups identified")
                return []
                
            # Merge similar themes
            theme_groups = await self._merge_similar_theme_groups(theme_groups)
            
            # Generate a narrative for each theme group
            narratives = []
            for theme, summaries in theme_groups.items():
                # Only create narratives with sufficient content
                if len(summaries) > 0:
                    narrative = self._convert_summary_to_narrative(summaries[0])
                    narrative = self._enrich_narrative(narrative, summaries, collection_metadata, theme)
                    
                    # Skip narratives with errors or empty content
                    if (narrative.get("narrative") and 
                        "No narrative" not in narrative.get("narrative", "") and
                        narrative.get("photo_ids")):
                        narratives.append(narrative)
            
            # Calculate process duration
            duration = round(time.time() - start_time, 2)
            logger.info(f"Generated {len(narratives)} narratives in {duration} seconds")
            
            # Add metadata to each narrative
            for narrative in narratives:
                if "metadata" not in narrative:
                    narrative["metadata"] = {}
                
                narrative["metadata"].update({
                    "photo_count": len(photos),
                    "batch_count": len(batch_summaries),
                    "narrative_count": len(narratives),
                    "process_time_seconds": duration,
                    "model": self.model,
                    "generated_at": datetime.now().isoformat()
                })
            
            return narratives
            
        except Exception as e:
            logger.error(f"Error in narrative generation: {str(e)}")
            # Return an error result instead of an empty list
            # This way, downstream processors know something went wrong
            traceback.print_exc()
            return [{
                "title": "Error in Narrative Generation",
                "narrative": f"An error occurred while generating narratives: {str(e)}",
                "themes": ["error"],
                "photo_ids": [],
                "metadata": {
                    "error": str(e),
                    "model": self.model,
                    "generated_at": datetime.now().isoformat(),
                    "status": "error"
                }
            }]
    
    async def _process_photo_batches(self, photos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process photos in batches and generate summaries.
        
        Args:
            photos: List of photo metadata
            
        Returns:
            List of batch summaries
        """
        logger.info(f"Processing {len(photos)} photos in batches")
        
        try:
            # Process photos using the batch processor
            batch_summaries = await self.batch_processor.process_photos(
                photos,
                model=self.model,
                max_concurrent_batches=self.max_concurrent_batches
            )
            
            # Log how many batch summaries were created
            logger.info(f"Generated {len(batch_summaries)} batch summaries")
            
            # Return the batch summaries
            return batch_summaries
            
        except Exception as e:
            logger.error(f"Error in batch processing: {str(e)}")
            traceback.print_exc()
            return []
    
    async def _group_summaries_by_theme(
        self, 
        batch_summaries: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group batch summaries by theme.
        
        Args:
            batch_summaries: List of batch summaries
            
        Returns:
            Dictionary mapping theme names to lists of related summaries
        """
        # Initial grouping based on detected themes
        theme_groups = defaultdict(list)
        
        # First, group by explicit detected themes
        for summary in batch_summaries:
            theme = None
            
            # Try to get theme from detected_theme field
            if "detected_theme" in summary:
                theme = summary["detected_theme"]
            
            # If no theme detected, derive one from the summary
            if not theme:
                theme = self._derive_theme_from_summary(summary)
            
            # Default theme if still none
            if not theme:
                theme = "Miscellaneous"
                
            theme_groups[theme].append(summary)
        
        # Now merge very similar themes to avoid fragmentation
        merged_groups = await self._merge_similar_theme_groups(theme_groups)
        
        # Log the themes we found
        logger.info(f"Grouped batch summaries into {len(merged_groups)} themes: {', '.join(merged_groups.keys())}")
        
        return merged_groups
    
    def _derive_theme_from_summary(self, summary: Dict[str, Any]) -> str:
        """Derive a theme from a summary if no explicit theme is available.
        
        Args:
            summary: Batch summary
            
        Returns:
            Derived theme name
        """
        # Try to get primary topic from topics field
        if "topics" in summary and summary["topics"]:
            return f"Theme: {summary['topics'][0]}"
        
        # Try to get primary location
        if "locations" in summary and summary["locations"]:
            return f"Location: {summary['locations'][0]}"
        
        # Try to use meta-summary
        if "meta_summary" in summary and summary["meta_summary"]:
            # Extract key phrases from meta-summary
            words = summary["meta_summary"].lower().split()
            for keyword in ["vacation", "trip", "wedding", "party", "family", "beach", "nature", "city"]:
                if keyword in words:
                    return f"Theme: {keyword.capitalize()}"
        
        # Default theme based on date if available
        if "date_range" in summary:
            date_range = summary["date_range"]
            if "formatted_start" in date_range:
                return f"Period: {date_range['formatted_start']}"
            elif "start" in date_range:
                return f"Period: {date_range['start']}"
        
        # Fallback to batch number
        return f"Group {summary.get('batch_number', 'unknown')}"
    
    async def _merge_similar_theme_groups(
        self, 
        theme_groups: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Merge very similar theme groups to avoid fragmentation.
        
        Args:
            theme_groups: Dictionary mapping theme names to lists of summaries
            
        Returns:
            Dictionary with merged theme groups
        """
        # If we have only a few groups, don't bother merging
        if len(theme_groups) <= 3:
            return theme_groups
        
        # Use a lightweight model to identify similar themes
        try:
            # Prepare the theme data for the model
            theme_data = []
            for theme, summaries in theme_groups.items():
                # Collect key information from all summaries in this theme
                all_topics = []
                all_locations = []
                for summary in summaries:
                    if "topics" in summary:
                        all_topics.extend(summary.get("topics", []))
                    if "locations" in summary:
                        all_locations.extend(summary.get("locations", []))
                
                # Create a theme descriptor
                theme_data.append({
                    "theme": theme,
                    "topics": list(set(all_topics)),
                    "locations": list(set(all_locations)),
                    "count": len(summaries)
                })
            
            # Request theme merging from the model
            messages = [
                {"role": "system", "content": "You are an expert at analyzing and organizing photo collection themes."},
                {"role": "user", "content": f"""Given these theme groups from a photo collection, suggest which ones should be merged together to avoid too many tiny narrative groups.
                 Each theme should represent a cohesive story that users would expect to see together.
                 
                 Theme groups:
                 {json.dumps(theme_data, indent=2)}
                 
                 Respond with a JSON array where each element describes which themes should be merged:
                 [
                     {{"merged_name": "New Theme Name", "themes_to_merge": ["Theme1", "Theme2"]}},
                     {{"merged_name": "Another Theme", "themes_to_merge": ["Theme3", "Theme4", "Theme5"]}}
                 ]
                 
                 Themes that shouldn't be merged should not be included in the response.
                 Don't merge themes that have completely different topics or locations.
                 Try to keep the final number of themes between 3-7 if possible.
                 """}
            ]
            
            # Use a lightweight model for this task
            lightweight_model = "gpt-4o-mini" if self.model != "gpt-4o-mini" else "gpt-3.5-turbo"
            
            # Make the API call
            response = await self.client.call_with_retry(
                model=lightweight_model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=1000
            )
            
            # Process the response
            merge_text = response.choices[0].message.content
            try:
                merge_data = json.loads(merge_text)
                
                # Apply the merges
                merged_groups = defaultdict(list)
                
                # Track which themes have been merged
                merged_themes = set()
                
                # First, process all the merges
                for merge_item in merge_data:
                    merged_name = merge_item.get("merged_name")
                    themes_to_merge = merge_item.get("themes_to_merge", [])
                    
                    if not merged_name or not themes_to_merge:
                        continue
                    
                    # Merge the specified themes
                    for theme in themes_to_merge:
                        if theme in theme_groups:
                            merged_groups[merged_name].extend(theme_groups[theme])
                            merged_themes.add(theme)
                
                # Now add any themes that weren't merged
                for theme, summaries in theme_groups.items():
                    if theme not in merged_themes:
                        merged_groups[theme] = summaries
                
                return dict(merged_groups)
                
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.error(f"Error processing theme merge response: {e}")
                return theme_groups
                
        except Exception as e:
            logger.error(f"Error in theme merging: {e}")
            # If theme merging fails, return the original groups
            return theme_groups
    
    def _convert_summary_to_narrative(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a single batch summary to a narrative structure.
        
        Args:
            summary: Batch summary
            
        Returns:
            Narrative dictionary
        """
        # Extract the main elements from the summary
        narrative_text = summary.get("summary", "No narrative available.")
        
        # Create a basic narrative structure
        narrative = {
            "title": self._generate_title_from_summary(summary),
            "narrative": narrative_text,
            "themes": summary.get("topics", []),
            "timeline": []
        }
        
        # Add a basic timeline if we have date information
        if "date_range" in summary:
            date_range = summary["date_range"]
            narrative["timeline"] = [
                {
                    "period": f"{date_range.get('start', '')} to {date_range.get('end', '')}",
                    "events": [narrative_text]
                }
            ]
        
        return narrative
    
    def _generate_title_from_summary(self, summary: Dict[str, Any]) -> str:
        """Generate a title from a summary.
        
        Args:
            summary: Batch summary
            
        Returns:
            Generated title
        """
        # If we have a meta-summary, use it as a basis for the title
        if "meta_summary" in summary and summary["meta_summary"]:
            meta_summary = summary["meta_summary"]
            # Convert to title case and limit length
            title_words = meta_summary.split()[:8]  # Limit to 8 words
            return " ".join(title_words).title()
        
        # Try to create a title from location and topic
        location = ""
        topic = ""
        
        if "locations" in summary and summary["locations"]:
            location = summary["locations"][0]
            
        if "topics" in summary and summary["topics"]:
            topic = summary["topics"][0]
            
        if location and topic:
            return f"{topic.title()} in {location}"
        elif location:
            return f"Exploring {location}"
        elif topic:
            return f"{topic.title()} Memories"
        
        # Default title if nothing else works
        if "batch_number" in summary:
            return f"Photo Collection - Group {summary['batch_number']}"
        else:
            return "Photo Collection"
    
    def _enrich_narrative(
        self, 
        narrative: Dict[str, Any],
        batch_summaries: List[Dict[str, Any]],
        collection_metadata: Optional[Dict[str, Any]] = None,
        theme: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich the narrative with additional information.
        
        Args:
            narrative: Consolidated narrative
            batch_summaries: List of batch summaries
            collection_metadata: Additional metadata for the collection
            theme: Theme of this narrative
            
        Returns:
            Enriched narrative
        """
        enriched = narrative.copy()
        
        # Add the theme
        if theme:
            enriched["theme"] = theme
        
        # Add collection metadata if provided
        if collection_metadata:
            enriched["collection_metadata"] = collection_metadata
        
        # Extract people from batch summaries
        all_people = set()
        for summary in batch_summaries:
            if "people" in summary and summary["people"]:
                all_people.update(summary["people"])
        
        if all_people:
            enriched["people"] = list(all_people)
        
        # Extract locations from batch summaries
        all_locations = set()
        for summary in batch_summaries:
            if "locations" in summary and summary["locations"]:
                all_locations.update(summary["locations"])
        
        if all_locations:
            enriched["locations"] = list(all_locations)
        
        # Determine date range from batch summaries
        date_range = self._extract_collection_date_range(batch_summaries)
        if date_range:
            enriched["date_range"] = date_range
        
        # Add batch summaries for reference
        enriched["batch_summaries"] = batch_summaries
        
        # Add photo IDs from all batches
        photo_ids = []
        for summary in batch_summaries:
            for photo in summary.get("photos", []):
                if "id" in photo:
                    photo_ids.append(photo["id"])
        
        if photo_ids:
            enriched["photo_ids"] = photo_ids
        
        return enriched
    
    def _extract_collection_date_range(
        self, 
        batch_summaries: List[Dict[str, Any]]
    ) -> Optional[Dict[str, str]]:
        """Extract overall date range from batch summaries.
        
        Args:
            batch_summaries: List of batch summaries
            
        Returns:
            Dictionary with start and end dates if available, None otherwise
        """
        start_dates = []
        end_dates = []
        
        for summary in batch_summaries:
            if "date_range" in summary:
                date_range = summary["date_range"]
                if "start" in date_range:
                    start_dates.append(date_range["start"])
                if "end" in date_range:
                    end_dates.append(date_range["end"])
        
        if not start_dates or not end_dates:
            return None
        
        try:
            # Convert to datetime for comparison and sort
            start_date_objs = []
            for d in start_dates:
                try:
                    start_date_objs.append(datetime.strptime(d, "%Y-%m-%d"))
                except (ValueError, TypeError):
                    # Skip invalid dates
                    logger.warning(f"Skipping invalid start date: {d}")
                    continue
            
            end_date_objs = []
            for d in end_dates:
                try:
                    end_date_objs.append(datetime.strptime(d, "%Y-%m-%d"))
                except (ValueError, TypeError):
                    # Skip invalid dates
                    logger.warning(f"Skipping invalid end date: {d}")
                    continue
            
            if not start_date_objs or not end_date_objs:
                return None
            
            # Get min start date and max end date
            min_start = min(start_date_objs).strftime("%Y-%m-%d")
            max_end = max(end_date_objs).strftime("%Y-%m-%d")
            
            # Format dates for display
            formatted_start = format_date_for_prompt(min_start)
            formatted_end = format_date_for_prompt(max_end)
            
            return {
                "start": min_start,
                "end": max_end,
                "formatted_start": formatted_start,
                "formatted_end": formatted_end,
                "display": f"{formatted_start} to {formatted_end}"
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing date range from batch summaries: {e}")
            return None
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """Create an empty result for cases where no narratives could be generated.
        
        Returns:
            Empty result dictionary
        """
        return {
            "title": "Photo Collection",
            "narrative": "No narrative could be generated for this collection of photos.",
            "themes": [],
            "timeline": [],
            "metadata": {
                "photo_count": 0,
                "batch_count": 0,
                "process_time_seconds": 0,
                "model": self.model,
                "generated_at": datetime.now().isoformat(),
                "status": "empty"
            }
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create an error result for cases where an error occurred.
        
        Args:
            error_message: Error message
            
        Returns:
            Error result dictionary
        """
        return {
            "title": "Error Generating Narrative",
            "narrative": f"An error occurred while generating the narrative: {error_message}",
            "themes": [],
            "timeline": [],
            "metadata": {
                "model": self.model,
                "generated_at": datetime.now().isoformat(),
                "status": "error",
                "error": error_message
            }
        } 
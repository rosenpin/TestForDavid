"""Main narrative generator module for photo collections."""
from typing import List, Dict, Any, Optional
import logging
import asyncio
import time
import json
from datetime import datetime
from openai import AsyncOpenAI

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
        batch_size: int = 25,
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
    ) -> Dict[str, Any]:
        """Generate narratives for a collection of photos.
        
        Args:
            photos: List of photo objects with metadata
            collection_metadata: Additional metadata for the collection
            
        Returns:
            Dictionary with generated narratives and metadata
        """
        start_time = time.time()
        logger.info(f"Starting narrative generation for {len(photos)} photos")
        
        try:
            # Process photos in batches
            batch_summaries = await self.batch_processor.process_photos(
                photos,
                model=self.model,
                max_concurrent_batches=self.max_concurrent_batches
            )
            
            # Save debug info if enabled
            if self.debug_mode:
                await save_debug_info("batch_summaries", batch_summaries, "debug_output")
            
            # If there are no batches, return early
            if not batch_summaries:
                logger.warning("No batch summaries generated, returning empty result")
                return self._create_empty_result()
            
            # Consolidate batch summaries into a narrative
            narrative = await self.summarizer.consolidate_summaries(
                batch_summaries,
                model=self.model
            )
            
            # Enrich the narrative with additional information
            enriched_narrative = self._enrich_narrative(
                narrative, 
                batch_summaries, 
                collection_metadata
            )
            
            # Save debug info if enabled
            if self.debug_mode:
                await save_debug_info("final_narrative", enriched_narrative, "debug_output")
            
            # Calculate duration
            duration = time.time() - start_time
            logger.info(f"Narrative generation completed in {duration:.2f} seconds")
            
            enriched_narrative["metadata"] = {
                "photo_count": len(photos),
                "batch_count": len(batch_summaries),
                "process_time_seconds": duration,
                "model": self.model,
                "generated_at": datetime.now().isoformat()
            }
            
            return enriched_narrative
            
        except Exception as e:
            logger.error(f"Error in narrative generation: {str(e)}")
            # Return a basic structure in case of error
            return self._create_error_result(str(e))
    
    def _enrich_narrative(
        self, 
        narrative: Dict[str, Any],
        batch_summaries: List[Dict[str, Any]],
        collection_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enrich the narrative with additional information.
        
        Args:
            narrative: Consolidated narrative
            batch_summaries: List of batch summaries
            collection_metadata: Additional metadata for the collection
            
        Returns:
            Enriched narrative
        """
        enriched = narrative.copy()
        
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
"""Photo batch processing for narrative generation."""
from typing import List, Dict, Any, Tuple, Optional
import logging
import asyncio
from datetime import datetime
import uuid

from .summarizer import NarrativeSummarizer
from .utils import save_debug_info

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BatchProcessor:
    """Handles the processing of photos in batches for narrative generation."""
    
    def __init__(
        self, 
        summarizer: NarrativeSummarizer,
        batch_size: int = 25,
        debug_mode: bool = False
    ):
        """Initialize the batch processor.
        
        Args:
            summarizer: NarrativeSummarizer instance for batch summarization
            batch_size: Number of photos per batch
            debug_mode: Whether to save debug information
        """
        self.summarizer = summarizer
        self.batch_size = batch_size
        self.debug_mode = debug_mode
    
    async def process_photos(
        self, 
        photos: List[Dict[str, Any]], 
        model: str,
        max_concurrent_batches: int = 5
    ) -> List[Dict[str, Any]]:
        """Process photos in batches and generate summaries.
        
        Args:
            photos: List of photo objects with metadata
            model: The OpenAI model to use
            max_concurrent_batches: Maximum number of concurrent batch processing tasks
            
        Returns:
            List of batch summary dictionaries
        """
        # Sort photos by date if available
        sorted_photos = self._sort_photos(photos)
        
        # Split photos into batches
        batches = self._create_batches(sorted_photos)
        logger.info(f"Split {len(sorted_photos)} photos into {len(batches)} batches")
        
        # Process each batch with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent_batches)
        tasks = []
        
        for i, batch in enumerate(batches):
            batch_id = f"batch_{i+1}_{uuid.uuid4().hex[:8]}"
            task = self._process_batch_with_semaphore(
                semaphore, batch, model, batch_id, i+1, len(batches)
            )
            tasks.append(task)
        
        # Wait for all batches to complete
        batch_summaries = await asyncio.gather(*tasks)
        
        # Return the batch summaries
        return batch_summaries
    
    async def _process_batch_with_semaphore(
        self, 
        semaphore: asyncio.Semaphore, 
        batch: List[Dict[str, Any]], 
        model: str,
        batch_id: str,
        batch_num: int,
        total_batches: int
    ) -> Dict[str, Any]:
        """Process a batch of photos with semaphore for concurrency control.
        
        Args:
            semaphore: Asyncio semaphore for concurrency control
            batch: List of photo objects in the batch
            model: The OpenAI model to use
            batch_id: Unique identifier for the batch
            batch_num: Batch number (1-indexed)
            total_batches: Total number of batches
            
        Returns:
            Batch summary dictionary
        """
        async with semaphore:
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch)} photos")
            
            # Save debug info if enabled
            if self.debug_mode:
                await save_debug_info(batch_id, batch, "debug_output/batches")
            
            # Generate summary for the batch
            summary = await self.summarizer.summarize_batch(
                batch, model, include_meta_summary=True
            )
            
            # Add batch metadata
            summary["batch_id"] = batch_id
            summary["batch_size"] = len(batch)
            summary["batch_number"] = batch_num
            summary["total_batches"] = total_batches
            
            # Try to determine date range for the batch
            date_range = self._extract_date_range(batch)
            if date_range:
                summary["date_range"] = date_range
            
            # Save debug info if enabled
            if self.debug_mode:
                await save_debug_info(f"{batch_id}_summary", summary, "debug_output/summaries")
            
            return summary
    
    def _sort_photos(self, photos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort photos by date if available.
        
        Args:
            photos: List of photo objects with metadata
            
        Returns:
            Sorted list of photos
        """
        # Try to sort photos by date if available
        photos_with_dates = []
        photos_without_dates = []
        
        for photo in photos:
            date_str = photo.get("date")
            if date_str:
                try:
                    # Handle potential float timestamp values
                    if isinstance(date_str, (int, float)):
                        try:
                            date_obj = datetime.fromtimestamp(date_str)
                            photos_with_dates.append((date_obj, photo))
                            continue
                        except (ValueError, TypeError, OverflowError):
                            # If we can't parse as timestamp, continue to string parsing
                            pass
                    
                    # Parse as string in format YYYY-MM-DD
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    photos_with_dates.append((date_obj, photo))
                except (ValueError, TypeError):
                    photos_without_dates.append(photo)
            else:
                photos_without_dates.append(photo)
        
        # Sort photos with dates
        photos_with_dates.sort(key=lambda x: x[0])
        sorted_photos = [photo for _, photo in photos_with_dates] + photos_without_dates
        
        return sorted_photos
    
    def _create_batches(self, photos: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split photos into batches.
        
        Args:
            photos: List of photo objects with metadata
            
        Returns:
            List of photo batches
        """
        batches = []
        
        # Split photos into batches based on batch size
        for i in range(0, len(photos), self.batch_size):
            batch = photos[i:i + self.batch_size]
            batches.append(batch)
        
        return batches
    
    def _extract_date_range(self, batch: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """Extract date range from a batch of photos.
        
        Args:
            batch: List of photo objects with metadata
            
        Returns:
            Dictionary with start and end dates if available, None otherwise
        """
        dates = []
        
        for photo in batch:
            date_value = photo.get("date")
            if date_value:
                try:
                    # Handle potential float timestamp values
                    if isinstance(date_value, (int, float)):
                        try:
                            date_obj = datetime.fromtimestamp(date_value)
                            dates.append(date_obj)
                            continue
                        except (ValueError, TypeError, OverflowError):
                            # If we can't parse as timestamp, continue to string parsing
                            pass
                    
                    # Parse as string in format YYYY-MM-DD
                    date_obj = datetime.strptime(date_value, "%Y-%m-%d")
                    dates.append(date_obj)
                except (ValueError, TypeError):
                    continue
        
        if not dates:
            return None
        
        # Sort dates and get min/max
        dates.sort()
        start_date = dates[0].strftime("%Y-%m-%d")
        end_date = dates[-1].strftime("%Y-%m-%d")
        
        return {
            "start": start_date,
            "end": end_date
        } 
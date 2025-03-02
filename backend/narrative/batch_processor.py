"""Photo batch processing for narrative generation."""
from typing import List, Dict, Any, Tuple, Optional
import logging
import asyncio
from datetime import datetime
import uuid
from collections import defaultdict

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
        batch_size: int = 100,
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
        
        # Create semantic batches instead of arbitrary chunks
        batches = self._create_semantic_batches(sorted_photos)
        logger.info(f"Split {len(sorted_photos)} photos into {len(batches)} semantic batches")
        
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
        
        # Filter out None values (failed batches)
        batch_summaries = [summary for summary in batch_summaries if summary is not None]
        
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
    ) -> Optional[Dict[str, Any]]:
        """Process a batch of photos with semaphore for concurrency control.
        
        Args:
            semaphore: Asyncio semaphore for concurrency control
            batch: List of photo objects in the batch
            model: The OpenAI model to use
            batch_id: Unique identifier for the batch
            batch_num: Batch number (1-indexed)
            total_batches: Total number of batches
            
        Returns:
            Batch summary dictionary or None if processing failed
        """
        async with semaphore:
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch)} photos")
            
            try:
                # Save debug info if enabled
                if self.debug_mode:
                    await save_debug_info(batch_id, batch, "debug_output/batches")
                
                # Try to determine date range for the batch
                date_range = self._extract_date_range(batch)
                
                # Create batch context with metadata about the batch
                batch_context = {
                    "batch_id": batch_id,
                    "batch_size": len(batch),
                    "batch_number": batch_num,
                    "total_batches": total_batches
                }
                
                if date_range:
                    batch_context["date_range"] = date_range
                
                # Generate summary for the batch
                summary = await self.summarizer.summarize_batch(
                    batch, model, include_meta_summary=True, batch_context=batch_context
                )
                
                # Add batch metadata to the summary
                summary["batch_id"] = batch_id
                summary["batch_size"] = len(batch)
                summary["batch_number"] = batch_num
                summary["total_batches"] = total_batches
                
                # Add date range if available
                if date_range:
                    summary["date_range"] = date_range
                
                # Keep track of photos in this batch (store minimal data)
                photo_references = []
                for photo in batch:
                    photo_ref = {
                        "id": photo.get("id", ""),
                        "filename": photo.get("filename", ""),
                    }
                    
                    # Include minimal metadata
                    if "location" in photo:
                        photo_ref["location"] = photo.get("location")
                    
                    if "timestamp" in photo:
                        photo_ref["timestamp"] = photo.get("timestamp")
                    
                    if "date" in photo:
                        photo_ref["date"] = photo.get("date")
                    
                    photo_references.append(photo_ref)
                
                # Add photo references to the summary
                summary["photos"] = photo_references
                
                # Save debug info if enabled
                if self.debug_mode:
                    await save_debug_info(f"{batch_id}_summary", summary, "debug_output/summaries")
                
                return summary
                
            except ValueError as e:
                logger.error(f"Failed to process batch {batch_id}: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error processing batch {batch_id}: {str(e)}")
                return None
    
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
    
    def _create_semantic_batches(self, photos: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Create semantically meaningful batches of photos based on metadata.
        
        This method groups photos into batches based on time proximity,
        location, and content similarity rather than arbitrary chunks.
        
        Args:
            photos: List of photo objects with metadata
            
        Returns:
            List of photo batches grouped by semantic similarity
        """
        # If very few photos, just return a single batch
        if len(photos) <= self.batch_size:
            return [photos]
        
        # 1. Start with location-based clustering
        location_clusters = self._cluster_by_location(photos)
        
        # 2. Further subdivide large location clusters by time
        time_location_clusters = []
        for location_cluster in location_clusters:
            if len(location_cluster) > self.batch_size:
                # Split this location cluster by time periods
                time_clusters = self._cluster_by_time_period(location_cluster)
                time_location_clusters.extend(time_clusters)
            else:
                time_location_clusters.append(location_cluster)
        
        # 3. For any remaining extra-large clusters, use description similarity or split by max size
        final_batches = []
        for cluster in time_location_clusters:
            if len(cluster) > self.batch_size * 2:  # If significantly larger than batch_size
                # Split oversized clusters into manageable chunks, trying to preserve themes
                sub_clusters = self._split_by_description_or_size(cluster, self.batch_size)
                final_batches.extend(sub_clusters)
            else:
                final_batches.append(cluster)
        
        # Ensure no batch is too small (less than 3 photos)
        return self._merge_small_batches(final_batches, min_size=3)
    
    def _cluster_by_location(self, photos: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group photos by location.
        
        Args:
            photos: List of photo objects with metadata
            
        Returns:
            List of photo clusters grouped by location
        """
        # Group photos by location
        location_groups = defaultdict(list)
        
        for photo in photos:
            # Extract location information
            location_key = "unknown"
            location = photo.get("location", {})
            
            if location and isinstance(location, dict):
                # Try to get city or country information
                city = location.get("city")
                country = location.get("country")
                
                if city:
                    location_key = city
                elif country:
                    location_key = country
                # If we have formatted location string, use that as fallback
                elif location.get("formatted"):
                    location_key = location.get("formatted")
            
            # Add photo to appropriate location group
            location_groups[location_key].append(photo)
        
        # Convert dictionary of groups to list of clusters
        return list(location_groups.values())
    
    def _cluster_by_time_period(self, photos: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group photos by time periods.
        
        Args:
            photos: List of photo objects with metadata
            
        Returns:
            List of photo clusters grouped by time period
        """
        # First sort photos by date
        sorted_photos = self._sort_photos(photos)
        
        # Define a significant time gap (in days) that would split clusters
        # This is approximately 1 month in seconds
        time_gap_threshold = 30 * 24 * 60 * 60
        
        clusters = []
        current_cluster = []
        last_timestamp = None
        
        for photo in sorted_photos:
            timestamp = photo.get("timestamp")
            
            # For the first photo, just add it to the current cluster
            if not current_cluster:
                current_cluster.append(photo)
                last_timestamp = timestamp
                continue
            
            # If no timestamp, just add to current cluster
            if timestamp is None or last_timestamp is None:
                current_cluster.append(photo)
                continue
            
            # Check if there's a significant time gap
            try:
                time_diff = abs(float(timestamp) - float(last_timestamp))
                if time_diff > time_gap_threshold:
                    # Start a new cluster if there's a significant time gap
                    if current_cluster:
                        clusters.append(current_cluster)
                        current_cluster = []
            except (ValueError, TypeError):
                # If timestamps can't be compared, just continue with current cluster
                pass
            
            # Add photo to current cluster and update last timestamp
            current_cluster.append(photo)
            last_timestamp = timestamp
        
        # Add the last cluster if not empty
        if current_cluster:
            clusters.append(current_cluster)
        
        # If no clusters were created (possibly due to missing timestamps),
        # fallback to simple size-based batching
        if not clusters:
            return self._create_batches(sorted_photos)
        
        return clusters
    
    # TODO: use gpt-4o-mini instead of basic keyword-based approach
    def _split_by_description_or_size(
        self, 
        photos: List[Dict[str, Any]], 
        target_size: int
    ) -> List[List[Dict[str, Any]]]:
        """Split a large batch of photos by description similarity or by size.
        
        Args:
            photos: List of photo objects to split
            target_size: Target size for each sub-batch
            
        Returns:
            List of photo batches
        """
        # If we have descriptions, try to group by similar descriptions
        if all(photo.get("description") for photo in photos):
            # This is a simple keyword-based approach
            topic_clusters = defaultdict(list)
            
            for photo in photos:
                description = photo.get("description", "").lower()
                
                # Simple keyword detection for common themes
                keywords = [
                    "beach", "mountain", "city", "food", "family", 
                    "party", "travel", "holiday", "wedding", "nature",
                    "sunset", "indoor", "outdoor", "night", "day"
                ]
                
                # Find matching keywords in description
                matches = [k for k in keywords if k in description]
                
                # Use the first matching keyword or "other" if none match
                key = matches[0] if matches else "other"
                topic_clusters[key].append(photo)
            
            # Convert to list of clusters and handle any that are too large
            result_clusters = []
            for topic_photos in topic_clusters.values():
                if len(topic_photos) > target_size * 1.5:
                    # Further subdivide large topic clusters by size
                    subclusters = self._create_batches(topic_photos)
                    result_clusters.extend(subclusters)
                else:
                    result_clusters.append(topic_photos)
                    
            return result_clusters
        
        # Fallback to simple size-based batching
        return self._create_batches(photos)
    
    def _create_batches(self, photos: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split photos into batches of approximately equal size.
        
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
    
    def _merge_small_batches(
        self, 
        batches: List[List[Dict[str, Any]]], 
        min_size: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """Merge very small batches with their neighbors.
        
        Args:
            batches: List of photo batches
            min_size: Minimum batch size
            
        Returns:
            List of merged photo batches
        """
        if not batches:
            return []
        
        # Skip merging if all batches are already larger than min_size
        if all(len(batch) >= min_size for batch in batches):
            return batches
        
        result = []
        current_batch = []
        
        for batch in batches:
            # If current accumulating batch is empty, start with this batch
            if not current_batch:
                current_batch = batch
                continue
            
            # If either this batch or accumulated batch is small, merge them
            if len(batch) < min_size or len(current_batch) < min_size:
                current_batch.extend(batch)
            else:
                # Both batches are large enough, add current to result and start new
                result.append(current_batch)
                current_batch = batch
        
        # Add the last accumulated batch
        if current_batch:
            result.append(current_batch)
        
        return result
    
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
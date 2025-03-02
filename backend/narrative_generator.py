"""Narrative generator for photo collections.

This is the main entry point for the narrative generation functionality.
It maintains the same interface as the original narrative_generator.py but
uses a modular structure internally for better maintainability.
"""
import os
import json
from typing import Dict, List, Any, Callable, Optional
import uuid
from openai import AsyncOpenAI
from dotenv import load_dotenv
import datetime
import asyncio
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modular components
from narrative.narrative_generator import NarrativeGenerator as ModularNarrativeGenerator
from narrative.utils import save_debug_info

# Load environment variables
load_dotenv()

class NarrativeGenerator:
    """Narrative generator for photo collections that maintains the original API."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize the narrative generator.
        
        Args:
            data_dir: Data directory for storing photos and metadata
        """
        self.data_dir = data_dir
        self.metadata_dir = os.path.join(data_dir, "metadata")
        self.photos_metadata_dir = os.path.join(self.metadata_dir, "photos")
        
        # Create necessary directories
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.photos_metadata_dir, exist_ok=True)
        
        # Get the OpenAI API key
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not found in environment variables")
        
        # Create the modular narrative generator
        self.generator = ModularNarrativeGenerator(
            api_key=self.api_key,
            model="o1",
            batch_size=100,
            max_concurrent_batches=5,
            debug_mode=True  # Enable debug mode for development
        )
    
    async def generate_narratives(self, status_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Generate narratives from photo descriptions.
        
        Args:
            status_callback: Optional callback function for status updates
            
        Returns:
            List of narrative objects
        """
        try:
            # Update status if callback provided
            if status_callback:
                status_callback(current_stage="generating_narratives")
            
            # Load photo descriptions
            descriptions = []
            people_data = {}
            
            # Find all photo metadata files
            photo_files = [f for f in os.listdir(self.photos_metadata_dir) if f.endswith(".json")]
            logger.info(f"Found {len(photo_files)} photo metadata files")
            
            # Update status if callback provided
            if status_callback:
                status_callback(total_photos=len(photo_files))
            
            # Load each photo's metadata
            for i, filename in enumerate(photo_files):
                file_path = os.path.join(self.photos_metadata_dir, filename)
                with open(file_path, "r") as f:
                    photo_data = json.load(f)
                
                # Extract photo ID from filename
                photo_id = os.path.splitext(filename)[0]
                photo_data["id"] = photo_id
                
                # Add to descriptions
                descriptions.append(photo_data)
                
                # Update people stats if face data exists
                if "faces" in photo_data and photo_data["faces"]:
                    for face in photo_data["faces"]:
                        if "person_id" in face and face["person_id"]:
                            person_id = face["person_id"]
                            if person_id not in people_data:
                                people_data[person_id] = {"photo_count": 0, "face_count": 0}
                            
                            people_data[person_id]["photo_count"] += 1
                            people_data[person_id]["face_count"] += 1
                
                # Update status periodically if callback provided
                if status_callback and i % 10 == 0:
                    status_callback(processed_photos=i+1)
            
            # Update status if callback provided
            if status_callback:
                status_callback(processed_photos=len(photo_files))
            
            # For empty collections, return early
            if not descriptions:
                logger.warning("No photos found, returning empty narrative list")
                return []
            
            # Format the photo data for our modular generator
            photos_for_generator = []
            for photo in descriptions:
                # Convert timestamp (float) to date string if needed
                date_value = photo.get("date") or photo.get("timestamp", "")
                formatted_date = ""
                if isinstance(date_value, (int, float)):
                    try:
                        # Convert Unix timestamp to YYYY-MM-DD format
                        formatted_date = datetime.datetime.fromtimestamp(date_value).strftime("%Y-%m-%d")
                    except (ValueError, TypeError, OverflowError) as e:
                        logger.warning(f"Failed to convert timestamp {date_value}: {e}")
                elif isinstance(date_value, str):
                    formatted_date = date_value
                
                formatted_photo = {
                    "id": photo.get("id", ""),
                    "caption": photo.get("description", "") or photo.get("caption", ""),
                    "date": formatted_date,
                    "location": photo.get("location", "") or photo.get("place", ""),
                }
                
                # Add any people detected in the photo
                if "faces" in photo and photo["faces"]:
                    people = []
                    for face in photo["faces"]:
                        if "person_id" in face and face["person_id"]:
                            people.append(face["person_id"])
                    if people:
                        formatted_photo["people"] = people
                
                photos_for_generator.append(formatted_photo)
            
            # Create collection metadata
            collection_metadata = {
                "people_data": people_data
            }
            
            # Generate narratives using our modular generator
            narrative_result = await self.generator.generate_narratives(
                photos_for_generator,
                collection_metadata
            )
            
            # Save debug info
            await save_debug_info("narrative_result", narrative_result, os.path.join(self.data_dir, "debug_output"))
            
            # Format the narratives for the expected output format
            narratives = []
            
            if "batch_summaries" in narrative_result:
                # Build from batch summaries and themes
                narrative_themes = narrative_result.get("themes", [])
                narrative_title = narrative_result.get("title", "Photo Collection")
                
                # Create a narrative for each theme or batch summary
                if narrative_themes:
                    # Use themes as narratives
                    for i, theme in enumerate(narrative_themes):
                        # Find related photos based on keywords
                        related_photos = self._find_related_photos(
                            theme, 
                            narrative_result.get("batch_summaries", []),
                            photos_for_generator
                        )
                        
                        narratives.append({
                            "id": str(i + 1),
                            "title": theme,
                            "description": narrative_result.get("narrative", "A collection of photos."),
                            "photo_ids": related_photos,
                            "selected_photo_ids": self.select_photos_for_display(related_photos)
                        })
                else:
                    # Create one narrative per batch summary
                    for i, batch in enumerate(narrative_result.get("batch_summaries", [])):
                        batch_photos = []
                        for photo in photos_for_generator:
                            # Get photo IDs from this batch
                            if any(keyword in (photo.get("caption", "") + " " + 
                                              photo.get("location", "")).lower() 
                                  for keyword in batch.get("keywords", [])):
                                batch_photos.append(photo["id"])
                        
                        # If no photos found, use a subset of all photos
                        if not batch_photos:
                            batch_photos = [p["id"] for p in 
                                           random.sample(photos_for_generator, 
                                                        min(50, len(photos_for_generator)))]
                        
                        narratives.append({
                            "id": str(i + 1),
                            "title": batch.get("meta_summary", f"Batch {i+1}"),
                            "description": batch.get("summary", "A collection of photos."),
                            "photo_ids": batch_photos,
                            "selected_photo_ids": self.select_photos_for_display(batch_photos)
                        })
            else:
                # Just create a single narrative with all photos
                photo_ids = [photo["id"] for photo in photos_for_generator]
                narratives.append({
                    "id": "1",
                    "title": narrative_result.get("title", "Photo Collection"),
                    "description": narrative_result.get("narrative", "A collection of photos."),
                    "photo_ids": photo_ids,
                    "selected_photo_ids": self.select_photos_for_display(photo_ids)
                })
            
            # Save the narratives to file
            narratives_path = os.path.join(self.metadata_dir, "narratives.json")
            with open(narratives_path, "w") as f:
                json.dump(narratives, f, indent=2)
            
            # Update photo metadata with narrative assignments
            for narrative in narratives:
                for photo_id in narrative["photo_ids"]:
                    photo_path = os.path.join(self.photos_metadata_dir, f"{photo_id}.json")
                    if os.path.exists(photo_path):
                        with open(photo_path, "r") as f:
                            photo_data = json.load(f)
                        
                        if "narratives" not in photo_data:
                            photo_data["narratives"] = []
                        
                        # Add narrative ID if not already present
                        if narrative["id"] not in photo_data["narratives"]:
                            photo_data["narratives"].append(narrative["id"])
                        
                        with open(photo_path, "w") as f:
                            json.dump(photo_data, f, indent=2)
            
            # Update status
            if status_callback:
                status_callback(current_stage="complete")
            
            return narratives
        
        except Exception as e:
            logger.error(f"Error generating narratives: {str(e)}")
            if status_callback:
                status_callback(error=str(e))
            raise
    
    def _find_related_photos(
        self, 
        theme: str, 
        batch_summaries: List[Dict[str, Any]],
        photos: List[Dict[str, Any]]
    ) -> List[str]:
        """Find photos related to a theme.
        
        Args:
            theme: Theme to find related photos for
            batch_summaries: List of batch summaries
            photos: List of photo objects
            
        Returns:
            List of photo IDs related to the theme
        """
        related_photos = set()
        theme_lower = theme.lower()
        
        # Look for photos with matching themes in batch summaries
        for batch in batch_summaries:
            if any(kw in theme_lower for kw in batch.get("keywords", [])) or \
               theme_lower in batch.get("summary", "").lower():
                # This batch is related to the theme
                for photo in photos:
                    # Ensure we're concatenating strings
                    caption = str(photo.get("caption", "")) if photo.get("caption") is not None else ""
                    location = str(photo.get("location", "")) if photo.get("location") is not None else ""
                    photo_text = (caption + " " + location).lower()
                    
                    if any(kw in photo_text for kw in batch.get("keywords", [])):
                        related_photos.add(photo["id"])
        
        # If we didn't find any photos, search directly in photo captions
        if not related_photos:
            for photo in photos:
                # Ensure we're concatenating strings
                caption = str(photo.get("caption", "")) if photo.get("caption") is not None else ""
                location = str(photo.get("location", "")) if photo.get("location") is not None else ""
                photo_text = (caption + " " + location).lower()
                
                if theme_lower in photo_text:
                    related_photos.add(photo["id"])
        
        # If still empty, get a random selection
        if not related_photos:
            sample_size = min(50, len(photos))
            related_photos = set(p["id"] for p in random.sample(photos, sample_size))
        
        return list(related_photos)
    
    def select_photos_for_display(self, photo_ids: List[str], max_photos: Optional[int] = None) -> List[str]:
        """Select photos to display in the narrative.
        
        This function can be used to intelligently select a subset of photos for display.
        For now, it simply returns all photos without restriction.
        
        Args:
            photo_ids: List of all photo IDs
            max_photos: Optional maximum number of photos to select
            
        Returns:
            List of selected photo IDs
        """
        # For now, just return all photos without any limit
        return photo_ids
        
        # Future implementation could intelligently select photos based on:
        # - Image quality
        # - Diversity of content
        # - Temporal distribution
        # - Etc. 
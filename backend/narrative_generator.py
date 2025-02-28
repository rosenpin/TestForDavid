import os
import json
from typing import Dict, List, Any
import uuid
from openai import AsyncOpenAI
from dotenv import load_dotenv
import datetime

# Load environment variables
load_dotenv()

# Configure OpenAI API
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class NarrativeGenerator:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.metadata_dir = os.path.join(data_dir, "metadata")
        self.photos_metadata_dir = os.path.join(self.metadata_dir, "photos")
        
        # Create necessary directories
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.photos_metadata_dir, exist_ok=True)
    
    async def generate_narratives(self, status_callback=None) -> List[Dict[str, Any]]:
        """Generate narratives from photo descriptions."""
        try:
            # Update status
            if status_callback:
                status_callback(current_stage="generating_narratives")
            
            # Load all photo metadata
            photo_metadata = []
            for filename in os.listdir(self.photos_metadata_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(self.photos_metadata_dir, filename), "r") as f:
                        metadata = json.load(f)
                        photo_metadata.append(metadata)
            
            # If we don't have enough photos, return empty narratives
            if len(photo_metadata) < 5:
                return []
            
            # Prepare descriptions for the LLM
            descriptions = [
                {
                    "id": photo["id"],
                    "description": photo["description"],
                    "timestamp": photo["timestamp"],
                    "location": photo.get("location", None),
                    "date_taken": datetime.datetime.fromtimestamp(photo["timestamp"]).strftime("%Y-%m-%d %H:%M:%S") if photo.get("timestamp") else None,
                    "location_name": self._format_location(photo.get("location", None)),
                    "people": photo.get("people", [])
                }
                for photo in photo_metadata
            ]
            
            # Sort by timestamp
            descriptions.sort(key=lambda x: x["timestamp"])
            
            # Generate narratives using OpenAI
            narratives = await self._generate_narratives_with_llm(descriptions)
            
            # Ensure each narrative has selected_photo_ids
            for narrative in narratives:
                # If selected_photo_ids is missing or empty, select representative photos
                if "selected_photo_ids" not in narrative or not narrative["selected_photo_ids"]:
                    narrative["selected_photo_ids"] = await self.select_representative_photos(narrative, photo_metadata)
                # Ensure all selected_photo_ids are valid (exist in photo_ids)
                else:
                    narrative["selected_photo_ids"] = [
                        photo_id for photo_id in narrative["selected_photo_ids"] 
                        if photo_id in narrative["photo_ids"]
                    ]
                    # If we filtered out all selected photos, select new ones
                    if not narrative["selected_photo_ids"]:
                        narrative["selected_photo_ids"] = await self.select_representative_photos(narrative, photo_metadata)
            
            # Save narratives
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
            print(f"Error generating narratives: {str(e)}")
            if status_callback:
                status_callback(error=str(e))
            raise
    
    def _format_location(self, location: Dict[str, Any]) -> str:
        """Format location information into a readable string."""
        if not location:
            return ""
        
        # Use the pre-formatted location string if available
        if location.get("formatted"):
            return location["formatted"]
        
        # Check if we have reverse geocoded information
        if "city" in location and "country" in location:
            if location["city"] and location["state"] and location["country"]:
                return f"{location['city']}, {location['state']}, {location['country']}"
            elif location["city"] and location["country"]:
                return f"{location['city']}, {location['country']}"
            elif location["country"]:
                return location["country"]
        
        # Fallback to coordinates
        if "latitude" in location and "longitude" in location:
            return f"Coordinates: {location['latitude']:.6f}, {location['longitude']:.6f}"
        
        return ""
    
    async def _generate_narratives_with_llm(self, descriptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use OpenAI to generate narratives from photo descriptions."""
        try:
            # Get people information
            people_data = self._collect_people_data(descriptions)
            
            # Prepare the prompt
            descriptions_text = "\n".join([
                f"Photo {i+1} (ID: {desc['id']}): {desc['description']}" + 
                (f" | Location: {desc['location_name']}" if desc.get('location_name') else 
                 (f" | Coordinates: {desc['location']['latitude']}, {desc['location']['longitude']}" if desc.get('location') else "")) +
                (f" | Date Taken: {desc['date_taken']}" if desc.get('date_taken') else "") +
                (f" | People: {', '.join(desc.get('people', []))}" if desc.get('people') else "")
                for i, desc in enumerate(descriptions)
            ])
            
            # Add people information to the prompt
            people_text = ""
            if people_data:
                people_text = "\n\nPeople identified in photos:\n" + "\n".join([
                    f"Person {person_id}: Appears in {stats['photo_count']} photos"
                    for person_id, stats in people_data.items()
                ])
            
            # Call OpenAI API using the client
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at analyzing photo collections and identifying meaningful life narratives.
                        Your task is to analyze photo descriptions and group them into coherent narratives or stories.
                        
                        IMPORTANT: You MUST respond with a valid JSON object containing an array of narrative objects.
                        
                        Each narrative MUST have these fields:
                        - "id": A unique string identifier (can be a simple number like "1", "2", etc.)
                        - "title": A short, engaging title (string)
                        - "description": A 1-2 paragraph description (string)
                        - "photo_ids": An array of string photo IDs that belong to this narrative
                        - "selected_photo_ids": An array of string photo IDs that are most representative (a subset of photo_ids)
                        
                        Pay special attention to:
                        1. Location data and timestamps when available
                        2. People identified in photos (person_X IDs represent the same individual across photos)
                        
                        Consider creating people-focused narratives for individuals who appear frequently.
                        
                        Create between 3-7 distinct narratives, depending on the diversity of the photos.
                        Each narrative should tell a meaningful story about the person's life, experiences, or interests.
                        A photo can belong to multiple narratives if relevant.
                        
                        REMEMBER: Your response MUST be a valid JSON object with this exact structure:
                        {
                          "narratives": [
                            {
                              "id": "1",
                              "title": "Narrative Title",
                              "description": "Detailed description of the narrative",
                              "photo_ids": ["photo-id-1", "photo-id-2", ...],
                              "selected_photo_ids": ["photo-id-1", "photo-id-3", ...]
                            },
                            ...
                          ]
                        }"""
                    },
                    {
                        "role": "user",
                        "content": f"""Here are descriptions of photos from someone's life. Analyze these descriptions and identify meaningful narratives or stories:

{descriptions_text}{people_text}

IMPORTANT: Your response MUST be a valid JSON object with the exact structure specified in the system instructions.
"""
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=16383
            )
            
            # Parse the response
            content = response.choices[0].message.content.strip()
            narratives_data = json.loads(content)
            
            # Ensure we have the expected format
            if "narratives" in narratives_data:
                narratives = narratives_data["narratives"]
            else:
                narratives = narratives_data
            
            # Ensure each narrative has a unique ID
            for narrative in narratives:
                if "id" not in narrative or not narrative["id"]:
                    narrative["id"] = str(uuid.uuid4())
                
                # Ensure photo_ids is present
                if "photo_ids" not in narrative or not narrative["photo_ids"]:
                    narrative["photo_ids"] = []
                
                # Ensure selected_photo_ids is present
                if "selected_photo_ids" not in narrative:
                    narrative["selected_photo_ids"] = []
                
                # Ensure all selected_photo_ids are in photo_ids
                narrative["selected_photo_ids"] = [
                    photo_id for photo_id in narrative["selected_photo_ids"] 
                    if photo_id in narrative["photo_ids"]
                ]
            
            return narratives
        
        except Exception as e:
            print(f"Error generating narratives with LLM: {str(e)}")
            # Return a simple fallback narrative if there's an error
            return [{
                "id": str(uuid.uuid4()),
                "title": "Photo Collection",
                "description": "A collection of photos from various moments in life.",
                "photo_ids": [desc["id"] for desc in descriptions],
                "selected_photo_ids": [desc["id"] for desc in descriptions[:min(10, len(descriptions))]]
            }]
    
    async def select_representative_photos(self, narrative: Dict[str, Any], photo_metadata: List[Dict[str, Any]]) -> List[str]:
        """Select the most representative photos for a narrative."""
        # Filter photos that belong to this narrative
        narrative_photos = [photo for photo in photo_metadata if photo["id"] in narrative["photo_ids"]]
        
        # If we have 10 or fewer photos, use all of them
        if len(narrative_photos) <= 10:
            return [photo["id"] for photo in narrative_photos]
        
        # Otherwise, use OpenAI to select the most representative ones
        try:
            # Prepare the prompt
            photos_text = "\n".join([
                f"Photo {i+1} (ID: {photo['id']}): {photo['description']}" + 
                (f" | Location: {self._format_location(photo.get('location'))}" if photo.get('location') else "") +
                (f" | Date Taken: {datetime.datetime.fromtimestamp(photo['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}" if photo.get('timestamp') else "")
                for i, photo in enumerate(narrative_photos)
            ])
            
            # Call OpenAI API using the client
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert curator who selects the most representative and engaging photos for a narrative.
                        Your task is to select a subset of photos that best tell the story of a narrative.
                        
                        IMPORTANT: You MUST respond with a valid JSON object containing an array of photo IDs.
                        
                        The response format MUST be:
                        {
                          "selected_photo_ids": ["photo-id-1", "photo-id-2", ...]
                        }
                        
                        Choose photos that are diverse, visually interesting, and capture key moments or elements of the narrative.
                        
                        Consider location and time data when making your selection:
                        - Include photos from different locations if the narrative spans multiple places
                        - Select photos that show progression over time if relevant
                        - Prioritize photos with both location and time data when available
                        
                        Avoid selecting very similar photos or ones that don't add new information to the narrative.
                        
                        REMEMBER: Your response MUST be a valid JSON object with the exact structure shown above."""
                    },
                    {
                        "role": "user",
                        "content": f"""Here is a narrative titled "{narrative['title']}" with the following description:
{narrative['description']}

And here are all the photos that belong to this narrative:
{photos_text}

Select the 5-10 most representative photos that best tell this narrative.

IMPORTANT: Your response MUST be a valid JSON object with the exact structure specified in the system instructions.
"""
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            # Parse the response
            content = response.choices[0].message.content.strip()
            selected_photos_data = json.loads(content)
            
            # Ensure we have the expected format
            if "selected_photo_ids" in selected_photos_data:
                selected_photos = selected_photos_data["selected_photo_ids"]
            else:
                selected_photos = selected_photos_data
            
            # Validate that all selected photos are in the narrative
            valid_selected_photos = [photo_id for photo_id in selected_photos if photo_id in narrative["photo_ids"]]
            
            # If we don't have any valid selected photos, use a subset of the narrative photos
            if not valid_selected_photos:
                import random
                valid_selected_photos = random.sample(narrative["photo_ids"], min(10, len(narrative["photo_ids"])))
            
            return valid_selected_photos
        
        except Exception as e:
            print(f"Error selecting representative photos: {str(e)}")
            # Fallback: select a random subset
            import random
            return random.sample(narrative["photo_ids"], min(10, len(narrative["photo_ids"])))
    
    def _collect_people_data(self, descriptions: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """Collect statistics about people appearing in photos."""
        people_stats = {}
        
        # Gather all photos by person
        for desc in descriptions:
            if "people" in desc and desc["people"]:
                for person_id in desc["people"]:
                    if person_id not in people_stats:
                        people_stats[person_id] = {"photo_count": 0, "photos": []}
                    
                    people_stats[person_id]["photo_count"] += 1
                    people_stats[person_id]["photos"].append(desc["id"])
        
        # Filter out people who appear in fewer than 3 photos
        filtered_stats = {
            person_id: stats 
            for person_id, stats in people_stats.items() 
            if stats["photo_count"] >= 3
        }
        
        # Remove the photos list from the output to keep it clean
        for person_id in filtered_stats:
            del filtered_stats[person_id]["photos"]
        
        return filtered_stats 
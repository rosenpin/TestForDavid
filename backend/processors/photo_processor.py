import os
import json
import uuid
import asyncio
import reverse_geocode
from typing import Dict, List, Any, Optional, Callable
from PIL import Image

from .exif_processor import ExifProcessor
from .face_processor import FaceProcessor
from .description_generator import DescriptionGenerator

# Include file utility functions directly
def ensure_directory(directory_path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(directory_path, exist_ok=True)

def copy_file(source_path: str, destination_path: str) -> None:
    """Copy a file from source to destination."""
    with open(source_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
        dst_file.write(src_file.read())

def remove_file(file_path: str) -> None:
    """Remove a file if it exists."""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing file {file_path}: {str(e)}")

def ensure_serializable(data):
    """Ensure that data is JSON serializable."""
    if isinstance(data, dict):
        return {str(k): ensure_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_serializable(item) for item in data]
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data
    else:
        # Convert anything else to string
        return str(data)

class PhotoProcessor:
    def __init__(self, data_dir: str = "data"):
        """Initialize the photo processor and its component processors."""
        # Set up directories
        self.data_dir = data_dir
        self.photos_dir = os.path.join(data_dir, "photos")
        self.metadata_dir = os.path.join(data_dir, "metadata")
        self.photos_metadata_dir = os.path.join(self.metadata_dir, "photos")
        self.faces_dir = os.path.join(data_dir, "faces")
        
        # Create necessary directories
        ensure_directory(self.photos_dir)
        ensure_directory(self.metadata_dir)
        ensure_directory(self.photos_metadata_dir)
        ensure_directory(self.faces_dir)
        
        # Initialize component processors
        self.exif_processor = ExifProcessor()
        self.face_processor = FaceProcessor(self.faces_dir, self.metadata_dir)
        self.description_generator = DescriptionGenerator()
    
    async def process_photo(self, photo_path: str) -> Dict[str, Any]:
        """Process a single photo, extracting metadata, detecting faces, and generating description."""
        try:
            # Generate a unique ID for the photo
            photo_id = str(uuid.uuid4())
            
            # Get file extension
            file_extension = os.path.splitext(photo_path)[1].lower()
            
            # Extract EXIF data
            exif_data = self.exif_processor.extract_exif_data(photo_path)
            
            # Handle HEIC/HEIF conversion if needed
            if file_extension in ['.heic', '.heif']:
                temp_jpeg_path = os.path.join(self.photos_dir, f"{photo_id}_temp.jpg")
                try:
                    img = Image.open(photo_path)
                    img.save(temp_jpeg_path, format="JPEG", quality=95)
                    photo_path = temp_jpeg_path
                    file_extension = '.jpg'
                except Exception as e:
                    print(f"Cannot process HEIC/HEIF file {photo_path}: {str(e)}")
                    return self._create_minimal_metadata(photo_id, photo_path, file_extension, exif_data)
            
            # Create a new filename and copy the photo
            new_filename = f"{photo_id}{file_extension}"
            destination_path = os.path.join(self.photos_dir, new_filename)
            
            copy_file(photo_path, destination_path)
            
            # Detect and process faces in the photo
            faces_data = await self.face_processor.process_faces(destination_path, photo_id)
            
            # Generate description using OpenAI
            description = await self.description_generator.generate_description(destination_path)
            
            # Apply reverse geocoding if we have GPS coordinates
            if exif_data.get("location"):
                try:
                    lat = exif_data["location"]["latitude"]
                    lon = exif_data["location"]["longitude"]
                    
                    coordinates = [(lat, lon)]
                    location_result = reverse_geocode.search(coordinates)[0]
                    
                    # Update location with reverse geocoded information
                    exif_data["location"].update({
                        "city": location_result.get("city"),
                        "state": location_result.get("state"),
                        "country": location_result.get("country"),
                        "country_code": location_result.get("country_code")
                    })
                    
                    # Create a human-readable location string
                    location_str = self.exif_processor.format_location(exif_data["location"])
                    exif_data["location"]["formatted"] = location_str
                except Exception as e:
                    print(f"Error in reverse geocoding: {str(e)}")
            
            # Create metadata
            metadata = {
                "id": photo_id,
                "filename": new_filename,
                "original_path": photo_path,
                "description": description,
                "timestamp": exif_data.get("timestamp") or os.path.getmtime(photo_path),
                "location": exif_data.get("location"),
                "exif": ensure_serializable(exif_data.get("exif", {})),
                "faces": faces_data,
                "people": [],  # Will be filled during face clustering
                "narratives": []
            }
            
            # Save metadata
            metadata_path = os.path.join(self.photos_metadata_dir, f"{photo_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Clean up temporary files
            if photo_path.endswith('_temp.jpg') and os.path.exists(photo_path):
                remove_file(photo_path)
            
            return metadata
        
        except Exception as e:
            print(f"Error processing photo {photo_path}: {str(e)}")
            return self._create_minimal_metadata(
                photo_id if 'photo_id' in locals() else str(uuid.uuid4()),
                photo_path,
                file_extension if 'file_extension' in locals() else os.path.splitext(photo_path)[1].lower(),
                exif_data if 'exif_data' in locals() else {}
            )
    
    def _create_minimal_metadata(self, photo_id, photo_path, file_extension, exif_data=None):
        """Create minimal metadata for files that couldn't be processed properly."""
        if exif_data is None:
            exif_data = {}
        
        return {
            "id": photo_id,
            "filename": f"{photo_id}{file_extension}",
            "original_path": photo_path,
            "description": "Could not process image file.",
            "timestamp": exif_data.get("timestamp") or os.path.getmtime(photo_path),
            "location": exif_data.get("location"),
            "exif": ensure_serializable(exif_data.get("exif", {})),
            "faces": [],
            "people": [],
            "narratives": []
        }
    
    async def process_directory(self, directory_path: str, status_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Process all photos in a directory."""
        photo_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif']
        photo_paths = []
        
        # Find all photos in the directory
        for root, _, files in os.walk(directory_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in photo_extensions):
                    photo_paths.append(os.path.join(root, file))
        
        # Update status
        total_photos = len(photo_paths)
        processed_photos = 0
        
        if status_callback:
            status_callback(total_photos=total_photos, processed_photos=processed_photos, current_stage="analyzing")
        
        # Process photos in batches
        batch_size = 5
        all_metadata = []
        
        for i in range(0, len(photo_paths), batch_size):
            batch = photo_paths[i:i+batch_size]
            tasks = [self.process_photo(photo_path) for photo_path in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if not isinstance(result, Exception):
                    all_metadata.append(result)
            
            processed_photos += len(batch)
            if status_callback:
                status_callback(processed_photos=processed_photos)
        
        # After processing all photos, perform face clustering if we have detected faces
        if self.face_processor.face_embeddings:
            if status_callback:
                status_callback(current_stage="clustering_faces")
            
            person_clusters = await self.face_processor.cluster_faces()
            person_stats = await self.face_processor.update_photos_with_person_ids(person_clusters, self.photos_metadata_dir)
            
            # Log clustering results
            print(f"Face clustering complete. Identified {len(person_clusters)} unique individuals.")
            if person_stats:
                print("Person statistics:", json.dumps({k: {"face_count": v["face_count"], "photo_count": v["photo_count"]} 
                                                    for k, v in person_stats.items()}, indent=2))
        
        return all_metadata 
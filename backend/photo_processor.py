import os
import json
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import uuid
import asyncio
from PIL import Image
import io
import openai
import exifread
import datetime
import pillow_heif
from fractions import Fraction
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# Configure OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

class PhotoProcessor:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.photos_dir = os.path.join(data_dir, "photos")
        self.metadata_dir = os.path.join(data_dir, "metadata")
        self.photos_metadata_dir = os.path.join(self.metadata_dir, "photos")
        
        # Create necessary directories
        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(self.photos_metadata_dir, exist_ok=True)
    
    async def process_photo(self, photo_path: str) -> Dict[str, Any]:
        """Process a single photo and generate a description using OpenAI."""
        try:
            # Generate a unique ID for the photo
            photo_id = str(uuid.uuid4())
            
            # Get file extension
            file_extension = os.path.splitext(photo_path)[1].lower()
            
            # Check if the file is a HEIC/HEIF file and if we should attempt conversion
            if file_extension in ['.heic', '.heif']:
                try:
                    # Try to open the HEIC file to verify it's readable
                    heif_file = pillow_heif.read_heif(photo_path)
                    
                    # If we got here, we can read the HEIC file, so continue processing
                    print(f"Successfully verified HEIC/HEIF file: {photo_path}")
                except Exception as e:
                    print(f"Cannot process HEIC/HEIF file {photo_path}, error: {str(e)}")
                    # Return minimal metadata for unreadable files
                    return {
                        "id": photo_id,
                        "filename": f"{photo_id}{file_extension}",
                        "original_path": photo_path,
                        "description": "Unreadable HEIC/HEIF image file.",
                        "timestamp": os.path.getmtime(photo_path),
                        "location": None,
                        "exif": {"error": f"Cannot process HEIC/HEIF format: {str(e)}"},
                        "narratives": []
                    }
            
            # Create a new filename
            new_filename = f"{photo_id}{file_extension}"
            destination_path = os.path.join(self.photos_dir, new_filename)
            
            # Copy the photo to our data directory
            with open(photo_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
                dst_file.write(src_file.read())
            
            # Extract EXIF data
            exif_data = self._extract_exif_data(photo_path)
            
            # Generate description using OpenAI
            description = await self._generate_description(destination_path)
            
            # Create metadata
            metadata = {
                "id": photo_id,
                "filename": new_filename,
                "original_path": photo_path,
                "description": description,
                "timestamp": exif_data.get("timestamp") or os.path.getmtime(photo_path),
                "location": exif_data.get("location"),
                "exif": exif_data.get("exif", {}),
                "narratives": []  # Will be populated later
            }
            
            # Save metadata
            metadata_path = os.path.join(self.photos_metadata_dir, f"{photo_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            
            return metadata
        
        except Exception as e:
            print(f"Error processing photo {photo_path}: {str(e)}")
            # Return minimal metadata for files with errors
            return {
                "id": photo_id if 'photo_id' in locals() else str(uuid.uuid4()),
                "filename": f"{photo_id if 'photo_id' in locals() else str(uuid.uuid4())}{file_extension if 'file_extension' in locals() else os.path.splitext(photo_path)[1].lower()}",
                "original_path": photo_path,
                "description": f"Error processing image: {str(e)}",
                "timestamp": os.path.getmtime(photo_path),
                "location": None,
                "exif": {"error": str(e)},
                "narratives": []
            }

    def _extract_exif_data(self, image_path: str) -> Dict[str, Any]:
        """Extract EXIF data from an image, including GPS location and capture time."""
        result = {
            "exif": {},
            "location": None,
            "timestamp": None
        }
        
        try:
            # Check if file is HEIC/HEIF
            is_heic = image_path.lower().endswith(('.heic', '.heif'))
            
            # Extract EXIF data
            if is_heic:
                # For HEIC files, we need special handling
                try:
                    heif_file = pillow_heif.read_heif(image_path)
                    # Convert to JPEG for easier processing
                    img = Image.frombytes(
                        heif_file.mode, 
                        heif_file.size, 
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride,
                    )
                    # Extract what we can from the image
                    result["exif"] = {"Format": "HEIC/HEIF"}
                    # We might not get EXIF from HEIC this way, but we tried
                except Exception as e:
                    print(f"Error processing HEIC/HEIF file {image_path}: {str(e)}")
                    result["exif"] = {"Format": "HEIC/HEIF", "Error": str(e)}
            else:
                # For standard formats, use exifread
                with open(image_path, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                    
                    # Convert to a serializable dictionary
                    for tag, value in tags.items():
                        result["exif"][tag] = str(value)
                    
                    # Extract GPS coordinates if available
                    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                        lat = self._convert_to_degrees(tags['GPS GPSLatitude'].values)
                        lon = self._convert_to_degrees(tags['GPS GPSLongitude'].values)
                        
                        # Check for reference direction (N/S, E/W)
                        if 'GPS GPSLatitudeRef' in tags and str(tags['GPS GPSLatitudeRef']) == 'S':
                            lat = -lat
                        if 'GPS GPSLongitudeRef' in tags and str(tags['GPS GPSLongitudeRef']) == 'W':
                            lon = -lon
                        
                        result["location"] = {"latitude": lat, "longitude": lon}
                    
                    # Extract timestamp if available
                    if 'EXIF DateTimeOriginal' in tags:
                        try:
                            date_str = str(tags['EXIF DateTimeOriginal'])
                            # Parse the date string (format typically: "YYYY:MM:DD HH:MM:SS")
                            dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                            result["timestamp"] = dt.timestamp()
                        except Exception as e:
                            print(f"Error parsing date from EXIF: {str(e)}")

            return result
        
        except Exception as e:
            print(f"Error extracting EXIF data from {image_path}: {str(e)}")
            return result
    
    def _convert_to_degrees(self, value: Tuple[Fraction, Fraction, Fraction]) -> float:
        """Helper function to convert GPS coordinates from EXIF to decimal degrees."""
        degrees = float(value[0])
        minutes = float(value[1]) / 60.0
        seconds = float(value[2]) / 3600.0
        return degrees + minutes + seconds
    
    async def _generate_description(self, image_path: str) -> str:
        """Generate a description for an image using OpenAI's Vision API."""
        try:
            # Handle HEIC/HEIF format by converting to JPEG first if needed
            if image_path.lower().endswith(('.heic', '.heif')):
                try:
                    # Open HEIC file and convert to JPEG format for API submission
                    heif_file = pillow_heif.read_heif(image_path)
                    img = Image.frombytes(
                        heif_file.mode, 
                        heif_file.size, 
                        heif_file.data,
                        "raw",
                        heif_file.mode,
                        heif_file.stride,
                    )
                except Exception as e:
                    print(f"Error opening HEIC/HEIF file {image_path}: {str(e)}")
                    return "Could not process HEIC/HEIF image format."
            else:
                # Resize image if needed to reduce API costs
                img = Image.open(image_path)
            
            max_size = 1024  # Max dimension
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            
            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # Call OpenAI API
            response = await openai.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a detailed image analyzer. Describe this image focusing on people, activities, locations, emotions, and any notable elements. Be specific but concise."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in detail, focusing on who is in it, what they're doing, where it is, and the emotional tone."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Error generating description for {image_path}: {str(e)}")
            return "No description available due to an error."
    
    async def process_directory(self, directory_path: str, status_callback=None) -> List[Dict[str, Any]]:
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
        
        # Process photos in batches to avoid overwhelming the system
        batch_size = 5
        all_metadata = []
        
        for i in range(0, len(photo_paths), batch_size):
            batch = photo_paths[i:i+batch_size]
            tasks = [self.process_photo(photo_path) for photo_path in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"Error in batch processing: {str(result)}")
                else:
                    all_metadata.append(result)
            
            processed_photos += len(batch)
            if status_callback:
                status_callback(processed_photos=processed_photos)
        
        return all_metadata 
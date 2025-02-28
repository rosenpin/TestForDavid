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
from openai import AsyncOpenAI
import exifread
import datetime
import pillow_heif
import piexif
import piexif.helper
from fractions import Fraction
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# Configure OpenAI API
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        
        # Track if pillow_heif is working properly
        self.use_pillow_heif = True
    
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
                    # If we've had issues with pillow_heif before, skip directly to PIL
                    if not self.use_pillow_heif:
                        print(f"Skipping pillow_heif for {photo_path}, using PIL directly...")
                        # Create a temporary JPEG file
                        temp_jpeg_path = os.path.join(self.photos_dir, f"{photo_id}_temp.jpg")
                        
                        # Try using PIL directly and preserve EXIF data
                        self._convert_heic_to_jpeg_with_exif(photo_path, temp_jpeg_path)
                        print(f"Successfully converted HEIC/HEIF to JPEG using PIL: {photo_path}")
                        
                        # Update file extension and path for further processing
                        file_extension = '.jpg'
                        photo_path = temp_jpeg_path
                    else:
                        # Try to open the HEIC file to verify it's readable
                        try:
                            heif_file = pillow_heif.read_heif(photo_path)
                            print(f"Successfully verified HEIC/HEIF file: {photo_path}")
                        except Exception as heif_error:
                            # Mark pillow_heif as not working for future files
                            self.use_pillow_heif = False
                            
                            # Try alternative approach - convert to JPEG first
                            print(f"Primary HEIC/HEIF reading failed: {str(heif_error)}, trying fallback...")
                            
                            # Create a temporary JPEG file
                            temp_jpeg_path = os.path.join(self.photos_dir, f"{photo_id}_temp.jpg")
                            
                            # Try using PIL directly and preserve EXIF data
                            self._convert_heic_to_jpeg_with_exif(photo_path, temp_jpeg_path)
                            print(f"Successfully converted HEIC/HEIF to JPEG using PIL: {photo_path}")
                            
                            # Update file extension and path for further processing
                            file_extension = '.jpg'
                            photo_path = temp_jpeg_path
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
            
            # Clean up temporary files if they exist
            if photo_path.endswith('_temp.jpg') and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except Exception as e:
                    print(f"Warning: Could not remove temporary file {photo_path}: {str(e)}")
            
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

    def _convert_heic_to_jpeg_with_exif(self, heic_path: str, jpeg_path: str) -> None:
        """Convert HEIC to JPEG while preserving EXIF data."""
        try:
            # Open the HEIC file
            img = Image.open(heic_path)
            
            # Extract EXIF data from the original file
            exif_dict = None
            
            # Try to extract EXIF data using exifread
            with open(heic_path, 'rb') as f:
                try:
                    tags = exifread.process_file(f, details=False)
                    if tags:
                        # Create a new EXIF dictionary
                        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                        
                        # Map some common EXIF tags
                        if 'EXIF DateTimeOriginal' in tags:
                            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = str(tags['EXIF DateTimeOriginal'])
                        
                        if 'EXIF Make' in tags:
                            exif_dict["0th"][piexif.ImageIFD.Make] = str(tags['EXIF Make'])
                        
                        if 'EXIF Model' in tags:
                            exif_dict["0th"][piexif.ImageIFD.Model] = str(tags['EXIF Model'])
                        
                        # GPS data
                        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                            lat = self._convert_to_degrees(tags['GPS GPSLatitude'].values)
                            lon = self._convert_to_degrees(tags['GPS GPSLongitude'].values)
                            
                            # Check for reference direction (N/S, E/W)
                            if 'GPS GPSLatitudeRef' in tags and str(tags['GPS GPSLatitudeRef']) == 'S':
                                lat = -lat
                            if 'GPS GPSLongitudeRef' in tags and str(tags['GPS GPSLongitudeRef']) == 'W':
                                lon = -lon
                            
                            # Convert to EXIF format
                            lat_deg = int(abs(lat))
                            lat_min = int((abs(lat) - lat_deg) * 60)
                            lat_sec = int(((abs(lat) - lat_deg) * 60 - lat_min) * 60 * 100)
                            
                            lon_deg = int(abs(lon))
                            lon_min = int((abs(lon) - lon_deg) * 60)
                            lon_sec = int(((abs(lon) - lon_deg) * 60 - lon_min) * 60 * 100)
                            
                            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = ((lat_deg, 1), (lat_min, 1), (lat_sec, 100))
                            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = ((lon_deg, 1), (lon_min, 1), (lon_sec, 100))
                            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = 'S' if lat < 0 else 'N'
                            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = 'W' if lon < 0 else 'E'
                except Exception as e:
                    print(f"Warning: Could not extract EXIF data from HEIC: {str(e)}")
            
            # Save as JPEG with EXIF data if available
            if exif_dict:
                try:
                    exif_bytes = piexif.dump(exif_dict)
                    img.save(jpeg_path, format="JPEG", exif=exif_bytes, quality=95)
                except Exception as e:
                    print(f"Warning: Could not save EXIF data to JPEG: {str(e)}")
                    img.save(jpeg_path, format="JPEG", quality=95)
            else:
                img.save(jpeg_path, format="JPEG", quality=95)
                
        except Exception as e:
            print(f"Error converting HEIC to JPEG with EXIF: {str(e)}")
            # Fallback to simple conversion without EXIF
            img = Image.open(heic_path)
            img.save(jpeg_path, format="JPEG", quality=95)

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
                    # If we've had issues with pillow_heif before, skip directly to PIL
                    if not self.use_pillow_heif:
                        print(f"Skipping pillow_heif for EXIF extraction on {image_path}, using PIL directly...")
                        # Try using PIL directly as a fallback
                        img = Image.open(image_path)
                        result["exif"] = {"Format": "HEIC/HEIF (converted)"}
                    else:
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
                        except Exception as heif_error:
                            # Mark pillow_heif as not working for future files
                            self.use_pillow_heif = False
                            
                            # Try using PIL directly as a fallback
                            print(f"HEIC/HEIF reading failed in EXIF extraction: {str(heif_error)}, trying PIL...")
                            img = Image.open(image_path)
                            result["exif"] = {"Format": "HEIC/HEIF (converted)"}
                    
                    # Try to get EXIF from the PIL image
                    if hasattr(img, '_getexif') and img._getexif():
                        exif_data = img._getexif()
                        for tag_id, value in exif_data.items():
                            tag_name = exifread.tags.EXIF_TAGS.get(tag_id, str(tag_id))
                            result["exif"][tag_name] = str(value)
                            
                            # Look for date/time information
                            if tag_name == 'DateTimeOriginal':
                                try:
                                    date_str = str(value)
                                    dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                    result["timestamp"] = dt.timestamp()
                                except Exception as e:
                                    print(f"Error parsing date from EXIF: {str(e)}")
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
                    # If we've had issues with pillow_heif before, skip directly to PIL
                    if not self.use_pillow_heif:
                        print(f"Skipping pillow_heif for description generation on {image_path}, using PIL directly...")
                        # Try using PIL directly as a fallback
                        img = Image.open(image_path)
                    else:
                        # Open HEIC file and convert to JPEG format for API submission
                        try:
                            heif_file = pillow_heif.read_heif(image_path)
                            img = Image.frombytes(
                                heif_file.mode, 
                                heif_file.size, 
                                heif_file.data,
                                "raw",
                                heif_file.mode,
                                heif_file.stride,
                            )
                        except Exception as heif_error:
                            # Mark pillow_heif as not working for future files
                            self.use_pillow_heif = False
                            
                            # Try using PIL directly as a fallback
                            print(f"HEIC/HEIF reading failed in description generation: {str(heif_error)}, trying PIL...")
                            img = Image.open(image_path)
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
            
            # Call OpenAI API using the client
            response = await client.chat.completions.create(
                model="gpt-4o",
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
                max_tokens=500
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
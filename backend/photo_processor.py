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
import reverse_geocode
from fractions import Fraction
from dotenv import load_dotenv
import re

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
    
    async def process_photo(self, photo_path: str) -> Dict[str, Any]:
        """Process a single photo and generate a description using OpenAI."""
        try:
            # Generate a unique ID for the photo
            photo_id = str(uuid.uuid4())
            
            # Get file extension
            file_extension = os.path.splitext(photo_path)[1].lower()
            
            # Extract EXIF data
            exif_data = self._extract_exif_data(photo_path)
            
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
            
            with open(photo_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
                dst_file.write(src_file.read())
            
            # Generate description using OpenAI
            description = await self._generate_description(destination_path)
            
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
                    location_str = self._format_location(exif_data["location"])
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
                "exif": self._ensure_serializable(exif_data.get("exif", {})),
                "narratives": []
            }
            
            # Save metadata
            metadata_path = os.path.join(self.photos_metadata_dir, f"{photo_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Clean up temporary files
            if photo_path.endswith('_temp.jpg') and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except Exception:
                    pass
            
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
            "exif": self._ensure_serializable(exif_data.get("exif", {})),
            "narratives": []
        }

    def _format_location(self, location: Dict[str, Any]) -> str:
        """Format location information into a readable string."""
        if not location:
            return ""
        
        # Check if we have reverse geocoded information
        if "city" in location and location["city"]:
            if location.get("state") and location.get("country"):
                return f"{location['city']}, {location['state']}, {location['country']}"
            elif location.get("country"):
                return f"{location['city']}, {location['country']}"
            else:
                return location['city']
        elif location.get("state") and location.get("country"):
            return f"{location['state']}, {location['country']}"
        elif location.get("country"):
            return location['country']
        
        # Fallback to coordinates
        if "latitude" in location and "longitude" in location:
            return f"Coordinates: {location['latitude']:.6f}, {location['longitude']:.6f}"
        
        return ""

    def _extract_exif_data(self, image_path: str) -> Dict[str, Any]:
        """Extract EXIF data from an image, including GPS location and capture time."""
        result = {
            "exif": {},
            "location": None,
            "timestamp": None
        }
        
        try:
            # Open image with PIL to check for additional EXIF data
            try:
                pil_img = Image.open(image_path)
                pil_exif = pil_img._getexif() or {}
                
                # Extract GPS data from PIL
                if pil_exif:
                    # GPS data is typically in tag 34853
                    gps_info = pil_exif.get(34853)
                    if gps_info and isinstance(gps_info, dict):
                        try:
                            # The standard format uses these keys:
                            # 1: GPSLatitudeRef, 2: GPSLatitude
                            # 3: GPSLongitudeRef, 4: GPSLongitude
                            if 1 in gps_info and 2 in gps_info and 3 in gps_info and 4 in gps_info:
                                lat_ref = gps_info[1]
                                lat_data = gps_info[2]
                                lon_ref = gps_info[3]
                                lon_data = gps_info[4]
                                
                                lat = self._convert_to_degrees(lat_data)
                                lon = self._convert_to_degrees(lon_data)
                                
                                # Apply reference direction
                                if lat_ref == 'S':
                                    lat = -lat
                                if lon_ref == 'W':
                                    lon = -lon
                                
                                result["location"] = {"latitude": lat, "longitude": lon}
                                print(f"Extracted GPS from PIL: {lat}, {lon}")
                        except Exception as e:
                            print(f"Error extracting GPS from PIL: {str(e)}")
            except Exception as e:
                print(f"Error with PIL EXIF extraction: {str(e)}")
            
            # Use exifread for more complete metadata extraction
            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=True)
                
                # Convert to a serializable dictionary
                for tag, value in tags.items():
                    result["exif"][str(tag)] = str(value)
                
                # Extract GPS coordinates if available
                if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                    try:
                        lat = self._convert_to_degrees(tags['GPS GPSLatitude'].values)
                        lon = self._convert_to_degrees(tags['GPS GPSLongitude'].values)
                        
                        # Check for reference direction (N/S, E/W)
                        if 'GPS GPSLatitudeRef' in tags and str(tags['GPS GPSLatitudeRef']) == 'S':
                            lat = -lat
                        if 'GPS GPSLongitudeRef' in tags and str(tags['GPS GPSLongitudeRef']) == 'W':
                            lon = -lon
                        
                        result["location"] = {"latitude": lat, "longitude": lon}
                    except Exception as e:
                        print(f"Error extracting standard GPS: {str(e)}")
                
                # Try to extract GPS data from Samsung-specific tags or other formats
                if not result.get("location"):
                    # Check for Samsung EXIF format or other manufacturer-specific formats
                    for tag_name, tag_value in tags.items():
                        # Look for any tag that might contain GPS data
                        tag_str = str(tag_name).lower()
                        if 'gps' in tag_str or 'location' in tag_str or 'position' in tag_str:
                            print(f"Found potential GPS tag: {tag_name}: {tag_value}")
                
                # Look for XMP GPS data (used by some Samsung and Google phones)
                if not result.get("location"):
                    for tag_name, tag_value in result["exif"].items():
                        if 'xmp' in tag_name.lower():
                            # Look for coordinates in XMP data
                            coords_match = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", str(tag_value))
                            if coords_match:
                                try:
                                    lat = float(coords_match.group(1))
                                    lon = float(coords_match.group(2))
                                    result["location"] = {"latitude": lat, "longitude": lon}
                                    print(f"Extracted GPS from XMP: {lat}, {lon}")
                                    break
                                except Exception:
                                    pass
                
                # Some phones store GPS data in UserComment or MakerNote field
                if not result.get("location"):
                    special_fields = ['EXIF UserComment', 'MakerNote', 'Image ImageDescription']
                    for field in special_fields:
                        if field in tags:
                            field_text = str(tags[field])
                            # Look for coordinates pattern like "51.5074 N, 0.1278 W" or "51.5074, -0.1278"
                            coords_match = re.search(r"(\d+\.\d+)\s*[NS]?\s*[,;]\s*(-?\d+\.\d+|[^,;]+\d+\.\d+)\s*[EW]?", field_text)
                            if coords_match:
                                try:
                                    lat_str = coords_match.group(1)
                                    lon_str = coords_match.group(2)
                                    
                                    # Clean up and convert to float
                                    lat = float(re.search(r"\d+\.\d+", lat_str).group())
                                    lon = float(re.search(r"\d+\.\d+", lon_str).group())
                                    
                                    # Check if we need to negate values based on cardinal directions
                                    if 'S' in field_text and lat > 0:
                                        lat = -lat
                                    if 'W' in field_text and lon > 0:
                                        lon = -lon
                                    
                                    result["location"] = {"latitude": lat, "longitude": lon}
                                    print(f"Extracted GPS from {field}: {lat}, {lon}")
                                    break
                                except Exception as e:
                                    print(f"Error extracting GPS from {field}: {str(e)}")
                
                # Extract timestamp if available
                if 'EXIF DateTimeOriginal' in tags:
                    try:
                        date_str = str(tags['EXIF DateTimeOriginal'])
                        dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        result["timestamp"] = dt.timestamp()
                    except Exception as e:
                        print(f"Error parsing date from EXIF: {str(e)}")
                elif 'Image DateTime' in tags:
                    try:
                        date_str = str(tags['Image DateTime'])
                        dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        result["timestamp"] = dt.timestamp()
                    except Exception as e:
                        print(f"Error parsing date from Image DateTime: {str(e)}")
            
            # Check for additional location data sources if we still don't have location
            if not result.get("location"):
                # Try to extract from the filename (some cameras encode coordinates in filenames)
                filename = os.path.basename(image_path)
                coords_match = re.search(r"(-?\d+\.\d+)[_\s](-?\d+\.\d+)", filename)
                if coords_match:
                    try:
                        lat = float(coords_match.group(1))
                        lon = float(coords_match.group(2))
                        result["location"] = {"latitude": lat, "longitude": lon}
                        print(f"Extracted GPS from filename: {lat}, {lon}")
                    except Exception:
                        pass
            
            return result
        
        except Exception as e:
            print(f"Error extracting EXIF data from {image_path}: {str(e)}")
            return result
    
    def _ensure_serializable(self, data):
        """Ensure that data is JSON serializable."""
        if isinstance(data, dict):
            return {str(k): self._ensure_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._ensure_serializable(item) for item in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # Convert anything else to string
            return str(data)
    
    def _convert_to_degrees(self, value: Tuple[Fraction, Fraction, Fraction]) -> float:
        """Helper function to convert GPS coordinates from EXIF to decimal degrees."""
        try:
            if isinstance(value, tuple) or isinstance(value, list):
                degrees = float(value[0])
                minutes = float(value[1]) / 60.0
                seconds = float(value[2]) / 3600.0
                return degrees + minutes + seconds
            else:
                # Some cameras store coordinates as a single float
                return float(value)
        except (IndexError, ValueError, TypeError) as e:
            print(f"Error converting GPS value {value}: {str(e)}")
            return 0.0
    
    async def _generate_description(self, image_path: str) -> str:
        """Generate a description for an image using OpenAI's Vision API."""
        try:
            # Open and resize image
            img = Image.open(image_path)
            
            # Resize image if needed to reduce API costs
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            
            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # Call OpenAI API
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
        
        return all_metadata 
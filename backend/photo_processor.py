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
import pyheif
import subprocess
from fractions import Fraction
from dotenv import load_dotenv
import reverse_geocode
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
        
        # Track if pillow_heif is working properly
        self.use_pillow_heif = True
        
        # Track if pyheif is working properly
        self.use_pyheif = True
    
    async def process_photo(self, photo_path: str) -> Dict[str, Any]:
        """Process a single photo and generate a description using OpenAI."""
        try:
            # Generate a unique ID for the photo
            photo_id = str(uuid.uuid4())
            
            # Get file extension
            file_extension = os.path.splitext(photo_path)[1].lower()
            
            # Extract EXIF data first (before any conversion)
            exif_data = self._extract_exif_data(photo_path)
            
            # Check if the file is a HEIC/HEIF file and if we should attempt conversion
            if file_extension in ['.heic', '.heif']:
                try:
                    # Create a temporary JPEG file
                    temp_jpeg_path = os.path.join(self.photos_dir, f"{photo_id}_temp.jpg")
                    
                    # Try using PIL directly and preserve EXIF data
                    self._convert_heic_to_jpeg_with_exif(photo_path, temp_jpeg_path, exif_data)
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
                        "timestamp": exif_data.get("timestamp") or os.path.getmtime(photo_path),
                        "location": exif_data.get("location"),
                        "exif": self._ensure_serializable(exif_data.get("exif", {"error": f"Cannot process HEIC/HEIF format: {str(e)}"})),
                        "narratives": []
                    }
            
            # Create a new filename
            new_filename = f"{photo_id}{file_extension}"
            destination_path = os.path.join(self.photos_dir, new_filename)
            
            # Copy the photo to our data directory
            with open(photo_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
                dst_file.write(src_file.read())
            
            # Generate description using OpenAI
            description = await self._generate_description(destination_path)
            
            # Try to extract GPS coordinates from EXIF data if not already extracted
            if not exif_data.get("location"):
                exif_data["location"] = self._extract_gps_from_exif(exif_data["exif"])
                
            # Apply reverse geocoding if we have GPS coordinates
            if exif_data.get("location"):
                try:
                    lat = exif_data["location"]["latitude"]
                    lon = exif_data["location"]["longitude"]
                    
                    # Use reverse_geocode to get location information
                    coordinates = [(lat, lon)]
                    location_result = reverse_geocode.search(coordinates)[0]
                    
                    # Add reverse geocoded information to the location data
                    exif_data["location"].update({
                        "city": location_result.get("city"),
                        "state": location_result.get("state"),
                        "country": location_result.get("country"),
                        "country_code": location_result.get("country_code")
                    })
                    
                    print(f"Reverse geocoded location: {exif_data['location']}")
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

    def _extract_gps_from_exif(self, exif_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract GPS coordinates from EXIF data."""
        try:
            # Look for GPSInfo tag in the EXIF data
            gps_info_key = None
            for key in exif_data:
                if "GPSInfo" in key:
                    gps_info_key = key
                    break
            
            # Method 1: Look for GPS coordinates in ExifTool extracted data first
            for key in exif_data:
                if 'ExifTool_GPSLatitude' in key and 'ExifTool_GPSLongitude' in key:
                    try:
                        lat = float(exif_data['ExifTool_GPSLatitude'])
                        lon = float(exif_data['ExifTool_GPSLongitude'])
                        
                        # Apply reference direction if available
                        if 'ExifTool_GPSLatitudeRef' in exif_data and exif_data['ExifTool_GPSLatitudeRef'] == 'S':
                            lat = -lat
                        if 'ExifTool_GPSLongitudeRef' in exif_data and exif_data['ExifTool_GPSLongitudeRef'] == 'W':
                            lon = -lon
                        
                        print(f"Extracted GPS coordinates from ExifTool data: {lat}, {lon}")
                        return {"latitude": lat, "longitude": lon}
                    except (ValueError, KeyError) as e:
                        print(f"Error extracting GPS from ExifTool data: {str(e)}")
            
            # Method 2: Try to extract from GPSInfo tags (traditional method)
            if gps_info_key:
                gps_data = exif_data[gps_info_key]
                print(f"Processing GPSInfo tag: {gps_info_key} = {gps_data}")
                
                # Try to extract latitude and longitude using regex
                lat_ref = "N"
                lon_ref = "E"
                
                # Look for latitude and longitude reference
                lat_ref_match = re.search(r"GPSLatitudeRef\'\,\)\: \'([NS])\'", str(gps_data))
                lon_ref_match = re.search(r"GPSLongitudeRef\'\,\)\: \'([EW])\'", str(gps_data))
                
                if lat_ref_match:
                    lat_ref = lat_ref_match.group(1)
                if lon_ref_match:
                    lon_ref = lon_ref_match.group(1)
                
                # Look for latitude and longitude values
                lat_match = re.search(r"GPSLatitude\'\,\)\: \((.*?)\)", str(gps_data))
                lon_match = re.search(r"GPSLongitude\'\,\)\: \((.*?)\)", str(gps_data))
                
                if lat_match and lon_match:
                    try:
                        # Parse the latitude and longitude values
                        lat_parts = lat_match.group(1).split(',')
                        lon_parts = lon_match.group(1).split(',')
                        
                        # Convert to decimal degrees
                        lat = 0
                        lon = 0
                        
                        # Handle different formats
                        if len(lat_parts) >= 3:
                            # DMS format
                            lat = float(lat_parts[0]) + float(lat_parts[1])/60 + float(lat_parts[2])/3600
                            lon = float(lon_parts[0]) + float(lon_parts[1])/60 + float(lon_parts[2])/3600
                        elif len(lat_parts) == 1:
                            # Decimal format
                            lat = float(lat_parts[0])
                            lon = float(lon_parts[0])
                        
                        # Apply reference direction
                        if lat_ref == 'S':
                            lat = -lat
                        if lon_ref == 'W':
                            lon = -lon
                        
                        print(f"Extracted GPS coordinates: {lat}, {lon}")
                        return {"latitude": lat, "longitude": lon}
                    except Exception as e:
                        print(f"Error parsing GPS coordinates: {str(e)}")
            
            # Method 3: Try using RegionAppliedToDimensions which might contain GPS info in XMP metadata
            if "RegionAppliedToDimensionsW" in exif_data:
                try:
                    # Look for GPS data in RegionInfo
                    for key in exif_data:
                        if "GPSLatitude" in key and not key.startswith("ExifTool_"):
                            lat_key = key
                            for lon_key in exif_data:
                                if "GPSLongitude" in lon_key and not lon_key.startswith("ExifTool_"):
                                    try:
                                        lat = float(exif_data[lat_key])
                                        lon = float(exif_data[lon_key])
                                        
                                        # Apply reference direction if available
                                        lat_ref_key = next((k for k in exif_data if "GPSLatitudeRef" in k), None)
                                        lon_ref_key = next((k for k in exif_data if "GPSLongitudeRef" in k), None)
                                        
                                        if lat_ref_key and exif_data[lat_ref_key] == "S":
                                            lat = -lat
                                        if lon_ref_key and exif_data[lon_ref_key] == "W":
                                            lon = -lon
                                        
                                        print(f"Extracted GPS coordinates from region info: {lat}, {lon}")
                                        return {"latitude": lat, "longitude": lon}
                                    except Exception as e:
                                        print(f"Error parsing GPS from region info: {str(e)}")
                except Exception as e:
                    print(f"Error checking region info for GPS: {str(e)}")
            
            # Method 4: Parse deeper into the GPSInfo structure using direct dictionary access
            for key, value in exif_data.items():
                if isinstance(value, dict) and "GPS" in str(key):
                    try:
                        gps_dict = value
                        if 1 in gps_dict and 2 in gps_dict and 3 in gps_dict and 4 in gps_dict:
                            lat_ref = gps_dict[1]
                            lat_data = gps_dict[2]
                            lon_ref = gps_dict[3]
                            lon_data = gps_dict[4]
                            
                            # Extract coordinates
                            lat = self._convert_to_degrees(lat_data)
                            lon = self._convert_to_degrees(lon_data)
                            
                            # Apply reference direction
                            if lat_ref == 'S':
                                lat = -lat
                            if lon_ref == 'W':
                                lon = -lon
                            
                            print(f"Extracted GPS coordinates from nested dict: {lat}, {lon}")
                            return {"latitude": lat, "longitude": lon}
                    except Exception as e:
                        print(f"Error extracting GPS from nested dict: {str(e)}")
            
            # Method 5: Check all keys containing "GPS" and try to find latitude/longitude
            gps_keys = [k for k in exif_data.keys() if "GPS" in k]
            for key in gps_keys:
                print(f"Found GPS key: {key} = {exif_data[key]}")
            
            # Look for GPS coordinates in any key containing "GPS"
            lat_value = None
            lon_value = None
            lat_ref = "N"
            lon_ref = "E"
            
            for key in exif_data:
                if "GPSLatitude" in key and not key.startswith("ExifTool_"):
                    try:
                        lat_value = float(exif_data[key])
                    except (ValueError, TypeError):
                        if isinstance(exif_data[key], str):
                            # Try to parse from string format like "(40, 5, 31.718)"
                            try:
                                parts = re.findall(r"\d+\.?\d*", exif_data[key])
                                if len(parts) >= 3:
                                    lat_value = float(parts[0]) + float(parts[1])/60 + float(parts[2])/3600
                            except Exception:
                                pass
            
                if "GPSLongitude" in key and not key.startswith("ExifTool_"):
                    try:
                        lon_value = float(exif_data[key])
                    except (ValueError, TypeError):
                        if isinstance(exif_data[key], str):
                            # Try to parse from string format like "(74, 8, 57.156)"
                            try:
                                parts = re.findall(r"\d+\.?\d*", exif_data[key])
                                if len(parts) >= 3:
                                    lon_value = float(parts[0]) + float(parts[1])/60 + float(parts[2])/3600
                            except Exception:
                                pass
            
                if "GPSLatitudeRef" in key:
                    lat_ref = exif_data[key]
                    if lat_ref == "S":
                        lat_ref = "S"
            
                if "GPSLongitudeRef" in key:
                    lon_ref = exif_data[key]
                    if lon_ref == "W":
                        lon_ref = "W"
            
            if lat_value is not None and lon_value is not None:
                # Apply reference direction
                if lat_ref == "S":
                    lat_value = -lat_value
                if lon_ref == "W":
                    lon_value = -lon_value
                
                print(f"Extracted GPS coordinates from generic keys: {lat_value}, {lon_value}")
                return {"latitude": lat_value, "longitude": lon_value}
            
            # Method 6: Check for GPS data in combined keys or other formats
            for key in exif_data:
                if "GPS" in key and isinstance(exif_data[key], str):
                    gps_str = exif_data[key]
                    
                    # Try to extract coordinates using regex
                    coords_match = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", gps_str)
                    if coords_match:
                        try:
                            lat = float(coords_match.group(1))
                            lon = float(coords_match.group(2))
                            print(f"Extracted GPS coordinates from string: {lat}, {lon}")
                            return {"latitude": lat, "longitude": lon}
                        except Exception as e:
                            print(f"Error parsing GPS coordinates from string: {str(e)}")
            
            # Check if there's a GPSHPositioningError but no actual coordinates
            # This suggests GPS data might be in an unusual format
            if any("GPSHPositioningError" in k for k in exif_data.keys()):
                print("Found GPSHPositioningError but no coordinates. Trying additional extraction methods...")
                
                # Dump all EXIF data to debug
                for key, value in exif_data.items():
                    if "GPS" in key:
                        print(f"GPS-related key: {key} = {value}")
                
                # Special parsing for Apple HEIC files
                if "ExifTool_GPSHPositioningError" in exif_data:
                    # Look for coordinates in the entire EXIF data as a text
                    exif_text = str(exif_data)
                    coords_match = re.search(r"(\d+\.\d+)[,\s]+(-?\d+\.\d+)", exif_text)
                    if coords_match:
                        try:
                            lat = float(coords_match.group(1))
                            lon = float(coords_match.group(2))
                            print(f"Extracted GPS coordinates from EXIF text: {lat}, {lon}")
                            return {"latitude": lat, "longitude": lon}
                        except Exception as e:
                            print(f"Error parsing GPS coordinates from EXIF text: {str(e)}")
            
            # Method 7: Try to extract from Apple-specific metadata in MakerNote
            if "MakerNote" in exif_data and isinstance(exif_data["MakerNote"], str):
                maker_note = exif_data["MakerNote"]
                coords_match = re.search(r"(\d+\.\d+)[,\s]+(-?\d+\.\d+)", maker_note)
                if coords_match:
                    try:
                        lat = float(coords_match.group(1))
                        lon = float(coords_match.group(2))
                        print(f"Extracted GPS coordinates from MakerNote: {lat}, {lon}")
                        return {"latitude": lat, "longitude": lon}
                    except Exception as e:
                        print(f"Error parsing GPS coordinates from MakerNote: {str(e)}")
            
            return None
        except Exception as e:
            print(f"Error in _extract_gps_from_exif: {str(e)}")
            return None

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

    def _convert_heic_to_jpeg_with_exif(self, heic_path: str, jpeg_path: str, exif_data: Dict[str, Any] = None) -> None:
        """Convert HEIC to JPEG while preserving EXIF data."""
        try:
            # Open the HEIC file
            img = Image.open(heic_path)
            
            # Extract EXIF data from the original file if not provided
            exif_dict = None
            
            if exif_data and exif_data.get("exif") and not (len(exif_data["exif"]) == 1 and "Error" in exif_data["exif"]):
                # Create a new EXIF dictionary from the provided data
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                
                # Add timestamp if available
                if exif_data.get("timestamp"):
                    dt = datetime.datetime.fromtimestamp(exif_data["timestamp"])
                    date_str = dt.strftime("%Y:%m:%d %H:%M:%S")
                    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str
                
                # Add GPS data if available
                if exif_data.get("location"):
                    lat = exif_data["location"]["latitude"]
                    lon = exif_data["location"]["longitude"]
                    
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
                # Try multiple methods for HEIC files
                
                # Method 1: Try PIL first (most reliable for conversion)
                try:
                    img = Image.open(image_path)
                    result["exif"]["Format"] = "HEIC/HEIF (PIL)"
                    
                    # Try to get EXIF from the PIL image
                    if hasattr(img, '_getexif') and img._getexif():
                        exif_data = img._getexif()
                        for tag_id, value in exif_data.items():
                            try:
                                tag_name = exifread.tags.EXIF_TAGS.get(tag_id, str(tag_id))
                                result["exif"][str(tag_name)] = str(value)
                                
                                # Look for date/time information
                                if tag_name == 'DateTimeOriginal':
                                    try:
                                        date_str = str(value)
                                        dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                        result["timestamp"] = dt.timestamp()
                                    except Exception as e:
                                        print(f"Error parsing date from EXIF: {str(e)}")
                                
                                # Look for GPS information in PIL EXIF
                                if tag_id == 34853:  # GPSInfo tag
                                    try:
                                        gps_info = value
                                        if isinstance(gps_info, dict):
                                            lat_ref = gps_info.get(1, 'N')  # 1 is GPSLatitudeRef
                                            lat = gps_info.get(2)  # 2 is GPSLatitude
                                            lon_ref = gps_info.get(3, 'E')  # 3 is GPSLongitudeRef
                                            lon = gps_info.get(4)  # 4 is GPSLongitude
                                            
                                            if lat and lon:
                                                lat_value = self._convert_to_degrees(lat)
                                                lon_value = self._convert_to_degrees(lon)
                                                
                                                if lat_ref == 'S':
                                                    lat_value = -lat_value
                                                if lon_ref == 'W':
                                                    lon_value = -lon_value
                                                
                                                result["location"] = {"latitude": lat_value, "longitude": lon_value}
                                                print(f"Found GPS coordinates in PIL EXIF: {lat_value}, {lon_value}")
                                    except Exception as e:
                                        print(f"Error extracting GPS from PIL EXIF: {str(e)}")
                            except Exception as e:
                                print(f"Error processing EXIF tag {tag_id}: {str(e)}")
                except Exception as e:
                    print(f"Error extracting EXIF with PIL from {image_path}: {str(e)}")
                
                # Method 2: Try pyheif if PIL didn't get location data
                if self.use_pyheif and (not result.get("location") or len(result["exif"]) <= 1):
                    try:
                        # Read HEIC file with pyheif
                        heif_file = pyheif.read(image_path)
                        
                        # Extract metadata
                        for metadata in heif_file.metadata or []:
                            if metadata['type'] == 'Exif':
                                # Parse EXIF data
                                exif_data = metadata['data']
                                if exif_data:
                                    # Skip the EXIF header (first 6 bytes)
                                    if exif_data[0:6] == b'Exif\x00\x00':
                                        exif_data = exif_data[6:]
                                    
                                    # Use exifread to parse the EXIF data
                                    from io import BytesIO
                                    tags = exifread.process_file(BytesIO(exif_data), details=False)
                                    
                                    # Convert to a serializable dictionary
                                    for tag, value in tags.items():
                                        result["exif"][str(tag)] = str(value)
                                    
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
                                        print(f"Found GPS coordinates in pyheif EXIF: {lat}, {lon}")
                                    
                                    # Extract timestamp if available
                                    if 'EXIF DateTimeOriginal' in tags:
                                        try:
                                            date_str = str(tags['EXIF DateTimeOriginal'])
                                            # Parse the date string (format typically: "YYYY:MM:DD HH:MM:SS")
                                            dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                            result["timestamp"] = dt.timestamp()
                                        except Exception as e:
                                            print(f"Error parsing date from EXIF: {str(e)}")
                    except Exception as e:
                        print(f"Error processing HEIC/HEIF file with pyheif {image_path}: {str(e)}")
                        self.use_pyheif = False  # Disable pyheif for future files
                
                # Method 3: Try pillow_heif if we still don't have good data
                if self.use_pillow_heif and (not result.get("location") or len(result["exif"]) <= 1):
                    try:
                        heif_file = pillow_heif.read_heif(image_path)
                        # Extract what we can from the image
                        result["exif"]["Format"] = "HEIC/HEIF (pillow_heif)"
                        
                        # Try to extract metadata from pillow_heif
                        if hasattr(heif_file, 'metadata') and heif_file.metadata:
                            for key, value in heif_file.metadata.items():
                                result["exif"][f"HEIF_{key}"] = str(value)
                    except Exception as e:
                        print(f"Error processing HEIC/HEIF file with pillow_heif {image_path}: {str(e)}")
                        self.use_pillow_heif = False  # Disable pillow_heif for future files
                
                # Method 4: Try exiftool as a last resort if available
                if (not result.get("location") or len(result["exif"]) <= 2) and self._is_exiftool_available():
                    try:
                        exiftool_data = self._extract_with_exiftool(image_path)
                        if exiftool_data:
                            # Add exiftool data to our result
                            for key, value in exiftool_data.items():
                                result["exif"][f"ExifTool_{key}"] = str(value)
                            
                            # Try to extract GPS coordinates
                            if 'GPSLatitude' in exiftool_data and 'GPSLongitude' in exiftool_data:
                                try:
                                    lat = float(exiftool_data['GPSLatitude'])
                                    lon = float(exiftool_data['GPSLongitude'])
                                    
                                    # Apply reference direction if available
                                    if 'GPSLatitudeRef' in exiftool_data and exiftool_data['GPSLatitudeRef'] == 'S':
                                        lat = -lat
                                    if 'GPSLongitudeRef' in exiftool_data and exiftool_data['GPSLongitudeRef'] == 'W':
                                        lon = -lon
                                    
                                    result["location"] = {"latitude": lat, "longitude": lon}
                                    print(f"Found GPS coordinates in ExifTool: {lat}, {lon}")
                                except Exception as e:
                                    print(f"Error parsing GPS from ExifTool: {str(e)}")
                            
                            # Special handling for Apple HEIC files with GPSHPositioningError
                            if 'GPSHPositioningError' in exiftool_data and not result.get("location"):
                                print(f"Found GPSHPositioningError in ExifTool data: {exiftool_data['GPSHPositioningError']}")
                                # This indicates GPS data exists but might be in a different format
                                # Dump all GPS-related fields
                                for key, value in exiftool_data.items():
                                    if 'GPS' in key:
                                        print(f"GPS ExifTool data: {key} = {value}")
                            
                            # Try to extract timestamp
                            if 'DateTimeOriginal' in exiftool_data:
                                try:
                                    date_str = exiftool_data['DateTimeOriginal']
                                    # Parse the date string (format typically: "YYYY:MM:DD HH:MM:SS")
                                    dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                    result["timestamp"] = dt.timestamp()
                                except Exception as e:
                                    print(f"Error parsing date from ExifTool: {str(e)}")
                    except Exception as e:
                        print(f"Error using ExifTool on {image_path}: {str(e)}")
                
                # Final attempt: If we still don't have location data, try the enhanced GPS extraction
                if not result.get("location") and result["exif"]:
                    try:
                        result["location"] = self._extract_gps_from_exif(result["exif"])
                        if result["location"]:
                            print(f"Successfully extracted GPS coordinates with enhanced method: {result['location']}")
                    except Exception as e:
                        print(f"Error in final GPS extraction attempt: {str(e)}")
                
                # Method 5: Try to extract GPS from RegionAppliedToDimensions if available
                if not result.get("location") and "ExifTool_RegionAreaX" in result["exif"]:
                    try:
                        # Check if we have GPS data in the XMP metadata
                        if "ExifTool_GPSLatitude" in result["exif"] and "ExifTool_GPSLongitude" in result["exif"]:
                            lat_str = result["exif"]["ExifTool_GPSLatitude"]
                            lon_str = result["exif"]["ExifTool_GPSLongitude"]
                            
                            try:
                                lat = float(lat_str)
                                lon = float(lon_str)
                                
                                # Apply reference direction if available
                                if "ExifTool_GPSLatitudeRef" in result["exif"] and result["exif"]["ExifTool_GPSLatitudeRef"] == "S":
                                    lat = -lat
                                if "ExifTool_GPSLongitudeRef" in result["exif"] and result["exif"]["ExifTool_GPSLongitudeRef"] == "W":
                                    lon = -lon
                                
                                result["location"] = {"latitude": lat, "longitude": lon}
                                print(f"Found GPS coordinates in XMP metadata: {lat}, {lon}")
                            except ValueError:
                                print(f"Could not convert GPS coordinates to float: {lat_str}, {lon_str}")
                    except Exception as e:
                        print(f"Error extracting GPS from XMP metadata: {str(e)}")
                
                # Method 6: Look for GPS data in the raw EXIF dictionary
                if not result.get("location"):
                    try:
                        # Check for GPS data in the raw EXIF dictionary
                        gps_data_key = None
                        for key in result["exif"]:
                            if "GPSInfo" in key and "GPSLatitude" in result["exif"][key]:
                                gps_data_key = key
                                break
                        
                        if gps_data_key:
                            print(f"Found GPS data in raw EXIF: {gps_data_key}")
                            # Try to parse the GPS data
                            gps_data = result["exif"][gps_data_key]
                            # This is a complex string representation, try to extract coordinates
                            import re
                            
                            # Look for latitude and longitude patterns
                            lat_match = re.search(r"GPSLatitude\'\,\)\: \((.*?)\)", gps_data)
                            lon_match = re.search(r"GPSLongitude\'\,\)\: \((.*?)\)", gps_data)
                            lat_ref_match = re.search(r"GPSLatitudeRef\'\,\)\: \'(.*?)\'", gps_data)
                            lon_ref_match = re.search(r"GPSLongitudeRef\'\,\)\: \'(.*?)\'", gps_data)
                            
                            if lat_match and lon_match:
                                try:
                                    # Parse the latitude and longitude values
                                    lat_parts = lat_match.group(1).split(',')
                                    lon_parts = lon_match.group(1).split(',')
                                    
                                    # Convert to decimal degrees
                                    lat = float(lat_parts[0]) + float(lat_parts[1])/60 + float(lat_parts[2])/3600
                                    lon = float(lon_parts[0]) + float(lon_parts[1])/60 + float(lon_parts[2])/3600
                                    
                                    # Apply reference direction
                                    if lat_ref_match and lat_ref_match.group(1) == 'S':
                                        lat = -lat
                                    if lon_ref_match and lon_ref_match.group(1) == 'W':
                                        lon = -lon
                                    
                                    result["location"] = {"latitude": lat, "longitude": lon}
                                    print(f"Extracted GPS coordinates from raw EXIF: {lat}, {lon}")
                                except Exception as e:
                                    print(f"Error parsing GPS coordinates from raw EXIF: {str(e)}")
                    except Exception as e:
                        print(f"Error extracting GPS from raw EXIF: {str(e)}")
                
                # Method 7: Check for GPS data in Apple-specific EXIF tags
                if not result.get("location"):
                    try:
                        # Apple devices often store GPS data in specific tags
                        apple_gps_keys = [
                            "ExifTool_GPSLatitude", "ExifTool_GPSLongitude",
                            "GPSLatitude", "GPSLongitude",
                            "GPS:Latitude", "GPS:Longitude"
                        ]
                        
                        lat = None
                        lon = None
                        lat_ref = "N"
                        lon_ref = "E"
                        
                        for key in result["exif"]:
                            if "GPSLatitudeRef" in key:
                                lat_ref = result["exif"][key]
                            if "GPSLongitudeRef" in key:
                                lon_ref = result["exif"][key]
                        
                        for key in apple_gps_keys:
                            if key in result["exif"]:
                                if "Latitude" in key:
                                    try:
                                        lat = float(result["exif"][key])
                                    except ValueError:
                                        pass
                                elif "Longitude" in key:
                                    try:
                                        lon = float(result["exif"][key])
                                    except ValueError:
                                        pass
                        
                        if lat is not None and lon is not None:
                            # Apply reference direction
                            if lat_ref == "S":
                                lat = -lat
                            if lon_ref == "W":
                                lon = -lon
                            
                            result["location"] = {"latitude": lat, "longitude": lon}
                            print(f"Found GPS coordinates in Apple-specific tags: {lat}, {lon}")
                    except Exception as e:
                        print(f"Error extracting GPS from Apple-specific tags: {str(e)}")
                
                # Method 8: Check for GPS data in the GPSInfo tag (34853)
                if not result.get("location"):
                    try:
                        for key, value in result["exif"].items():
                            if "34853" in key or "GPSInfo" in key:
                                print(f"Found GPSInfo tag: {key} = {value}")
                                # Try to extract GPS data from this tag
                                if isinstance(value, str) and "{" in value and "}" in value:
                                    # This looks like a dictionary representation
                                    gps_dict_str = value.strip()
                                    # Extract values using regex
                                    import re
                                    
                                    # Look for GPS data patterns
                                    lat_ref_match = re.search(r"1: ['\"]([NS])['\"]", gps_dict_str)
                                    lon_ref_match = re.search(r"3: ['\"]([EW])['\"]", gps_dict_str)
                                    lat_match = re.search(r"2: \((.*?)\)", gps_dict_str)
                                    lon_match = re.search(r"4: \((.*?)\)", gps_dict_str)
                                    
                                    if lat_match and lon_match:
                                        try:
                                            # Parse latitude and longitude values
                                            lat_parts = lat_match.group(1).split(',')
                                            lon_parts = lon_match.group(1).split(',')
                                            
                                            # Convert to decimal degrees
                                            lat = 0
                                            lon = 0
                                            
                                            # Handle different formats
                                            if len(lat_parts) >= 3:
                                                # DMS format
                                                lat = float(lat_parts[0]) + float(lat_parts[1])/60 + float(lat_parts[2])/3600
                                                lon = float(lon_parts[0]) + float(lon_parts[1])/60 + float(lon_parts[2])/3600
                                            elif len(lat_parts) == 1:
                                                # Decimal format
                                                lat = float(lat_parts[0])
                                                lon = float(lon_parts[0])
                                            
                                            # Apply reference direction
                                            if lat_ref_match and lat_ref_match.group(1) == 'S':
                                                lat = -lat
                                            if lon_ref_match and lon_ref_match.group(1) == 'W':
                                                lon = -lon
                                            
                                            result["location"] = {"latitude": lat, "longitude": lon}
                                            print(f"Extracted GPS coordinates from GPSInfo tag: {lat}, {lon}")
                                        except Exception as e:
                                            print(f"Error parsing GPS coordinates from GPSInfo tag: {str(e)}")
                    except Exception as e:
                        print(f"Error extracting GPS from GPSInfo tag: {str(e)}")
                
                # Method 9: Try to extract GPS from ExifTool_GPSLatitude and ExifTool_GPSLongitude
                if not result.get("location"):
                    try:
                        if "ExifTool_GPSLatitude" in result["exif"] and "ExifTool_GPSLongitude" in result["exif"]:
                            try:
                                lat = float(result["exif"]["ExifTool_GPSLatitude"])
                                lon = float(result["exif"]["ExifTool_GPSLongitude"])
                                
                                # Apply reference direction if available
                                if "ExifTool_GPSLatitudeRef" in result["exif"] and result["exif"]["ExifTool_GPSLatitudeRef"] == "S":
                                    lat = -lat
                                if "ExifTool_GPSLongitudeRef" in result["exif"] and result["exif"]["ExifTool_GPSLongitudeRef"] == "W":
                                    lon = -lon
                                
                                result["location"] = {"latitude": lat, "longitude": lon}
                                print(f"Found GPS coordinates in ExifTool tags: {lat}, {lon}")
                            except ValueError:
                                print(f"Could not convert ExifTool GPS coordinates to float")
                    except Exception as e:
                        print(f"Error extracting GPS from ExifTool tags: {str(e)}")
            else:
                # For standard formats, use exifread
                with open(image_path, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                    
                    # Convert to a serializable dictionary
                    for tag, value in tags.items():
                        result["exif"][str(tag)] = str(value)
                    
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
                        print(f"Found GPS coordinates in standard format: {lat}, {lon}")
                    
                    # Extract timestamp if available
                    if 'EXIF DateTimeOriginal' in tags:
                        try:
                            date_str = str(tags['EXIF DateTimeOriginal'])
                            # Parse the date string (format typically: "YYYY:MM:DD HH:MM:SS")
                            dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                            result["timestamp"] = dt.timestamp()
                        except Exception as e:
                            print(f"Error parsing date from EXIF: {str(e)}")

            # Ensure all keys in the exif dictionary are strings
            result["exif"] = self._ensure_serializable(result["exif"])
            return result
        
        except Exception as e:
            print(f"Error extracting EXIF data from {image_path}: {str(e)}")
            return result
    
    def _is_exiftool_available(self) -> bool:
        """Check if ExifTool is available on the system."""
        try:
            result = subprocess.run(['exiftool', '-ver'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True, 
                                   check=False)
            return result.returncode == 0
        except Exception:
            return False
    
    def _extract_with_exiftool(self, image_path: str) -> Dict[str, Any]:
        """Extract metadata using ExifTool."""
        try:
            # Run ExifTool with JSON output and numeric values
            result = subprocess.run(['exiftool', '-j', '-n', image_path], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True, 
                                   check=False)
            
            if result.returncode == 0 and result.stdout:
                # Parse JSON output
                import json
                data = json.loads(result.stdout)
                if data and isinstance(data, list) and len(data) > 0:
                    base_data = data[0]
                    
                    # If we have GPSHPositioningError but no GPS coordinates, 
                    # specifically request GPS coordinates
                    if 'GPSHPositioningError' in base_data and (
                        'GPSLatitude' not in base_data or 'GPSLongitude' not in base_data):
                        print("GPS data might be present but not extracted. Trying specific GPS extraction...")
                        
                        # Request specific GPS fields using exiftool
                        gps_result = subprocess.run(
                            ['exiftool', '-j', '-n', '-GPSLatitude', '-GPSLongitude', 
                             '-GPSLatitudeRef', '-GPSLongitudeRef', '-coordFormat', '%d.%d', image_path],
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, 
                            text=True, 
                            check=False
                        )
                        
                        if gps_result.returncode == 0 and gps_result.stdout:
                            try:
                                gps_data = json.loads(gps_result.stdout)
                                if gps_data and isinstance(gps_data, list) and len(gps_data) > 0:
                                    # Merge GPS data with base data
                                    for key, value in gps_data[0].items():
                                        if key not in base_data and key != 'SourceFile':
                                            base_data[key] = value
                                    
                                    print(f"Additional GPS data extracted: {gps_data[0]}")
                            except Exception as e:
                                print(f"Error parsing additional GPS data: {str(e)}")
                    
                    return base_data
            
            return {}
        except Exception as e:
            print(f"Error running ExifTool: {str(e)}")
            return {}
    
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
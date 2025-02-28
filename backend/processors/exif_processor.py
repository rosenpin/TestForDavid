import os
import exifread
import datetime
import re
from PIL import Image
from fractions import Fraction
from typing import Dict, Any, Tuple, List

class ExifProcessor:
    def __init__(self):
        """Initialize the EXIF processor."""
        pass

    def extract_exif_data(self, image_path: str) -> Dict[str, Any]:
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
    
    def format_location(self, location: Dict[str, Any]) -> str:
        """Format location information into a readable string."""
        if not location:
            return ""
        
        # Check if we have the formatted location already
        if location.get("formatted"):
            return location["formatted"]
        
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
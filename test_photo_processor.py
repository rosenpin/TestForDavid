import asyncio
import sys
import os
from pathlib import Path
import json

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from photo_processor import PhotoProcessor
import exifread
from PIL import Image
import piexif

# Additional debug function to directly check GPS tags with multiple methods
def debug_exif_gps(image_path):
    print(f"\n--- Debugging GPS data for: {image_path} ---")
    
    # Method 1: Using exifread
    try:
        print("\nMethod 1: Using exifread")
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=True)
            
            # Check for GPS tags
            gps_tags = {tag: value for tag, value in tags.items() if 'GPS' in tag}
            if gps_tags:
                print(f"Found {len(gps_tags)} GPS tags:")
                for tag, value in gps_tags.items():
                    print(f"  {tag}: {value}")
                
                # Check for the critical latitude and longitude tags
                if 'GPS GPSLatitude' in gps_tags and 'GPS GPSLongitude' in gps_tags:
                    print("  Found latitude and longitude tags")
                    print(f"  Latitude values: {gps_tags['GPS GPSLatitude'].values}")
                    print(f"  Longitude values: {gps_tags['GPS GPSLongitude'].values}")
                else:
                    print("  Missing latitude or longitude tags")
            else:
                print("  No GPS tags found via exifread")
    except Exception as e:
        print(f"  Error with exifread: {str(e)}")
    
    # Method 2: Using PIL/Pillow
    try:
        print("\nMethod 2: Using PIL/Pillow")
        img = Image.open(image_path)
        exif_data = img._getexif()
        
        if exif_data:
            # GPS data is typically in tag 34853
            gps_info = exif_data.get(34853)
            if gps_info and isinstance(gps_info, dict):
                print("  Found GPS info in PIL EXIF:")
                for key, value in gps_info.items():
                    print(f"  Tag {key}: {value}")
                
                # Check for latitude and longitude
                if 1 in gps_info and 2 in gps_info and 3 in gps_info and 4 in gps_info:
                    print("  Found latitude and longitude")
                    print(f"  Latitude ref: {gps_info[1]}, values: {gps_info[2]}")
                    print(f"  Longitude ref: {gps_info[3]}, values: {gps_info[4]}")
                else:
                    print("  Missing complete lat/long data")
            else:
                print("  No GPS info found in PIL EXIF")
        else:
            print("  No EXIF data found via PIL")
    except Exception as e:
        print(f"  Error with PIL: {str(e)}")
    
    # Method 3: Using piexif
    try:
        print("\nMethod 3: Using piexif")
        exif_dict = piexif.load(image_path)
        
        if "GPS" in exif_dict and exif_dict["GPS"]:
            print("  Found GPS data via piexif:")
            for tag, value in exif_dict["GPS"].items():
                tag_str = str(tag)
                # Convert byte strings to readable form
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8')
                    except:
                        value = str(value)
                print(f"  Tag {tag_str}: {value}")
            
            # Check for latitude and longitude (tags 2 and 4)
            if 2 in exif_dict["GPS"] and 4 in exif_dict["GPS"]:
                print("  Found latitude and longitude")
                print(f"  Latitude values: {exif_dict['GPS'][2]}")
                print(f"  Longitude values: {exif_dict['GPS'][4]}")
            else:
                print("  Missing latitude or longitude tags")
        else:
            print("  No GPS data found via piexif")
    except Exception as e:
        print(f"  Error with piexif: {str(e)}")
    
    print("----------------------------------------")

async def test_exif(path='../test_photos'):
    processor = PhotoProcessor()
    
    # Look for a few sample image files
    image_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
                image_files.append(os.path.join(root, file))
                if len(image_files) >= 3:  # Just check a few sample files
                    break
        if len(image_files) >= 3:
            break
    
    # Debug some sample images
    for image_path in image_files:
        debug_exif_gps(image_path)
    
    # Process all photos
    results = await processor.process_directory(path)
    print(f"\nProcessed {len(results)} photos")
    
    # Print summary of results
    photos_with_location = [p for p in results if p.get("location")]
    print(f"Photos with location data: {len(photos_with_location)}/{len(results)}")
    
    # Print location data for the first 5 photos that have it
    for i, photo in enumerate(photos_with_location[:5]):
        print(f"Photo with location {i+1}: {photo['location']}")
    
    # Save detailed results to a file for inspection
    with open("photo_processing_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to photo_processing_results.json")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_exif()) 
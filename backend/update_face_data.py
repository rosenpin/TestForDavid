import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from tqdm import tqdm
import argparse

from processors.face_processor import FaceProcessor
from processors.photo_processor import ensure_directory

async def update_photos_with_face_data(
    data_dir: str = "data", 
    status_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """Update existing photo metadata files with face detection and recognition data.
    
    Args:
        data_dir: Directory containing photos and metadata
        status_callback: Optional callback for status updates
        
    Returns:
        Dict with statistics about the update process
    """
    # Set up directories
    photos_dir = os.path.join(data_dir, "photos")
    metadata_dir = os.path.join(data_dir, "metadata")
    photos_metadata_dir = os.path.join(metadata_dir, "photos")
    faces_dir = os.path.join(data_dir, "faces")
    
    # Create necessary directories
    for dir_path in [photos_dir, metadata_dir, photos_metadata_dir, faces_dir]:
        ensure_directory(dir_path)
    
    # Initialize face processor
    face_processor = FaceProcessor(faces_dir, metadata_dir)
    
    # Get all metadata files
    metadata_files = [f for f in os.listdir(photos_metadata_dir) if f.endswith('.json')]
    
    if status_callback:
        status_callback(
            current_stage="detecting_faces",
            total_photos=len(metadata_files),
            processed_photos=0
        )
    
    # Stats
    stats = {
        "total": len(metadata_files),
        "processed": 0,
        "faces_detected": 0,
        "photos_with_faces": 0,
        "errors": 0,
        "skipped": 0
    }
    
    # Process each metadata file to detect faces
    for i, metadata_file in enumerate(tqdm(metadata_files, desc="Detecting faces")):
        try:
            # Read metadata
            metadata_path = os.path.join(photos_metadata_dir, metadata_file)
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Skip if already has faces data
            if metadata.get('faces') and len(metadata['faces']) > 0:
                stats["skipped"] += 1
                continue
                
            # Get photo path
            photo_id = metadata['id']
            filename = metadata['filename']
            photo_path = os.path.join(photos_dir, filename)
            
            # Check if photo exists
            if not os.path.exists(photo_path):
                # Try with common extensions
                extensions = ['.jpg', '.jpeg', '.png']
                found = False
                for ext in extensions:
                    test_path = os.path.join(photos_dir, f"{filename}{ext}")
                    if os.path.exists(test_path):
                        photo_path = test_path
                        found = True
                        break
                
                # If still not found, try using photo_id as filename
                if not found:
                    for ext in extensions:
                        test_path = os.path.join(photos_dir, f"{photo_id}{ext}")
                        if os.path.exists(test_path):
                            photo_path = test_path
                            found = True
                            break
                
                if not found:
                    print(f"Photo not found: {filename} (ID: {photo_id})")
                    stats["errors"] += 1
                    continue
            
            # Process faces in the photo
            faces_data = await face_processor.process_faces(photo_path, photo_id)
            
            # Update metadata with face data
            if faces_data:
                metadata['faces'] = faces_data
                stats["faces_detected"] += len(faces_data)
                stats["photos_with_faces"] += 1
            else:
                metadata['faces'] = []
            
            # Save updated metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            stats["processed"] += 1
            
            # Update status
            if status_callback:
                status_callback(
                    processed_photos=i + 1,
                    faces_detected=stats["faces_detected"]
                )
                
        except Exception as e:
            print(f"Error processing {metadata_file}: {str(e)}")
            stats["errors"] += 1
    
    # After processing all photos, cluster faces to identify persons
    if status_callback:
        status_callback(
            current_stage="clustering_faces"
        )
    
    try:
        # Cluster faces to identify unique persons
        print("Clustering faces to identify unique persons...")
        person_clusters = await face_processor.cluster_faces()
        
        # Update photos with person IDs
        print("Updating photos with person IDs...")
        person_stats = await face_processor.update_photos_with_person_ids(person_clusters, photos_metadata_dir)
        
        # Add person stats to the overall stats
        stats["unique_persons"] = len(person_clusters)
        stats["person_stats"] = {
            person_id: {
                "face_count": person_info.get("face_count", 0),
                "photo_count": person_info.get("photo_count", 0)
            }
            for person_id, person_info in person_stats.items()
        }
    except Exception as e:
        print(f"Error during face clustering: {str(e)}")
        stats["clustering_error"] = str(e)
    
    if status_callback:
        status_callback(
            current_stage="face_processing_complete",
            stats=stats
        )
    
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update existing photo metadata with face detection and recognition")
    parser.add_argument("--data-dir", default="data", help="Directory containing photos and metadata")
    args = parser.parse_args()
    
    loop = asyncio.get_event_loop()
    stats = loop.run_until_complete(update_photos_with_face_data(args.data_dir))
    
    print("Face Detection and Recognition Update Complete:")
    print(f"Total files: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Photos with faces: {stats['photos_with_faces']}")
    print(f"Total faces detected: {stats['faces_detected']}")
    print(f"Unique persons identified: {stats.get('unique_persons', 0)}")
    print(f"Skipped (already had face data): {stats['skipped']}")
    print(f"Errors: {stats['errors']}") 
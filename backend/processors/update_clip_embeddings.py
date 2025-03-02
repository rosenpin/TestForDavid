import os
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from tqdm import tqdm
import argparse

from .clip_processor import ClipProcessor
from .photo_processor import ensure_directory

async def update_photos_with_clip_embeddings(
    data_dir: str = "data", 
    status_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """Update existing photo metadata files with CLIP embeddings.
    
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
    
    # Check if directories exist
    for dir_path in [photos_dir, metadata_dir, photos_metadata_dir]:
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"Directory not found: {dir_path}")
    
    # Initialize CLIP processor
    clip_processor = ClipProcessor()
    
    # Get all metadata files
    metadata_files = [f for f in os.listdir(photos_metadata_dir) if f.endswith('.json')]
    
    if status_callback:
        status_callback(
            current_stage="adding_clip_embeddings",
            total_photos=len(metadata_files),
            processed_photos=0
        )
    
    # Stats
    stats = {
        "total": len(metadata_files),
        "processed": 0,
        "errors": 0,
        "skipped": 0
    }
    
    # Process each metadata file
    for i, metadata_file in enumerate(tqdm(metadata_files, desc="Processing CLIP embeddings")):
        try:
            # Read metadata
            metadata_path = os.path.join(photos_metadata_dir, metadata_file)
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Skip if clip_data already exists and has embeddings
            if metadata.get('clip_data') and metadata['clip_data'].get('embedding'):
                stats["skipped"] += 1
                continue
                
            # Get photo path
            photo_id = metadata['id']
            filename = metadata['filename']
            photo_path = os.path.join(photos_dir, filename)
            
            # Check if photo exists
            if not os.path.exists(photo_path):
                print(f"Photo not found: {photo_path}")
                stats["errors"] += 1
                continue
            
            # Generate CLIP embeddings
            clip_data = clip_processor.process_image(photo_path)
            
            # Update metadata
            metadata['clip_data'] = clip_data
            
            # Save updated metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            stats["processed"] += 1
            
            # Update status
            if status_callback:
                status_callback(
                    processed_photos=i + 1
                )
                
        except Exception as e:
            print(f"Error processing {metadata_file}: {str(e)}")
            stats["errors"] += 1
    
    if status_callback:
        status_callback(
            current_stage="clip_embeddings_complete",
            stats=stats
        )
    
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update existing photo metadata with CLIP embeddings")
    parser.add_argument("--data-dir", default="data", help="Directory containing photos and metadata")
    args = parser.parse_args()
    
    loop = asyncio.get_event_loop()
    stats = loop.run_until_complete(update_photos_with_clip_embeddings(args.data_dir))
    
    print(f"CLIP Embeddings Update Complete:")
    print(f"Total files: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Skipped (already had embeddings): {stats['skipped']}")
    print(f"Errors: {stats['errors']}") 
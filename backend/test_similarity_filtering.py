#!/usr/bin/env python3
"""
Script to test CLIP-based similarity filtering.
This script demonstrates how the CLIP embeddings are used to filter out similar images.
"""

import os
import json
import argparse
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def compute_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Calculate cosine similarity between two CLIP embeddings."""
    if not embedding1 or not embedding2:
        return 0.0
    
    # Convert to numpy arrays
    a = np.array(embedding1)
    b = np.array(embedding2)
    
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(similarity)

def find_similar_photos(
    data_dir: str, 
    similarity_threshold: float = 0.85,
    save_results: bool = True
) -> Dict[str, List[Tuple[str, float]]]:
    """Find similar photos in the dataset using CLIP embeddings.
    
    Args:
        data_dir: Data directory
        similarity_threshold: Threshold above which photos are considered similar
        save_results: Whether to save the results to a file
        
    Returns:
        Dictionary mapping photo IDs to lists of similar photos (with similarity scores)
    """
    # Set up paths
    metadata_dir = os.path.join(data_dir, "metadata")
    photos_metadata_dir = os.path.join(metadata_dir, "photos")
    photos_dir = os.path.join(data_dir, "photos")
    
    # Check if directory exists
    if not os.path.exists(photos_metadata_dir):
        logger.error(f"Photos metadata directory not found: {photos_metadata_dir}")
        return {}
    
    # Load all photo metadata
    photos_data = {}
    for filename in os.listdir(photos_metadata_dir):
        if filename.endswith(".json"):
            photo_id = os.path.splitext(filename)[0]
            file_path = os.path.join(photos_metadata_dir, filename)
            try:
                with open(file_path, "r") as f:
                    photo_data = json.load(f)
                photos_data[photo_id] = photo_data
            except Exception as e:
                logger.warning(f"Error loading metadata for {filename}: {str(e)}")
    
    logger.info(f"Loaded metadata for {len(photos_data)} photos")
    
    # Extract photos with CLIP embeddings
    photos_with_embeddings = {}
    for photo_id, photo_data in photos_data.items():
        if photo_data.get("clip_data") and photo_data["clip_data"].get("embedding"):
            # Get full image path
            image_filename = photo_data.get("filename")
            image_path = os.path.join(photos_dir, image_filename) if image_filename else None
            
            photos_with_embeddings[photo_id] = {
                "embedding": photo_data["clip_data"]["embedding"],
                "description": photo_data.get("description", "No description"),
                "filename": image_filename,
                "full_path": image_path,
                "timestamp": photo_data.get("timestamp", 0)
            }
    
    logger.info(f"Found {len(photos_with_embeddings)} photos with CLIP embeddings")
    
    # Print a line separator for readability
    print("\n" + "="*80)
    print("FINDING SIMILAR PHOTOS BASED ON CLIP EMBEDDINGS")
    print("="*80 + "\n")
    
    # Find similar photos
    similar_photos = {}
    for photo_id, photo_info in photos_with_embeddings.items():
        similar = []
        for other_id, other_info in photos_with_embeddings.items():
            if photo_id == other_id:
                continue
                
            similarity = compute_similarity(photo_info["embedding"], other_info["embedding"])
            if similarity >= similarity_threshold:
                similar.append((other_id, similarity))
        
        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)
        
        # Only store if we found similar photos
        if similar:
            similar_photos[photo_id] = similar
            
            # Print details about this set of similar photos
            print(f"\nREFERENCE IMAGE: {photo_info['full_path']}")
            print(f"Description: {photo_info['description']}")
            print("\nSimilar images:")
            
            for i, (similar_id, score) in enumerate(similar, 1):
                similar_info = photos_with_embeddings[similar_id]
                print(f"  {i}. {similar_info['full_path']} (similarity: {score:.4f})")
                print(f"     Description: {similar_info['description']}")
            
            print("-" * 80)
    
    logger.info(f"Found {len(similar_photos)} photos with similar matches")
    
    # Save results to file if requested
    if save_results and similar_photos:
        results_dir = os.path.join(data_dir, "results")
        os.makedirs(results_dir, exist_ok=True)
        results_path = os.path.join(results_dir, "similar_photos.json")
        
        # Create a more detailed report
        report = {}
        for photo_id, similars in similar_photos.items():
            photo_info = photos_with_embeddings[photo_id]
            similar_details = []
            
            for similar_id, score in similars:
                similar_info = photos_with_embeddings[similar_id]
                similar_details.append({
                    "id": similar_id,
                    "similarity": score,
                    "description": similar_info["description"],
                    "filename": similar_info["filename"],
                    "full_path": similar_info["full_path"]
                })
            
            report[photo_id] = {
                "description": photo_info["description"],
                "filename": photo_info["filename"],
                "full_path": photo_info["full_path"],
                "similar_photos": similar_details
            }
        
        # Save the report
        with open(results_path, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Saved similar photos report to {results_path}")
        
        # Generate a human-readable version that's easier to use
        human_readable_path = os.path.join(results_dir, "similar_photos_report.txt")
        with open(human_readable_path, "w") as f:
            f.write("SIMILAR PHOTOS REPORT\n")
            f.write("====================\n\n")
            
            for photo_id, data in report.items():
                f.write(f"REFERENCE IMAGE: {data['full_path']}\n")
                f.write(f"Description: {data['description']}\n")
                f.write("\nSIMILAR IMAGES:\n")
                
                for i, similar in enumerate(data['similar_photos'], 1):
                    f.write(f"{i}. {similar['full_path']} (similarity: {similar['similarity']:.4f})\n")
                    f.write(f"   Description: {similar['description']}\n")
                
                f.write("\n" + "="*70 + "\n\n")
        
        logger.info(f"Saved human-readable report to {human_readable_path}")
    
    return similar_photos

def demonstrate_filtering(
    data_dir: str,
    similarity_threshold: float = 0.85,
    max_photos: Optional[int] = None
) -> Dict[str, Any]:
    """Demonstrate the photo filtering for narratives.
    
    Args:
        data_dir: Data directory
        similarity_threshold: Threshold for similarity filtering
        max_photos: Maximum number of photos to include
        
    Returns:
        Dictionary with the filtering results
    """
    # Set up paths
    metadata_dir = os.path.join(data_dir, "metadata")
    photos_metadata_dir = os.path.join(metadata_dir, "photos")
    photos_dir = os.path.join(data_dir, "photos")
    
    # Get all photo IDs
    photo_ids = [os.path.splitext(f)[0] for f in os.listdir(photos_metadata_dir) if f.endswith(".json")]
    
    # Load metadata for all photos
    photos_metadata = {}
    for photo_id in photo_ids:
        file_path = os.path.join(photos_metadata_dir, f"{photo_id}.json")
        try:
            with open(file_path, "r") as f:
                photo_data = json.load(f)
            photos_metadata[photo_id] = photo_data
        except Exception as e:
            logger.warning(f"Error loading metadata for {photo_id}: {str(e)}")
    
    # Check which photos have CLIP embeddings
    photos_with_embeddings = {
        pid: data for pid, data in photos_metadata.items() 
        if data.get("clip_data") and data["clip_data"].get("embedding")
    }
    
    # Create a list of (photo_id, embedding) pairs
    candidates = [
        (pid, data["clip_data"]["embedding"]) 
        for pid, data in photos_with_embeddings.items()
    ]
    
    # Sort by timestamp if available
    try:
        candidates.sort(key=lambda x: photos_metadata[x[0]].get("timestamp", 0))
    except Exception as e:
        logger.warning(f"Error sorting by timestamp: {str(e)}")
    
    # Get full paths for all photos
    def get_image_path(photo_id):
        image_filename = photos_metadata[photo_id].get("filename")
        return os.path.join(photos_dir, image_filename) if image_filename else None
    
    # Print a line separator for readability
    print("\n" + "="*80)
    print("FILTERING DEMONSTRATION")
    print("="*80 + "\n")
    print(f"Total photos: {len(photo_ids)}")
    print(f"Photos with CLIP embeddings: {len(photos_with_embeddings)}")
    print(f"Similarity threshold: {similarity_threshold}")
    if max_photos:
        print(f"Maximum photos to select: {max_photos}")
    print("\n")
    
    # Filter photos
    filtered_ids = []
    excluded_ids = []
    exclusion_reasons = {}
    
    # Start with the first photo
    if candidates:
        first_id = candidates[0][0]
        filtered_ids.append(first_id)
        
        print(f"Selected first photo: {get_image_path(first_id)}")
        print(f"Description: {photos_metadata[first_id].get('description', 'No description')}")
        print("\n")
        
        # Filter remaining photos
        for candidate_id, candidate_embedding in candidates[1:]:
            # Stop if we've reached max photos
            if max_photos is not None and len(filtered_ids) >= max_photos:
                reason = "Max photos limit reached"
                excluded_ids.append(candidate_id)
                exclusion_reasons[candidate_id] = reason
                print(f"Excluding: {get_image_path(candidate_id)}")
                print(f"Reason: {reason}")
                print("")
                continue
                
            # Check if this photo is too similar to any already selected photo
            too_similar = False
            for selected_id in filtered_ids:
                selected_embedding = photos_metadata[selected_id]["clip_data"]["embedding"]
                similarity = compute_similarity(candidate_embedding, selected_embedding)
                
                if similarity > similarity_threshold:
                    too_similar = True
                    reason = f"Too similar to {get_image_path(selected_id)} (similarity: {similarity:.4f})"
                    excluded_ids.append(candidate_id)
                    exclusion_reasons[candidate_id] = reason
                    print(f"Excluding: {get_image_path(candidate_id)}")
                    print(f"Reason: {reason}")
                    print("")
                    break
            
            # Add to filtered list if not too similar
            if not too_similar:
                filtered_ids.append(candidate_id)
                print(f"Selected: {get_image_path(candidate_id)}")
                print(f"Description: {photos_metadata[candidate_id].get('description', 'No description')}")
                print("")
    
    # Print summary
    print("\nFINAL SELECTIONS:")
    print("================")
    for i, pid in enumerate(filtered_ids, 1):
        print(f"{i}. {get_image_path(pid)}")
    
    # Create a report
    report = {
        "total_photos": len(photo_ids),
        "photos_with_embeddings": len(photos_with_embeddings),
        "filtered_photos_count": len(filtered_ids),
        "excluded_photos_count": len(excluded_ids),
        "similarity_threshold": similarity_threshold,
        "filtered_photos": [
            {
                "id": pid, 
                "filename": photos_metadata[pid].get("filename", "Unknown"),
                "full_path": get_image_path(pid),
                "description": photos_metadata[pid].get("description", "No description")
            } 
            for pid in filtered_ids
        ],
        "excluded_photos": [
            {
                "id": pid, 
                "filename": photos_metadata[pid].get("filename", "Unknown"),
                "full_path": get_image_path(pid),
                "description": photos_metadata[pid].get("description", "No description"),
                "reason": exclusion_reasons.get(pid, "Unknown")
            } 
            for pid in excluded_ids
        ]
    }
    
    # Save the report
    results_dir = os.path.join(data_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    report_path = os.path.join(results_dir, "filtering_demonstration.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Generate a human-readable version
    human_readable_path = os.path.join(results_dir, "filtering_report.txt")
    with open(human_readable_path, "w") as f:
        f.write("FILTERING DEMONSTRATION REPORT\n")
        f.write("=============================\n\n")
        f.write(f"Total photos: {len(photo_ids)}\n")
        f.write(f"Photos with CLIP embeddings: {len(photos_with_embeddings)}\n")
        f.write(f"Similarity threshold: {similarity_threshold}\n")
        f.write(f"Included photos: {len(filtered_ids)}\n")
        f.write(f"Excluded photos: {len(excluded_ids)}\n\n")
        
        f.write("INCLUDED PHOTOS:\n")
        f.write("---------------\n")
        for i, pid in enumerate(filtered_ids, 1):
            path = get_image_path(pid)
            f.write(f"{i}. {path}\n")
            f.write(f"   Description: {photos_metadata[pid].get('description', 'No description')}\n\n")
        
        f.write("\nEXCLUDED PHOTOS:\n")
        f.write("---------------\n")
        for i, pid in enumerate(excluded_ids, 1):
            path = get_image_path(pid)
            f.write(f"{i}. {path}\n")
            f.write(f"   Description: {photos_metadata[pid].get('description', 'No description')}\n")
            f.write(f"   Reason: {exclusion_reasons.get(pid, 'Unknown')}\n\n")
    
    logger.info(f"Filtered photos: {len(filtered_ids)} out of {len(photos_with_embeddings)}")
    logger.info(f"Saved filtering demonstration report to {report_path}")
    logger.info(f"Saved human-readable report to {human_readable_path}")
    
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test CLIP-based similarity filtering")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--mode", choices=["similar", "filter"], default="filter", 
                      help="Mode: 'similar' to find similar photos, 'filter' to demonstrate filtering")
    parser.add_argument("--threshold", type=float, default=0.85, 
                      help="Similarity threshold (0-1, higher means more strict filtering)")
    parser.add_argument("--max-photos", type=int, default=None,
                      help="Maximum number of photos to include in filtering demo")
    
    args = parser.parse_args()
    
    if args.mode == "similar":
        find_similar_photos(args.data_dir, args.threshold)
    else:
        demonstrate_filtering(args.data_dir, args.threshold, args.max_photos) 
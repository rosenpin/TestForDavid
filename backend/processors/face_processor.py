import os
import json
import numpy as np
import face_recognition
from PIL import Image
from sklearn.cluster import DBSCAN
from typing import Dict, List, Any, Tuple

# Directly include needed functions instead of importing
def save_json(data: Dict[str, Any], file_path: str) -> None:
    """Save data as JSON to the specified file path."""
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON data from the specified file path."""
    with open(file_path, "r") as f:
        return json.load(f)

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

class FaceProcessor:
    def __init__(self, faces_dir: str, metadata_dir: str):
        """Initialize the face processor."""
        self.faces_dir = faces_dir
        self.metadata_dir = metadata_dir
        
        # Create necessary directories
        os.makedirs(self.faces_dir, exist_ok=True)
        
        # Face embeddings storage
        self.face_embeddings = []
        self.face_photo_ids = []
        self.face_locations = []
        self.face_ids = []
        
        # Face recognition parameters
        self.min_face_size = 30  # Minimum face size in pixels
        self.recognition_tolerance = 0.6  # Lower = more strict matching
        self.clustering_eps = 0.5  # DBSCAN epsilon parameter (clustering threshold)
        self.clustering_min_samples = 3  # Min samples for a cluster
    
    async def process_faces(self, image_path: str, photo_id: str) -> List[Dict[str, Any]]:
        """Detect and process faces in an image."""
        try:
            # Load the image
            image = face_recognition.load_image_file(image_path)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(image)
            
            # If no faces found, return empty list
            if not face_locations:
                return []
            
            # Extract face encodings (embeddings)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            # Process each face
            faces_data = []
            for i, (encoding, location) in enumerate(zip(face_encodings, face_locations)):
                # Generate a temporary face ID
                temp_face_id = f"{photo_id}_{i}"
                
                # Store face data for clustering
                self.face_embeddings.append(encoding)
                self.face_photo_ids.append(photo_id)
                self.face_locations.append(location)
                self.face_ids.append(temp_face_id)
                
                # Extract face thumbnail
                top, right, bottom, left = location
                face_image = image[top:bottom, left:right]
                face_pil = Image.fromarray(face_image)
                
                # Save face thumbnail
                face_thumbnail_path = os.path.join(self.faces_dir, f"{temp_face_id}.jpg")
                face_pil.save(face_thumbnail_path)
                
                # Add face data to the list
                faces_data.append({
                    "id": temp_face_id,
                    "location": {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left
                    },
                    "thumbnail_path": face_thumbnail_path
                })
            
            return faces_data
        
        except Exception as e:
            print(f"Error processing faces for {image_path}: {str(e)}")
            return []
    
    async def cluster_faces(self) -> Dict[str, List[str]]:
        """Cluster detected faces to identify unique individuals."""
        try:
            if not self.face_embeddings:
                return {}
            
            # Convert list of embeddings to numpy array
            embeddings_array = np.array(self.face_embeddings)
            
            # Perform clustering
            clustering = DBSCAN(eps=self.clustering_eps, min_samples=self.clustering_min_samples, metric="euclidean")
            labels = clustering.fit_predict(embeddings_array)
            
            # Create person IDs and mapping
            person_clusters = {}
            for i, label in enumerate(labels):
                # Skip noise points (label = -1)
                if label == -1:
                    continue
                
                # Generate a person ID for this cluster
                person_id = f"person_{label}"
                
                if person_id not in person_clusters:
                    person_clusters[person_id] = []
                
                # Add this face to the person's cluster
                person_clusters[person_id].append(self.face_ids[i])
            
            return person_clusters
        
        except Exception as e:
            print(f"Error clustering faces: {str(e)}")
            return {}
    
    async def update_photos_with_person_ids(self, person_clusters: Dict[str, List[str]], photos_metadata_dir: str) -> Dict[str, Dict[str, Any]]:
        """Update photo metadata with person IDs for each face."""
        try:
            # Create a mapping from face_id to person_id
            face_to_person = {}
            for person_id, face_ids in person_clusters.items():
                for face_id in face_ids:
                    face_to_person[face_id] = person_id
            
            # Dictionary to gather all faces by photo
            photo_faces = {}
            
            # Group faces by photo_id
            for i, face_id in enumerate(self.face_ids):
                photo_id = self.face_photo_ids[i]
                if photo_id not in photo_faces:
                    photo_faces[photo_id] = []
                
                # Get the person ID for this face
                person_id = face_to_person.get(face_id, None)
                
                # Update face info
                face_info = {
                    "id": face_id,
                    "person_id": person_id,
                    "location": {
                        "top": self.face_locations[i][0],
                        "right": self.face_locations[i][1],
                        "bottom": self.face_locations[i][2],
                        "left": self.face_locations[i][3]
                    }
                }
                
                photo_faces[photo_id].append(face_info)
            
            # Update photo metadata files
            person_stats = {}
            
            for photo_id, faces in photo_faces.items():
                metadata_path = os.path.join(photos_metadata_dir, f"{photo_id}.json")
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                        
                        # Update faces data
                        metadata["faces"] = faces
                        
                        # Add a list of person IDs in this photo
                        person_ids = list(set(face["person_id"] for face in faces if face["person_id"]))
                        metadata["people"] = person_ids
                        
                        # Update person statistics
                        for person_id in person_ids:
                            if person_id not in person_stats:
                                person_stats[person_id] = {"face_count": 0, "photo_count": 0, "photos": set()}
                            
                            person_stats[person_id]["photos"].add(photo_id)
                        
                        with open(metadata_path, "w") as f:
                            json.dump(metadata, f, indent=2)
                    except Exception as e:
                        print(f"Error updating metadata for photo {photo_id}: {str(e)}")
            
            # Finalize person statistics
            for person_id, stats in person_stats.items():
                # Get list of all faces for this person
                person_faces = person_clusters.get(person_id, [])
                
                stats["face_count"] = len(person_faces)
                stats["photo_count"] = len(stats["photos"])
                stats["photos"] = list(stats["photos"])  # Convert set to list for JSON serialization
            
            # Save person statistics
            person_stats_path = os.path.join(self.metadata_dir, "person_stats.json")
            with open(person_stats_path, "w") as f:
                json.dump(person_stats, f, indent=2)
            
            return person_stats
        
        except Exception as e:
            print(f"Error updating photos with person IDs: {str(e)}")
            return {} 
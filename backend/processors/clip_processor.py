import torch
from PIL import Image
import clip
from typing import Dict, Any, List, Tuple
import numpy as np
import os

class ClipProcessor:
    def __init__(self, model_name: str = "ViT-B/32"):
        """Initialize the CLIP processor with the specified model.
        
        Args:
            model_name: Name of the CLIP model to use
        """
        # Load the model and move it to GPU if available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        
        # Set model to evaluation mode
        self.model.eval()
        
        # Image size is fixed by the model
        self.image_size = 224  # CLIP's default image size
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process an image and return its CLIP embedding.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing the image embedding
        """
        try:
            # Load and preprocess the image
            image = Image.open(image_path)
            
            # Convert RGBA to RGB if necessary
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            
            # Preprocess the image
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            # Generate embedding
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                
            # Convert to numpy and normalize
            embedding = image_features.cpu().numpy().flatten()
            embedding = embedding / np.linalg.norm(embedding)
            
            return {
                "embedding": embedding.tolist(),  # Convert to list for JSON serialization
                "model": "CLIP-ViT-B/32",
                "embedding_size": len(embedding)
            }
            
        except Exception as e:
            print(f"Error processing image {image_path} with CLIP: {str(e)}")
            return {
                "embedding": None,
                "error": str(e)
            }
    
    @staticmethod
    def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two CLIP embeddings.
        
        Args:
            embedding1: First image embedding
            embedding2: Second image embedding
            
        Returns:
            Similarity score between 0 and 1, where 1 means identical
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        # Convert to numpy arrays
        a = np.array(embedding1)
        b = np.array(embedding2)
        
        # Calculate cosine similarity
        similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        # Clip to range [0, 1]
        similarity = max(0.0, min(1.0, similarity))
        
        return float(similarity)
    
    @staticmethod
    def find_similar_images(
        target_embedding: List[float], 
        candidate_embeddings: List[Dict[str, Any]],
        threshold: float = 0.8
    ) -> List[Tuple[str, float]]:
        """Find similar images based on CLIP embeddings.
        
        Args:
            target_embedding: Embedding of the target image
            candidate_embeddings: List of dictionaries containing image IDs and embeddings
            threshold: Similarity threshold (0 to 1)
            
        Returns:
            List of tuples containing (image_id, similarity_score) sorted by similarity
        """
        if target_embedding is None:
            return []
            
        results = []
        
        for candidate in candidate_embeddings:
            if "embedding" not in candidate or candidate["embedding"] is None:
                continue
                
            similarity = ClipProcessor.calculate_similarity(target_embedding, candidate["embedding"])
            
            if similarity >= threshold:
                results.append((candidate["id"], similarity))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results 
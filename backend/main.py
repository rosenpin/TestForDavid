from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import os
import json
import shutil
from typing import List, Dict, Any, Optional
import uuid
from pathlib import Path
import asyncio
import random

from processors import PhotoProcessor
from narrative_generator import NarrativeGenerator

# Constants for directory paths
BASE_DIR = "."
DATA_DIR = os.path.join(BASE_DIR, "data")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
METADATA_DIR = os.path.join(DATA_DIR, "metadata")
PHOTOS_METADATA_DIR = os.path.join(METADATA_DIR, "photos")
TEMP_UPLOADS_DIR = os.path.join(DATA_DIR, "temp_uploads")
NARRATIVES_FILE = os.path.join(METADATA_DIR, "narratives.json")
FACES_DIR = os.path.join(DATA_DIR, "faces")

app = FastAPI(title="Life Narrative Explorer")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)
os.makedirs(PHOTOS_METADATA_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)

# Mount static files directory for serving photos
app.mount("/api/photo-files", StaticFiles(directory=PHOTOS_DIR), name="photos")
app.mount("/api/face-files", StaticFiles(directory=FACES_DIR), name="faces")

# Global variables to track processing state
processing_status = {
    "is_processing": False,
    "total_photos": 0,
    "processed_photos": 0,
    "current_stage": "idle",  # idle, analyzing, generating_narratives, complete
    "error": None
}

# Initialize processors
photo_processor = PhotoProcessor(data_dir=DATA_DIR)
narrative_generator = NarrativeGenerator(data_dir=DATA_DIR)

@app.get("/api")
async def read_root():
    return {"message": "Life Narrative Explorer API"}

@app.get("/api/status")
async def get_status():
    return processing_status

@app.post("/api/process-directory")
async def process_directory(directory_path: str, background_tasks: BackgroundTasks):
    """Process all photos in a directory and generate narratives."""
    global processing_status
    
    if processing_status["is_processing"]:
        raise HTTPException(status_code=400, detail="Already processing photos")
    
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory_path}")
    
    # Reset status
    processing_status = {
        "is_processing": True,
        "total_photos": 0,
        "processed_photos": 0,
        "current_stage": "idle",
        "error": None
    }
    
    # Start processing in the background
    background_tasks.add_task(process_photos_and_generate_narratives, directory_path)
    
    return {"message": f"Started processing photos in {directory_path}"}

async def process_photos_and_generate_narratives(directory_path: str):
    """Background task to process photos and generate narratives."""
    global processing_status
    
    try:
        # Update status callback function
        def update_status(**kwargs):
            for key, value in kwargs.items():
                processing_status[key] = value
        
        # Process photos
        await photo_processor.process_directory(directory_path, update_status)
        
        # Generate narratives
        await narrative_generator.generate_narratives(update_status)
        
        # Mark as complete
        processing_status["is_processing"] = False
        processing_status["current_stage"] = "complete"
    
    except Exception as e:
        processing_status["is_processing"] = False
        processing_status["error"] = str(e)
        print(f"Error in background processing: {str(e)}")

@app.get("/api/narratives")
async def get_narratives():
    try:
        if not os.path.exists(NARRATIVES_FILE):
            return {"narratives": []}
        
        with open(NARRATIVES_FILE, "r") as f:
            narratives = json.load(f)
        return {"narratives": narratives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving narratives: {str(e)}")

@app.get("/api/narratives/{narrative_id}")
async def get_narrative(narrative_id: str):
    try:
        if not os.path.exists(NARRATIVES_FILE):
            raise HTTPException(status_code=404, detail="Narratives not found")
        
        with open(NARRATIVES_FILE, "r") as f:
            narratives = json.load(f)
        
        for narrative in narratives:
            if narrative["id"] == narrative_id:
                return narrative
        
        raise HTTPException(status_code=404, detail=f"Narrative with ID {narrative_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving narrative: {str(e)}")

@app.get("/api/photos/{photo_id}")
async def get_photo_metadata(photo_id: str):
    try:
        # Check if the photo_id has a file extension
        if "." in photo_id:
            # This is likely a request for the actual photo file, not metadata
            # Let the static file handler handle it
            raise HTTPException(status_code=404, detail="Not Found")
        
        photo_path = os.path.join(PHOTOS_METADATA_DIR, f"{photo_id}.json")
        
        if not os.path.exists(photo_path):
            # Try to find the file in the old location
            old_photo_path = os.path.join("data/metadata/photos", f"{photo_id}.json")
            
            if os.path.exists(old_photo_path):
                photo_path = old_photo_path
            else:
                raise HTTPException(status_code=404, detail=f"Photo metadata not found for ID {photo_id}")
        
        with open(photo_path, "r") as f:
            photo_metadata = json.load(f)
        return photo_metadata
    except Exception as e:
        print(f"Error retrieving photo metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving photo metadata: {str(e)}")

@app.post("/api/upload-photos")
async def upload_photos(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None):
    """Upload photos and process them."""
    global processing_status
    
    if processing_status["is_processing"]:
        raise HTTPException(status_code=400, detail="Already processing photos")
    
    # Reset status
    processing_status = {
        "is_processing": True,
        "total_photos": len(files),
        "processed_photos": 0,
        "current_stage": "uploading",
        "error": None
    }
    
    try:
        # Create a temporary directory for uploads
        os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)
        
        # Save uploaded files
        saved_paths = []
        for file in files:
            file_path = os.path.join(TEMP_UPLOADS_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_paths.append(file_path)
        
        # Start processing in the background
        if background_tasks:
            background_tasks.add_task(process_photos_and_generate_narratives, TEMP_UPLOADS_DIR)
        
        return {"message": f"Uploaded {len(files)} photos for processing"}
    
    except Exception as e:
        processing_status["is_processing"] = False
        processing_status["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Error uploading photos: {str(e)}")

@app.post("/api/narratives")
async def generate_narrative(background_tasks: BackgroundTasks):
    """Generate narratives from existing photos."""
    global processing_status
    
    if processing_status["is_processing"]:
        raise HTTPException(status_code=400, detail="Already processing photos")
    
    # Reset status
    processing_status = {
        "is_processing": True,
        "total_photos": 0,
        "processed_photos": 0,
        "current_stage": "generating_narratives",
        "error": None
    }
    
    try:
        # Start narrative generation in the background
        background_tasks.add_task(generate_narratives_only)
        
        return {"message": "Started generating narratives from existing photos"}
    
    except Exception as e:
        processing_status["is_processing"] = False
        processing_status["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Error generating narratives: {str(e)}")

async def generate_narratives_only():
    """Background task to generate narratives from existing photos."""
    global processing_status
    
    try:
        # Update status callback function
        def update_status(**kwargs):
            for key, value in kwargs.items():
                processing_status[key] = value
        
        # Generate narratives
        await narrative_generator.generate_narratives(update_status)
        
        # Mark as complete
        processing_status["is_processing"] = False
        processing_status["current_stage"] = "complete"
    
    except Exception as e:
        processing_status["is_processing"] = False
        processing_status["error"] = str(e)
        print(f"Error in background narrative generation: {str(e)}")

@app.get("/api/persons")
async def get_persons():
    """Get a list of all persons detected in photos."""
    try:
        person_stats_path = os.path.join(METADATA_DIR, "person_stats.json")
        if os.path.exists(person_stats_path):
            with open(person_stats_path, "r") as f:
                person_stats = json.load(f)
            return person_stats
        else:
            return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving person data: {str(e)}")

@app.get("/api/persons/{person_id}")
async def get_person(person_id: str):
    """Get details for a specific person, including all photos they appear in."""
    try:
        person_stats_path = os.path.join(METADATA_DIR, "person_stats.json")
        if not os.path.exists(person_stats_path):
            raise HTTPException(status_code=404, detail="No person data available")
        
        with open(person_stats_path, "r") as f:
            person_stats = json.load(f)
        
        if person_id not in person_stats:
            raise HTTPException(status_code=404, detail=f"Person {person_id} not found")
        
        person_data = person_stats[person_id]
        
        # Get photo metadata for all photos this person appears in
        photo_metadata = []
        for photo_id in person_data.get("photos", []):
            photo_path = os.path.join(PHOTOS_METADATA_DIR, f"{photo_id}.json")
            if os.path.exists(photo_path):
                with open(photo_path, "r") as f:
                    photo_data = json.load(f)
                
                # Filter to only include this person's face data
                if "faces" in photo_data:
                    photo_data["faces"] = [face for face in photo_data["faces"] 
                                          if face.get("person_id") == person_id]
                
                photo_metadata.append(photo_data)
        
        # Add photo metadata to the response
        person_data["photo_metadata"] = photo_metadata
        
        return person_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving person data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["./"], reload_excludes=["./data/*", "./venv/*"]) 
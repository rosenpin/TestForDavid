from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
import json
import shutil
from typing import List, Dict, Any, Optional
import uuid
from pathlib import Path
import asyncio
import random

from photo_processor import PhotoProcessor
from narrative_generator import NarrativeGenerator

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
os.makedirs("data", exist_ok=True)
os.makedirs("data/photos", exist_ok=True)
os.makedirs("data/metadata", exist_ok=True)
os.makedirs("data/metadata/photos", exist_ok=True)
os.makedirs("data/temp_uploads", exist_ok=True)

# Mount static files directory for serving photos
app.mount("/photos", StaticFiles(directory="data/photos"), name="photos")

# Global variables to track processing state
processing_status = {
    "is_processing": False,
    "total_photos": 0,
    "processed_photos": 0,
    "current_stage": "idle",  # idle, analyzing, generating_narratives, complete
    "error": None
}

# Initialize processors
photo_processor = PhotoProcessor()
narrative_generator = NarrativeGenerator()

@app.get("/")
async def read_root():
    return {"message": "Life Narrative Explorer API"}

@app.get("/status")
async def get_status():
    return processing_status

@app.post("/process-directory")
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

@app.get("/narratives")
async def get_narratives():
    try:
        if not os.path.exists("data/metadata/narratives.json"):
            return {"narratives": []}
        
        with open("data/metadata/narratives.json", "r") as f:
            narratives = json.load(f)
        return {"narratives": narratives}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving narratives: {str(e)}")

@app.get("/narratives/{narrative_id}")
async def get_narrative(narrative_id: str):
    try:
        if not os.path.exists("data/metadata/narratives.json"):
            raise HTTPException(status_code=404, detail="Narratives not found")
        
        with open("data/metadata/narratives.json", "r") as f:
            narratives = json.load(f)
        
        for narrative in narratives:
            if narrative["id"] == narrative_id:
                return narrative
        
        raise HTTPException(status_code=404, detail=f"Narrative with ID {narrative_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving narrative: {str(e)}")

@app.get("/photos/{photo_id}")
async def get_photo_metadata(photo_id: str):
    try:
        photo_path = f"data/metadata/photos/{photo_id}.json"
        if not os.path.exists(photo_path):
            raise HTTPException(status_code=404, detail=f"Photo metadata not found for ID {photo_id}")
        
        with open(photo_path, "r") as f:
            photo_metadata = json.load(f)
        return photo_metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving photo metadata: {str(e)}")

@app.post("/upload-photos")
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
        temp_dir = "data/temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save uploaded files
        saved_paths = []
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_paths.append(file_path)
        
        # Start processing in the background
        if background_tasks:
            background_tasks.add_task(process_photos_and_generate_narratives, temp_dir)
        
        return {"message": f"Uploaded {len(files)} photos for processing"}
    
    except Exception as e:
        processing_status["is_processing"] = False
        processing_status["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Error uploading photos: {str(e)}")

@app.post("/narratives")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 
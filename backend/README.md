# Life Narrative Explorer - Backend

This is the backend API for the Life Narrative Explorer application, which analyzes collections of photos to generate AI-curated "life narratives".

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Run the server:
   ```
   python main.py
   ```

The server will start on http://localhost:8000

## API Endpoints

- `GET /` - Root endpoint
- `GET /status` - Get the current processing status
- `POST /process-directory` - Process all photos in a directory
  - Query parameter: `directory_path` - Path to the directory containing photos
- `GET /narratives` - Get all generated narratives
- `GET /narratives/{narrative_id}` - Get a specific narrative by ID
- `GET /photos/{photo_id}` - Get metadata for a specific photo
- `POST /upload-photos` - Upload photos for processing

## Data Structure

The application stores data in the following structure:

- `data/photos/` - Processed photos
- `data/metadata/` - Metadata for photos and narratives
  - `data/metadata/photos/` - Individual photo metadata JSON files
  - `data/metadata/narratives.json` - Generated narratives

## Processing Flow

1. Photos are processed to generate descriptions using OpenAI's Vision API
2. Descriptions are analyzed to identify meaningful narratives
3. Photos are grouped into these narratives
4. Representative photos are selected for each narrative

## Development

This application is built with FastAPI and uses OpenAI's APIs for image analysis and narrative generation. 
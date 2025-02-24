# Life Narrative Explorer

Life Narrative Explorer is an application that analyzes collections of photos to generate AI-curated "life narratives". It uses OpenAI's Vision API to generate descriptions for photos and then groups them into meaningful narratives.

## Project Structure

- `backend/` - Python FastAPI backend
- `frontend/` - React frontend
- `Photos/` - Sample photos for testing

## Setup

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. Run the server:
   ```
   python main.py
   ```

The backend will start on http://localhost:8000

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm run dev
   ```

The frontend will start on http://localhost:3000

## Usage

1. Open the application in your browser at http://localhost:3000
2. Go to the "Process Photos" page
3. Either:
   - Enter the path to a directory containing photos, or
   - Upload photos directly from your device
4. Wait for the processing to complete
5. Explore the generated narratives on the "Narratives" page

## Features

- Photo Analysis: AI generates descriptions for each photo, focusing on key details
- Narrative Generation: Descriptions are analyzed to identify meaningful life narratives
- Photo Selection: The most representative photos are selected for each narrative
- User Interface: Browse through narratives and view photos in slideshow or grid view

## Technologies Used

- Backend:
  - Python with FastAPI
  - OpenAI API for image analysis and narrative generation
  - Pillow for image processing

- Frontend:
  - React for the UI framework
  - React Router for navigation
  - Tailwind CSS for styling
  - Axios for API requests

## Future Improvements

- Authentication and user accounts
- Cloud storage for photos
- More advanced photo analysis
- Customizable narrative themes
- Sharing capabilities
- Export to various formats (PDF, slideshow, etc.) 
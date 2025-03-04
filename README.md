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

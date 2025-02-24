# Life Narrative Explorer - Frontend

This is the frontend for the Life Narrative Explorer application, which analyzes collections of photos to generate AI-curated "life narratives".

## Setup

1. Install dependencies:
   ```
   npm install
   ```

2. Start the development server:
   ```
   npm run dev
   ```

The frontend will start on http://localhost:3000 and will proxy API requests to the backend at http://localhost:8000.

## Build for Production

To build the application for production:

```
npm run build
```

The built files will be in the `dist` directory.

## Features

- Upload photos or process photos from a directory
- View generated life narratives
- Explore photos within each narrative in slideshow or grid view
- Track processing status in real-time

## Technologies Used

- React for the UI framework
- React Router for navigation
- Axios for API requests
- Tailwind CSS for styling
- Vite for the build system 
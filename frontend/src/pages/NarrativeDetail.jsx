import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';

const NarrativeDetail = () => {
  const { id } = useParams();
  const [narrative, setNarrative] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('slideshow'); // 'slideshow' or 'grid'

  useEffect(() => {
    const fetchNarrativeAndPhotos = async () => {
      try {
        setLoading(true);
        
        // Fetch narrative details
        const narrativeResponse = await axios.get(`/api/narratives/${id}`);
        setNarrative(narrativeResponse.data);
        
        // Fetch photo details for each photo in the narrative
        const photoIds = narrativeResponse.data.selected_photo_ids || [];
        const photoPromises = photoIds.map(photoId => 
          axios.get(`/api/photos/${photoId}`)
        );
        
        const photoResponses = await Promise.all(photoPromises);
        const photoData = photoResponses.map(response => response.data);
        setPhotos(photoData);
        
        setLoading(false);
      } catch (err) {
        console.error('Error fetching narrative details:', err);
        setError('Failed to load narrative details. Please try again later.');
        setLoading(false);
      }
    };

    fetchNarrativeAndPhotos();
  }, [id]);

  const goToNextPhoto = () => {
    setCurrentPhotoIndex((prevIndex) => 
      prevIndex === photos.length - 1 ? 0 : prevIndex + 1
    );
  };

  const goToPreviousPhoto = () => {
    setCurrentPhotoIndex((prevIndex) => 
      prevIndex === 0 ? photos.length - 1 : prevIndex - 1
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowRight') {
      goToNextPhoto();
    } else if (e.key === 'ArrowLeft') {
      goToPreviousPhoto();
    }
  };

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
        <strong className="font-bold">Error!</strong>
        <span className="block sm:inline"> {error}</span>
      </div>
    );
  }

  if (!narrative) {
    return (
      <div className="text-center py-12">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Narrative Not Found</h1>
        <p className="text-gray-600 mb-6">
          The narrative you're looking for doesn't exist or has been removed.
        </p>
        <Link to="/narratives" className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
          Back to Narratives
        </Link>
      </div>
    );
  }

  return (
    <div className="py-8">
      <div className="mb-8">
        <Link to="/narratives" className="text-blue-600 hover:text-blue-800 flex items-center">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Back to Narratives
        </Link>
      </div>
      
      <div className="bg-white rounded-lg shadow-md p-8 mb-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">{narrative.title}</h1>
        <p className="text-gray-600 mb-6 whitespace-pre-line">{narrative.description}</p>
        
        <div className="flex justify-between items-center mb-6">
          <div className="text-sm text-gray-500">
            {photos.length} photos in this narrative
          </div>
          <div className="flex space-x-2">
            <button 
              onClick={() => setViewMode('slideshow')}
              className={`px-3 py-1 rounded ${viewMode === 'slideshow' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
            >
              Slideshow
            </button>
            <button 
              onClick={() => setViewMode('grid')}
              className={`px-3 py-1 rounded ${viewMode === 'grid' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'}`}
            >
              Grid
            </button>
          </div>
        </div>
      </div>
      
      {viewMode === 'slideshow' && photos.length > 0 && (
        <div className="photo-viewer bg-black rounded-lg shadow-lg overflow-hidden relative">
          <div className="relative">
            <img 
              src={`/api/photos/${photos[currentPhotoIndex].filename}`} 
              alt={photos[currentPhotoIndex].description}
              className="w-full max-h-[70vh] object-contain mx-auto"
            />
            
            <div className="photo-controls absolute inset-0 flex justify-between items-center px-4">
              <button 
                onClick={goToPreviousPhoto}
                className="bg-black bg-opacity-50 text-white p-2 rounded-full hover:bg-opacity-70 transition"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button 
                onClick={goToNextPhoto}
                className="bg-black bg-opacity-50 text-white p-2 rounded-full hover:bg-opacity-70 transition"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
          
          <div className="bg-gray-900 text-white p-6">
            <p className="text-lg">{photos[currentPhotoIndex].description}</p>
            <div className="mt-2 text-gray-400 text-sm">
              Photo {currentPhotoIndex + 1} of {photos.length}
              {photos[currentPhotoIndex].location && (
                <div className="mt-1">
                  <span className="inline-flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Location: {photos[currentPhotoIndex].location.latitude.toFixed(6)}, {photos[currentPhotoIndex].location.longitude.toFixed(6)}
                  </span>
                </div>
              )}
              {photos[currentPhotoIndex].timestamp && (
                <div className="mt-1">
                  <span className="inline-flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    Date: {new Date(photos[currentPhotoIndex].timestamp * 1000).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      {viewMode === 'grid' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {photos.map((photo, index) => (
            <div key={photo.id} className="bg-white rounded-lg shadow-md overflow-hidden">
              <img 
                src={`/api/photos/${photo.filename}`} 
                alt={photo.description}
                className="w-full h-64 object-cover cursor-pointer"
                onClick={() => {
                  setCurrentPhotoIndex(index);
                  setViewMode('slideshow');
                }}
              />
              <div className="p-4">
                <p className="text-gray-600 line-clamp-3">{photo.description}</p>
                {photo.location && (
                  <p className="text-gray-500 text-xs mt-1 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {photo.location.latitude.toFixed(6)}, {photo.location.longitude.toFixed(6)}
                  </p>
                )}
                {photo.timestamp && (
                  <p className="text-gray-500 text-xs mt-1 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(photo.timestamp * 1000).toLocaleDateString()}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NarrativeDetail; 
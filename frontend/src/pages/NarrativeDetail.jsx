import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';

const NarrativeDetail = () => {
  const { id } = useParams();
  const [narrative, setNarrative] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('grid'); // 'slideshow' or 'grid'
  const [personData, setPersonData] = useState({});
  const [loadingPersons, setLoadingPersons] = useState(false);

  useEffect(() => {
    const fetchNarrativeAndPhotos = async () => {
      try {
        setLoading(true);
        
        // Fetch narrative details
        const narrativeResponse = await axios.get(`/api/narratives/${id}`);
        setNarrative(narrativeResponse.data);
        
        // Fetch photo details for each photo in the narrative
        const photoIds = narrativeResponse.data.selected_photo_ids || [];
        setLoadingProgress({ loaded: 0, total: photoIds.length });
        
        // Process photos in smaller batches to avoid too many concurrent requests
        const batchSize = 5; // Process 5 photos at a time
        const photoData = [];
        
        for (let i = 0; i < photoIds.length; i += batchSize) {
          const batch = photoIds.slice(i, i + batchSize);
          const batchPromises = batch.map(photoId => 
            axios.get(`/api/photos/${photoId}`)
              .catch(err => {
                console.warn(`Failed to load photo ${photoId}:`, err);
                // Return a placeholder instead of failing completely
                return { 
                  data: { 
                    id: photoId,
                    filename: 'placeholder.jpg', 
                    description: 'Image could not be loaded',
                    error: true
                  } 
                };
              })
          );
          
          const batchResponses = await Promise.all(batchPromises);
          photoData.push(...batchResponses.map(response => response.data));
          
          // Update progress
          setLoadingProgress({ 
            loaded: Math.min(i + batchSize, photoIds.length), 
            total: photoIds.length 
          });
        }
        
        setPhotos(photoData);
        setLoading(false);

        // After loading photos, fetch person data
        fetchPersonData();
      } catch (err) {
        console.error('Error fetching narrative details:', err);
        setError('Failed to load narrative details. Please try again later.');
        setLoading(false);
      }
    };

    // Function to fetch person data
    const fetchPersonData = async () => {
      try {
        setLoadingPersons(true);
        
        // Get all persons data
        const personsResponse = await axios.get('/api/persons');
        
        if (personsResponse.data) {
          // Create a lookup object for easy access
          const personsLookup = {};
          
          // Process each person
          Object.entries(personsResponse.data).forEach(([personId, personInfo]) => {
            personsLookup[personId] = {
              ...personInfo,
              // Get a sample face image if available
              sampleFace: personInfo.photos?.[0] ? `${personId}_sample` : null
            };
          });
          
          setPersonData(personsLookup);
        }
        
        setLoadingPersons(false);
      } catch (err) {
        console.error('Error fetching person data:', err);
        setLoadingPersons(false);
      }
    };

    fetchNarrativeAndPhotos();
  }, [id]);

  // Helper function to render faces for a photo
  const renderFaces = (photo, isSlideshow = false) => {
    if (!photo.faces || photo.faces.length === 0) {
      return null;
    }

    // Show loading indicator when person data is being fetched
    if (loadingPersons) {
      return (
        <div className={`${isSlideshow ? 'mt-4 pt-3 border-t border-gray-700' : 'mt-3 border-t pt-2'}`}>
          <div className="flex items-center space-x-2">
            <div className={`${isSlideshow ? 'text-gray-300' : 'text-gray-600'} text-sm`}>Loading people data...</div>
            <div className={`animate-spin rounded-full h-3 w-3 border-t-2 border-b-2 ${isSlideshow ? 'border-gray-300' : 'border-gray-600'}`}></div>
          </div>
        </div>
      );
    }

    // Check if we have any valid faces with person IDs
    const validFaces = photo.faces.filter(face => face.person_id && personData[face.person_id]);
    if (validFaces.length === 0) {
      return (
        <div className={`${isSlideshow ? 'mt-4 pt-3 border-t border-gray-700' : 'mt-3 border-t pt-2'}`}>
          <div className={`${isSlideshow ? 'text-gray-300' : 'text-gray-600'} text-sm italic`}>No recognized people in this photo</div>
        </div>
      );
    }

    return (
      <div className={`${isSlideshow ? 'mt-4 pt-3 border-t border-gray-700' : 'mt-3 border-t pt-2'}`}>
        <h3 className={`${isSlideshow ? 'text-sm font-medium text-gray-300 mb-3' : 'text-sm font-medium mb-2'}`}>People in this photo:</h3>
        <div className="flex flex-wrap gap-2">
          {photo.faces.map((face) => {
            if (!face.person_id) return null;
            
            const person = personData[face.person_id];
            if (!person) return null;

            // Calculate photo count for this person
            const photoCount = person.photos?.length || 0;
            
            return (
              <div 
                key={face.id} 
                className={`flex items-center ${isSlideshow ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-100 hover:bg-gray-200'} rounded-full px-2 py-1 transition-colors duration-200 cursor-pointer group relative`}
                title={`${face.person_id.replace('person_', 'Person ')} - Appears in ${photoCount} photo${photoCount !== 1 ? 's' : ''}`}
              >
                <img 
                  src={`/api/photo-files/faces/${face.id}.jpg`}
                  alt={`Face ${face.id}`}
                  className={`${isSlideshow ? 'w-10 h-10' : 'w-8 h-8'} rounded-full object-cover mr-1 border ${isSlideshow ? 'border-gray-600' : 'border-white'}`}
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
                  }}
                />
                <span className={`text-xs ${isSlideshow ? 'text-gray-300' : 'text-gray-700'}`}>{face.person_id.replace('person_', 'Person ')}</span>
                
                {/* Tooltip that appears on hover */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                  <div className="bg-gray-900 text-white text-xs rounded py-1 px-2 whitespace-nowrap">
                    Appears in {photoCount} photo{photoCount !== 1 ? 's' : ''}
                    <div className="absolute left-1/2 transform -translate-x-1/2 top-full">
                      <div className="border-4 border-transparent border-t-gray-900 w-0 h-0"></div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

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
      <div className="flex flex-col justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mb-4"></div>
        {loadingProgress.total > 0 && (
          <div className="text-gray-600">
            Loading photos ({loadingProgress.loaded} of {loadingProgress.total})...
            <div className="w-64 bg-gray-200 rounded-full h-2.5 mt-2">
              <div 
                className="bg-blue-500 h-2.5 rounded-full" 
                style={{ width: `${(loadingProgress.loaded / loadingProgress.total) * 100}%` }}
              ></div>
            </div>
          </div>
        )}
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
            {photos.length} photos in this narrative {narrative.photo_ids && narrative.photo_ids.length !== photos.length && `(${narrative.photo_ids.length} before filtering)`}
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
            {photos[currentPhotoIndex].error ? (
              <div className="w-full h-[70vh] flex items-center justify-center bg-gray-200">
                <div className="text-center p-6">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <p className="mt-4 text-gray-600">Image could not be loaded</p>
                </div>
              </div>
            ) : (
              <img 
                src={`/api/photo-files/${photos[currentPhotoIndex].filename}`} 
                alt={photos[currentPhotoIndex].description}
                className="w-full max-h-[70vh] object-contain mx-auto"
                onError={(e) => {
                  const imgElement = e.target;
                  const photoId = photos[currentPhotoIndex].id;
                  const filename = photos[currentPhotoIndex].filename;
                  
                  // Check if filename already has an extension
                  const hasExtension = /\.\w+$/.test(filename);
                  
                  if (!hasExtension) {
                    // Try with common image extensions
                    if (!imgElement.getAttribute('data-tried-jpg')) {
                      imgElement.setAttribute('data-tried-jpg', 'true');
                      imgElement.src = `/api/photo-files/${filename}.jpg`;
                    } else if (!imgElement.getAttribute('data-tried-jpeg')) {
                      imgElement.setAttribute('data-tried-jpeg', 'true');
                      imgElement.src = `/api/photo-files/${filename}.jpeg`;
                    } else if (!imgElement.getAttribute('data-tried-png')) {
                      imgElement.setAttribute('data-tried-png', 'true');
                      imgElement.src = `/api/photo-files/${filename}.png`;
                    } else if (!imgElement.getAttribute('data-tried-id')) {
                      // Try using just the photo ID
                      imgElement.setAttribute('data-tried-id', 'true');
                      imgElement.src = `/api/photo-files/${photoId}`;
                    } else {
                      // If all attempts fail, mark as error
                      const updatedPhotos = [...photos];
                      updatedPhotos[currentPhotoIndex] = {
                        ...updatedPhotos[currentPhotoIndex],
                        error: true
                      };
                      setPhotos(updatedPhotos);
                    }
                  } else {
                    // If filename has extension but still failed, try photoId
                    if (!imgElement.getAttribute('data-tried-id')) {
                      imgElement.setAttribute('data-tried-id', 'true');
                      imgElement.src = `/api/photo-files/${photoId}`;
                    } else {
                      // Mark as error if that also fails
                      const updatedPhotos = [...photos];
                      updatedPhotos[currentPhotoIndex] = {
                        ...updatedPhotos[currentPhotoIndex],
                        error: true
                      };
                      setPhotos(updatedPhotos);
                    }
                  }
                }}
              />
            )}
            
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
              
              {/* Add faces/person recognition section */}
              {renderFaces(photos[currentPhotoIndex], true)}
            </div>
          </div>
        </div>
      )}
      
      {viewMode === 'grid' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {photos.map((photo, index) => (
            <div key={photo.id} className="bg-white rounded-lg shadow-md overflow-hidden">
              {photo.error ? (
                <div className="h-64 bg-gray-200 flex items-center justify-center">
                  <div className="text-center p-4">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 mx-auto text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="mt-2 text-sm text-gray-600">Image could not be loaded</p>
                  </div>
                </div>
              ) : (
                <img 
                  src={`/api/photo-files/${photo.filename}`} 
                  alt={photo.description}
                  className="w-full h-64 object-cover cursor-pointer"
                  loading="lazy"
                  onClick={() => {
                    setCurrentPhotoIndex(index);
                    setViewMode('slideshow');
                  }}
                  onError={(e) => {
                    const imgElement = e.target;
                    const photoId = photo.id;
                    const filename = photo.filename;
                    
                    // Check if filename already has an extension
                    const hasExtension = /\.\w+$/.test(filename);
                    
                    if (!hasExtension) {
                      // Try with common image extensions
                      if (!imgElement.getAttribute('data-tried-jpg')) {
                        imgElement.setAttribute('data-tried-jpg', 'true');
                        imgElement.src = `/api/photo-files/${filename}.jpg`;
                      } else if (!imgElement.getAttribute('data-tried-jpeg')) {
                        imgElement.setAttribute('data-tried-jpeg', 'true');
                        imgElement.src = `/api/photo-files/${filename}.jpeg`;
                      } else if (!imgElement.getAttribute('data-tried-png')) {
                        imgElement.setAttribute('data-tried-png', 'true');
                        imgElement.src = `/api/photo-files/${filename}.png`;
                      } else if (!imgElement.getAttribute('data-tried-id')) {
                        // Try using just the photo ID
                        imgElement.setAttribute('data-tried-id', 'true');
                        imgElement.src = `/api/photo-files/${photoId}`;
                      } else {
                        // If all attempts fail, mark as error
                        const updatedPhotos = [...photos];
                        updatedPhotos[index] = {
                          ...updatedPhotos[index],
                          error: true
                        };
                        setPhotos(updatedPhotos);
                      }
                    } else {
                      // If filename has extension but still failed, try photoId
                      if (!imgElement.getAttribute('data-tried-id')) {
                        imgElement.setAttribute('data-tried-id', 'true');
                        imgElement.src = `/api/photo-files/${photoId}`;
                      } else {
                        // Mark as error if that also fails
                        const updatedPhotos = [...photos];
                        updatedPhotos[index] = {
                          ...updatedPhotos[index],
                          error: true
                        };
                        setPhotos(updatedPhotos);
                      }
                    }
                  }}
                />
              )}
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
                
                {/* Add faces/person recognition section */}
                {renderFaces(photo, false)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NarrativeDetail; 
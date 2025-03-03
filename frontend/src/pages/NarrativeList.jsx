import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const NarrativeList = () => {
  const [narratives, setNarratives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [processingInterval, setProcessingInterval] = useState(null);

  useEffect(() => {
    const fetchNarratives = async () => {
      try {
        setLoading(true);
        const response = await axios.get('/api/narratives');
        setNarratives(response.data.narratives || []);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching narratives:', err);
        setError('Failed to load narratives. Please try again later.');
        setLoading(false);
      }
    };

    fetchNarratives();
  }, []);

  useEffect(() => {
    checkProcessingStatus();
    return () => {
      if (processingInterval) {
        clearInterval(processingInterval);
      }
    };
  }, []);

  useEffect(() => {
    if (processingStatus && processingStatus.is_processing) {
      const interval = setInterval(checkProcessingStatus, 3000);
      setProcessingInterval(interval);
      return () => clearInterval(interval);
    } else if (processingInterval) {
      clearInterval(processingInterval);
      setProcessingInterval(null);
    }
  }, [processingStatus]);

  const checkProcessingStatus = async () => {
    try {
      const response = await axios.get('/api/status');
      setProcessingStatus(response.data);
      
      if (response.data && response.data.is_processing === false && response.data.current_stage === 'complete') {
        fetchNarratives();
      }
    } catch (err) {
      console.error('Error checking processing status:', err);
    }
  };

  const startFaceDetection = async () => {
    try {
      await axios.post('/api/update-face-data');
      checkProcessingStatus();
    } catch (err) {
      console.error('Error starting face detection:', err);
      setError('Failed to start face detection process. Please try again later.');
    }
  };

  const getStatusMessage = () => {
    if (!processingStatus || !processingStatus.is_processing) {
      return null;
    }

    const stage = processingStatus.current_stage;
    
    if (stage === 'preparing_face_data_update') {
      return 'Preparing for face detection...';
    } else if (stage === 'detecting_faces') {
      const processed = processingStatus.processed_photos || 0;
      const total = processingStatus.total_photos || 0;
      const faces = processingStatus.faces_detected || 0;
      return `Detecting faces: ${processed}/${total} photos processed (${faces} faces found)`;
    } else if (stage === 'clustering_faces') {
      return 'Grouping similar faces together...';
    } else {
      return `Processing: ${stage}`;
    }
  };

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

  if (narratives.length === 0) {
    return (
      <div className="text-center py-12">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Your Narratives</h1>
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-6 py-8 rounded-lg max-w-2xl mx-auto">
          <h2 className="text-xl font-semibold mb-3">No narratives found</h2>
          <p className="text-gray-600 mb-6">
            You haven't processed any photos yet. Process your photos to discover the narratives in your collection.
          </p>
          <Link to="/process" className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
            Process Photos
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Your Life Narratives</h1>
        
        <button
          onClick={startFaceDetection}
          disabled={processingStatus && processingStatus.is_processing}
          className={`flex items-center px-4 py-2 rounded-md ${
            processingStatus && processingStatus.is_processing
              ? 'bg-gray-300 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 text-white'
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
          </svg>
          Detect Faces
        </button>
      </div>
      
      {processingStatus && processingStatus.is_processing && (
        <div className="mb-8 bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded relative">
          <div className="flex items-center">
            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-3"></div>
            <span>{getStatusMessage()}</span>
          </div>
          {processingStatus.processed_photos !== undefined && processingStatus.total_photos > 0 && (
            <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
              <div 
                className="bg-blue-500 h-2.5 rounded-full" 
                style={{ width: `${(processingStatus.processed_photos / processingStatus.total_photos) * 100}%` }}
              ></div>
            </div>
          )}
        </div>
      )}
      
      {processingStatus && !processingStatus.is_processing && processingStatus.face_stats && (
        <div className="mb-8 bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded relative">
          <p className="font-medium">Face detection complete!</p>
          <p className="text-sm mt-1">
            Processed {processingStatus.face_stats.processed} photos, 
            detected {processingStatus.face_stats.faces_detected} faces, 
            identified {processingStatus.face_stats.unique_persons || 0} unique persons.
          </p>
        </div>
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {narratives.map((narrative) => {
          const photoCount = narrative.selected_photo_ids ? narrative.selected_photo_ids.length : 0;
          const isSmallCollection = photoCount < 30;
          
          return (
          <Link 
            key={narrative.id} 
            to={`/narratives/${narrative.id}`}
            className={`narrative-card bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition-all duration-300 ${isSmallCollection ? 'opacity-60' : ''}`}
          >
            {narrative.selected_photo_ids && narrative.selected_photo_ids.length > 0 && (
              <div className="h-48 overflow-hidden">
                <img 
                  src={`/api/photo-files/${narrative.selected_photo_ids[0]}`} 
                  alt={narrative.title}
                  className={`w-full h-full object-cover ${isSmallCollection ? 'filter grayscale' : ''}`}
                  loading="lazy"
                  onError={(e) => {
                    const imgElement = e.target;
                    const photoId = narrative.selected_photo_ids[0];
                    
                    const hasExtension = /\.\w+$/.test(photoId);
                    
                    if (!hasExtension) {
                      if (!imgElement.getAttribute('data-tried-jpg')) {
                        imgElement.setAttribute('data-tried-jpg', 'true');
                        imgElement.src = `/api/photo-files/${photoId}.jpg`;
                      } else if (!imgElement.getAttribute('data-tried-jpeg')) {
                        imgElement.setAttribute('data-tried-jpeg', 'true');
                        imgElement.src = `/api/photo-files/${photoId}.jpeg`;
                      } else if (!imgElement.getAttribute('data-tried-png')) {
                        imgElement.setAttribute('data-tried-png', 'true');
                        imgElement.src = `/api/photo-files/${photoId}.png`;
                      } else {
                        imgElement.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
                        imgElement.classList.add('placeholder-img');
                      }
                    } else {
                      imgElement.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
                      imgElement.classList.add('placeholder-img');
                    }
                  }}
                />
              </div>
            )}
            <div className="p-6">
              <h2 className={`text-xl font-semibold mb-2 ${isSmallCollection ? 'text-gray-600' : 'text-gray-800'}`}>{narrative.title}</h2>
              <p className="text-gray-600 line-clamp-3">
                {narrative.description}
              </p>
              <div className="mt-4 flex justify-between items-center">
                <span className={`text-sm ${isSmallCollection ? 'text-gray-400' : 'text-gray-500'}`}>
                  {photoCount} photos 
                </span>
                <span className={`font-medium ${isSmallCollection ? 'text-blue-400' : 'text-blue-600'}`}>View narrative →</span>
              </div>
            </div>
          </Link>
          );
        })}
      </div>
    </div>
  );
};

export default NarrativeList; 
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const NarrativeList = () => {
  const [narratives, setNarratives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      <h1 className="text-3xl font-bold text-gray-800 mb-8 text-center">Your Life Narratives</h1>
      
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
                    // If the image fails to load, try with different extensions
                    const imgElement = e.target;
                    const photoId = narrative.selected_photo_ids[0];
                    
                    // Only append extension if the photoId doesn't already have one
                    // Check if photoId contains a dot followed by file extension
                    const hasExtension = /\.\w+$/.test(photoId);
                    
                    if (!hasExtension) {
                      // Try with common image extensions
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
                        // If all formats fail, replace with placeholder
                        imgElement.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
                        imgElement.classList.add('placeholder-img');
                      }
                    } else {
                      // Already has extension but still failed, use placeholder
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
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';

const PersonDetail = () => {
  const { id } = useParams();
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPersonData = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`/api/persons/${id}`);
        setPerson(response.data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching person data:', err);
        setError('Failed to load person data. Please try again later.');
        setLoading(false);
      }
    };

    fetchPersonData();
  }, [id]);

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

  if (!person) {
    return (
      <div className="text-center py-12">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Person Not Found</h1>
        <p className="text-gray-600 mb-6">
          The person you're looking for could not be found.
        </p>
        <Link to="/narratives" className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
          Back to Narratives
        </Link>
      </div>
    );
  }

  // Get a sample photo for this person
  const photoCount = person.photos?.length || 0;
  const photoMetadata = person.photo_metadata || [];
  const firstPhoto = photoMetadata.length > 0 ? photoMetadata[0] : null;

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center mb-8">
        <Link to="/narratives" className="text-blue-600 hover:text-blue-800 mr-4">
          &larr; Back to Narratives
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <div className="flex items-center mb-6">
          {firstPhoto ? (
            <img 
              src={`/api/photo-files/${firstPhoto.filename}`}
              alt={`Person ${id.replace('person_', '')}`}
              className="w-20 h-20 rounded-full object-cover border-4 border-blue-100 mr-4"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
              }}
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-gray-200 flex items-center justify-center mr-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
              </svg>
            </div>
          )}
          <div>
            <h1 className="text-2xl font-bold text-gray-800">
              {id.replace('person_', 'Person ')}
            </h1>
            <p className="text-gray-600">
              Appears in {photoCount} photo{photoCount !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      </div>

      <h2 className="text-xl font-semibold text-gray-800 mb-4">Photos with this person</h2>
      
      {photoMetadata.length === 0 ? (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded relative">
          No photos found for this person.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {photoMetadata.map((photo) => (
            <div key={photo.id} className="bg-white rounded-lg shadow-md overflow-hidden">
              <div className="h-48 overflow-hidden">
                <img 
                  src={`/api/photo-files/${photo.filename}`} 
                  alt={photo.description || 'Photo'}
                  className="w-full h-full object-cover"
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
                        // If all attempts fail, use placeholder
                        imgElement.src = 'https://www.svgrepo.com/show/508699/landscape-placeholder.svg';
                      }
                    }
                  }}
                />
              </div>
              <div className="p-4">
                <p className="text-sm text-gray-600 line-clamp-3">
                  {photo.description || 'No description available'}
                </p>
                <div className="mt-3 flex justify-between items-center">
                  <span className="text-xs text-gray-500">
                    {photo.timestamp ? new Date(photo.timestamp * 1000).toLocaleDateString() : 'Unknown date'}
                  </span>
                  {photo.narrative_id && (
                    <Link 
                      to={`/narratives/${photo.narrative_id}`}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      View in Narrative
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PersonDetail; 
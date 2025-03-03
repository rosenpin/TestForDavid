import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const ProcessPhotos = () => {
  const [directoryPath, setDirectoryPath] = useState('');
  const [files, setFiles] = useState([]);
  const [status, setStatus] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef(null);
  const statusIntervalRef = useRef(null);
  const [faceProcessingStatus, setFaceProcessingStatus] = useState(null);
  const faceStatusIntervalRef = useRef(null);

  // Fetch processing status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get('/api/status');
        setStatus(response.data);
        
        // If processing is complete, clear the interval and show success message
        if (response.data.current_stage === 'complete') {
          if (statusIntervalRef.current) {
            clearInterval(statusIntervalRef.current);
            statusIntervalRef.current = null;
          }
          setLoading(false);
          setSuccess(true);
        }
        
        // If there's an error, show it
        if (response.data.error) {
          setError(response.data.error);
          setLoading(false);
          if (statusIntervalRef.current) {
            clearInterval(statusIntervalRef.current);
            statusIntervalRef.current = null;
          }
        }
      } catch (err) {
        console.error('Error fetching status:', err);
      }
    };

    // If we're loading, poll the status every 2 seconds
    if (loading && !statusIntervalRef.current) {
      fetchStatus(); // Fetch immediately
      statusIntervalRef.current = setInterval(fetchStatus, 2000);
    }

    // Clean up interval on unmount
    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, [loading]);

  // Check face processing status
  useEffect(() => {
    const checkFaceProcessingStatus = async () => {
      try {
        const response = await axios.get('/api/status');
        setFaceProcessingStatus(response.data);
        
        if (response.data && response.data.is_processing === false) {
          if (faceStatusIntervalRef.current) {
            clearInterval(faceStatusIntervalRef.current);
            faceStatusIntervalRef.current = null;
          }
        }
      } catch (err) {
        console.error('Error checking face processing status:', err);
      }
    };

    // Initial check
    checkFaceProcessingStatus();

    // Set up interval for checking face processing status
    if (faceProcessingStatus && faceProcessingStatus.is_processing && !faceStatusIntervalRef.current) {
      faceStatusIntervalRef.current = setInterval(checkFaceProcessingStatus, 3000);
    }

    // Clean up interval on unmount
    return () => {
      if (faceStatusIntervalRef.current) {
        clearInterval(faceStatusIntervalRef.current);
      }
    };
  }, [faceProcessingStatus]);

  const handleDirectorySubmit = async (e) => {
    e.preventDefault();
    
    if (!directoryPath.trim()) {
      setError('Please enter a directory path');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);
      
      await axios.post(`/api/process-directory?directory_path=${encodeURIComponent(directoryPath)}`);
      
      // Status updates will be handled by the useEffect
    } catch (err) {
      console.error('Error processing directory:', err);
      setError(err.response?.data?.detail || 'Failed to process directory');
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    
    if (files.length === 0) {
      setError('Please select at least one photo');
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);
      
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      
      await axios.post('/api/upload-photos', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // Status updates will be handled by the useEffect
    } catch (err) {
      console.error('Error uploading photos:', err);
      setError(err.response?.data?.detail || 'Failed to upload photos');
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const getProgressPercentage = () => {
    if (!status.total_photos || status.total_photos === 0) return 0;
    return Math.round((status.processed_photos / status.total_photos) * 100);
  };

  const getStatusText = () => {
    switch (status.current_stage) {
      case 'analyzing':
        return 'Analyzing photos...';
      case 'generating_narratives':
        return 'Generating narratives...';
      case 'complete':
        return 'Processing complete!';
      case 'uploading':
        return 'Uploading photos...';
      default:
        return 'Processing...';
    }
  };

  // Face detection functions
  const startFaceDetection = async () => {
    try {
      await axios.post('/api/update-face-data');
      const response = await axios.get('/api/status');
      setFaceProcessingStatus(response.data);
    } catch (err) {
      console.error('Error starting face detection:', err);
      setError('Failed to start face detection process. Please try again later.');
    }
  };

  const getFaceStatusMessage = () => {
    if (!faceProcessingStatus || !faceProcessingStatus.is_processing) {
      return null;
    }

    const stage = faceProcessingStatus.current_stage;
    
    if (stage === 'preparing_face_data_update') {
      return 'Preparing for face detection...';
    } else if (stage === 'detecting_faces') {
      const processed = faceProcessingStatus.processed_photos || 0;
      const total = faceProcessingStatus.total_photos || 0;
      const faces = faceProcessingStatus.faces_detected || 0;
      return `Detecting faces: ${processed}/${total} photos processed (${faces} faces found)`;
    } else if (stage === 'clustering_faces') {
      return 'Grouping similar faces together...';
    } else {
      return `Processing: ${stage}`;
    }
  };

  return (
    <div className="py-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-800 mb-8 text-center">Process Your Photos</h1>
      
      {success && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-8" role="alert">
          <strong className="font-bold">Success!</strong>
          <span className="block sm:inline"> Your photos have been processed and narratives have been generated.</span>
          <div className="mt-3">
            <Link to="/narratives" className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition duration-300">
              View Narratives
            </Link>
          </div>
        </div>
      )}
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-8" role="alert">
          <strong className="font-bold">Error!</strong>
          <span className="block sm:inline"> {error}</span>
        </div>
      )}
      
      {loading && (
        <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded relative mb-8" role="alert">
          <strong className="font-bold">{getStatusText()}</strong>
          
          {status.total_photos > 0 && (
            <div className="mt-3">
              <div className="w-full bg-gray-200 rounded-full h-4">
                <div 
                  className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${getProgressPercentage()}%` }}
                ></div>
              </div>
              <div className="text-sm mt-1">
                {status.processed_photos} of {status.total_photos} photos processed ({getProgressPercentage()}%)
              </div>
            </div>
          )}
        </div>
      )}

      {/* Face processing status */}
      {faceProcessingStatus && faceProcessingStatus.is_processing && (
        <div className="mb-8 bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded relative">
          <div className="flex items-center">
            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-3"></div>
            <span>{getFaceStatusMessage()}</span>
          </div>
          {faceProcessingStatus.processed_photos !== undefined && faceProcessingStatus.total_photos > 0 && (
            <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
              <div 
                className="bg-blue-500 h-2.5 rounded-full" 
                style={{ width: `${(faceProcessingStatus.processed_photos / faceProcessingStatus.total_photos) * 100}%` }}
              ></div>
            </div>
          )}
        </div>
      )}
      
      {faceProcessingStatus && !faceProcessingStatus.is_processing && faceProcessingStatus.face_stats && (
        <div className="mb-8 bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded relative">
          <p className="font-medium">Face detection complete!</p>
          <p className="text-sm mt-1">
            Processed {faceProcessingStatus.face_stats.processed} photos, 
            detected {faceProcessingStatus.face_stats.faces_detected} faces, 
            identified {faceProcessingStatus.face_stats.unique_persons || 0} unique persons.
          </p>
        </div>
      )}
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* File Upload */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">1. Upload Photos</h2>
          <p className="text-gray-600 mb-6">
            Select photos from your device to upload and process.
          </p>
          
          <form onSubmit={handleFileUpload}>
            <div className="mb-4">
              <label htmlFor="photos" className="block text-gray-700 text-sm font-medium mb-2">
                Select Photos
              </label>
              <input
                type="file"
                id="photos"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="hidden"
                multiple
                accept="image/*"
                disabled={loading}
              />
              <div 
                onClick={() => fileInputRef.current.click()}
                className="w-full px-3 py-6 border-2 border-dashed border-gray-300 rounded-md text-center cursor-pointer hover:border-blue-500 transition duration-300"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 mx-auto text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p className="mt-2 text-sm text-gray-600">
                  {files.length > 0 ? `${files.length} files selected` : 'Click to select photos or drag and drop'}
                </p>
              </div>
            </div>
            
            <button
              type="submit"
              className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition duration-300 disabled:bg-gray-400"
              disabled={loading || files.length === 0}
            >
              Upload and Process
            </button>
          </form>
        </div>

        {/* Face Detection */}
        <div className="bg-white rounded-lg shadow-md p-6 flex flex-col">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">2. Detect Faces</h2>
          <p className="text-gray-600 mb-6">
            After processing your photos, run face detection to identify people in your photos.
            This will help organize your photos by the people in them.
          </p>
          
          <button
            onClick={startFaceDetection}
            disabled={faceProcessingStatus && faceProcessingStatus.is_processing}
            className={`w-full flex items-center justify-center px-4 py-2 rounded-md mt-auto ${
              faceProcessingStatus && faceProcessingStatus.is_processing
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
      </div>
      
      {/* Regenerate Narratives */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-8">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">3. Regenerate Narratives</h2>
        <p className="text-gray-600 mb-6">
          If you've already processed your photos but want to regenerate the narratives without reprocessing everything, use this option.
          This is useful if narrative generation previously failed or if you made changes to the code that affects narrative generation.
        </p>
        
        <button
          onClick={async () => {
            try {
              setLoading(true);
              setError(null);
              setSuccess(false);
              
              await axios.post('/api/narratives');
              
              // Status updates will be handled by the useEffect
            } catch (err) {
              console.error('Error regenerating narratives:', err);
              setError(err.response?.data?.detail || 'Failed to regenerate narratives');
              setLoading(false);
            }
          }}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition duration-300 disabled:bg-gray-400"
          disabled={loading}
        >
          Regenerate Narratives
        </button>
      </div>
      
      <div className="bg-gray-100 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">What Happens Next?</h2>
        <ol className="list-decimal list-inside space-y-2 text-gray-700">
          <li>Your photos will be analyzed using AI to generate detailed descriptions.</li>
          <li>The descriptions will be analyzed to identify meaningful life narratives.</li>
          <li>The most representative photos will be selected for each narrative.</li>
          <li>If you run face detection, people in your photos will be identified and grouped.</li>
          <li>Once processing is complete, you'll be able to explore your narratives.</li>
        </ol>
      </div>
    </div>
  );
};

export default ProcessPhotos; 
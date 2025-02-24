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

  return (
    <div className="py-8">
      <h1 className="text-3xl font-bold text-gray-800 mb-8 text-center">Process Your Photos</h1>
      
      {success && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-8" role="alert">
          <strong className="font-bold">Success!</strong>
          <span className="block sm:inline"> Your photos have been processed and narratives have been generated.</span>
          <div className="mt-3">
            <Link to="/narratives" className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
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
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Directory Processing */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Process Photos from Directory</h2>
          <p className="text-gray-600 mb-6">
            Enter the path to a directory containing photos, and we'll process all the photos in that directory.
          </p>
          
          <form onSubmit={handleDirectorySubmit}>
            <div className="mb-4">
              <label htmlFor="directoryPath" className="block text-gray-700 text-sm font-medium mb-2">
                Directory Path
              </label>
              <input
                type="text"
                id="directoryPath"
                value={directoryPath}
                onChange={(e) => setDirectoryPath(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="/path/to/photos"
                disabled={loading}
              />
            </div>
            
            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition duration-300 disabled:bg-gray-400"
              disabled={loading}
            >
              Process Directory
            </button>
          </form>
        </div>
        
        {/* File Upload */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Upload Photos</h2>
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
      </div>
      
      <div className="mt-8 bg-gray-100 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">What Happens Next?</h2>
        <ol className="list-decimal list-inside space-y-2 text-gray-700">
          <li>Your photos will be analyzed using AI to generate detailed descriptions.</li>
          <li>The descriptions will be analyzed to identify meaningful life narratives.</li>
          <li>The most representative photos will be selected for each narrative.</li>
          <li>Once processing is complete, you'll be able to explore your narratives.</li>
        </ol>
      </div>
    </div>
  );
};

export default ProcessPhotos; 
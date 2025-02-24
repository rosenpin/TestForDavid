import React from 'react';
import { Link } from 'react-router-dom';

const Home = () => {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <h1 className="text-4xl font-bold text-center text-gray-800 mb-6">
        Discover the Stories in Your Photos
      </h1>
      
      <p className="text-xl text-center text-gray-600 max-w-3xl mb-10">
        Life Narrative Explorer uses AI to analyze your photos and identify meaningful narratives 
        that tell the story of your life experiences, adventures, and memories.
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl w-full mb-12">
        <div className="bg-white rounded-lg shadow-md p-8 flex flex-col items-center text-center">
          <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold text-gray-800 mb-3">Process Your Photos</h2>
          <p className="text-gray-600 mb-6">
            Upload your photos or point to a directory, and our AI will analyze them to identify people, 
            places, activities, and emotions.
          </p>
          <Link to="/process" className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
            Get Started
          </Link>
        </div>
        
        <div className="bg-white rounded-lg shadow-md p-8 flex flex-col items-center text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold text-gray-800 mb-3">Explore Narratives</h2>
          <p className="text-gray-600 mb-6">
            Discover the meaningful stories and themes in your photo collection, 
            from family gatherings to travel adventures.
          </p>
          <Link to="/narratives" className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-6 rounded-md transition duration-300">
            View Narratives
          </Link>
        </div>
      </div>
      
      <div className="bg-gray-100 rounded-lg p-8 max-w-4xl w-full">
        <h2 className="text-2xl font-semibold text-gray-800 mb-4">How It Works</h2>
        <ol className="list-decimal list-inside space-y-3 text-gray-700">
          <li><span className="font-medium">Photo Analysis:</span> AI generates descriptions for each photo, focusing on key details.</li>
          <li><span className="font-medium">Narrative Generation:</span> The descriptions are analyzed to identify meaningful life narratives.</li>
          <li><span className="font-medium">Photo Selection:</span> The most representative photos are selected for each narrative.</li>
          <li><span className="font-medium">Exploration:</span> Browse through your life narratives and relive your memories.</li>
        </ol>
      </div>
    </div>
  );
};

export default Home; 
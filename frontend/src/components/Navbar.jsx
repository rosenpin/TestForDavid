import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const Navbar = () => {
  const location = useLocation();
  
  const isActive = (path) => {
    return location.pathname === path ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-600 hover:text-blue-600';
  };
  
  return (
    <nav className="bg-white shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center py-4">
          <Link to="/" className="text-2xl font-bold text-blue-600">
            Life Narrative Explorer
          </Link>
          
          <div className="flex space-x-6">
            <Link to="/" className={`${isActive('/')} font-medium`}>
              Home
            </Link>
            <Link to="/narratives" className={`${isActive('/narratives')} font-medium`}>
              Narratives
            </Link>
            <Link to="/process" className={`${isActive('/process')} font-medium`}>
              Process Photos
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar; 
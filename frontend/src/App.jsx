import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import NarrativeList from './pages/NarrativeList';
import NarrativeDetail from './pages/NarrativeDetail';
import ProcessPhotos from './pages/ProcessPhotos';
import PersonDetail from './pages/PersonDetail';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/narratives" element={<NarrativeList />} />
          <Route path="/narratives/:id" element={<NarrativeDetail />} />
          <Route path="/process" element={<ProcessPhotos />} />
          <Route path="/persons/:id" element={<PersonDetail />} />
        </Routes>
      </main>
      <footer className="bg-white py-6 text-center text-gray-500 text-sm">
        <p>Life Narrative Explorer &copy; {new Date().getFullYear()}</p>
      </footer>
    </div>
  );
}

export default App; 
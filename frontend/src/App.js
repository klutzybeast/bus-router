import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import CounselorApp from "@/pages/CounselorApp";
import ProtectedApp from "@/components/ProtectedApp";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/counselor" element={<CounselorApp />} />
          <Route path="/*" element={<ProtectedApp />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;

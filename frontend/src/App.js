import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import BusRoutingMap from "@/components/BusRoutingMap";
import StaffZoneLookupPage from "@/pages/StaffZoneLookupPage";
import CounselorApp from "@/pages/CounselorApp";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<BusRoutingMap />} />
          <Route path="/staff-lookup" element={<StaffZoneLookupPage />} />
          <Route path="/counselor" element={<CounselorApp />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
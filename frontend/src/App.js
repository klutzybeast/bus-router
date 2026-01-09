import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import BusRoutingMap from "@/components/BusRoutingMap";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<BusRoutingMap />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
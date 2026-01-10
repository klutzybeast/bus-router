import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { Toaster } from "sonner";

// Suppress PostHog clone errors
window.addEventListener('error', (e) => {
  if (e.message && e.message.includes('postMessage') && e.message.includes('cloned')) {
    e.preventDefault();
    e.stopPropagation();
    return false;
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
    <Toaster position="top-right" richColors />
  </React.StrictMode>,
);

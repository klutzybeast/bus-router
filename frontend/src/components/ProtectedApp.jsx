import React from "react";
import { Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import PasscodeGate, { useAuth, LockButton } from "@/components/PasscodeGate";
import BusRoutingMap from "@/components/BusRoutingMap";
import StaffZoneLookupPage from "@/pages/StaffZoneLookupPage";

export default function ProtectedApp() {
  const { isAuthenticated, initialized, authenticate, lock } = useAuth();

  if (!initialized) {
    return (
      <div className="fixed inset-0 flex items-center justify-center" style={{ background: "#0f2742" }}>
        <div className="w-8 h-8 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <PasscodeGate onAuthenticated={authenticate} />
        <Toaster position="top-center" richColors />
      </>
    );
  }

  return (
    <>
      <LockButton onLock={lock} />
      <Routes>
        <Route path="/" element={<BusRoutingMap />} />
        <Route path="/staff-lookup" element={<StaffZoneLookupPage />} />
      </Routes>
      <Toaster position="top-center" richColors />
    </>
  );
}

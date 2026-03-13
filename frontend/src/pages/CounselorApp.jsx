import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, MapPin, Bus, Users, LogOut, Loader2, Navigation, Share, AlertCircle, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function CounselorApp() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busData, setBusData] = useState(null);
  const [attendance, setAttendance] = useState({});
  const [gpsStatus, setGpsStatus] = useState('idle');
  const [gpsMessage, setGpsMessage] = useState('');
  const [lastGpsUpdate, setLastGpsUpdate] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [locationCount, setLocationCount] = useState(0);
  
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const busNumberRef = useRef(null);

  // Check for saved session on mount
  useEffect(() => {
    const savedBus = localStorage.getItem('counselor_bus');
    if (savedBus) {
      handleAutoLogin(savedBus);
    }
  }, []);

  // Auto-login with saved bus number
  const handleAutoLogin = async (savedPin) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: savedPin })
      });

      const data = await response.json();

      if (response.ok) {
        setBusData(data);
        setAttendance(data.attendance || {});
        setIsLoggedIn(true);
        busNumberRef.current = data.bus_number;
        startGpsTracking();
      } else {
        localStorage.removeItem('counselor_bus');
      }
    } catch (err) {
      localStorage.removeItem('counselor_bus');
    } finally {
      setLoading(false);
    }
  };

  // Handle manual login
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Invalid bus number');
      }

      localStorage.setItem('counselor_bus', pin);
      setBusData(data);
      setAttendance(data.attendance || {});
      setIsLoggedIn(true);
      busNumberRef.current = data.bus_number;
      startGpsTracking();
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Send location to server
  const sendLocationUpdate = useCallback(async (position) => {
    const busNumber = busNumberRef.current;
    if (!busNumber) return;

    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/location`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bus_number: busNumber,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          speed: position.coords.speed,
          heading: position.coords.heading
        })
      });

      if (response.ok) {
        setLastGpsUpdate(new Date());
        setLocationCount(prev => prev + 1);
        setGpsMessage(`Sent: ${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`);
      } else {
        setGpsMessage('Server error - retrying...');
      }
    } catch (err) {
      setGpsMessage('Network error - retrying...');
    }
  }, []);

  // Start GPS tracking
  const startGpsTracking = useCallback(() => {
    setGpsStatus('requesting');
    setGpsMessage('Requesting GPS access...');

    if (!navigator.geolocation) {
      setGpsStatus('error');
      setGpsMessage('GPS not supported on this browser');
      return;
    }

    // Get current position
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsStatus('tracking');
        setGpsMessage('GPS connected!');
        sendLocationUpdate(position);

        // Watch position
        watchIdRef.current = navigator.geolocation.watchPosition(
          (pos) => sendLocationUpdate(pos),
          (err) => {
            setGpsMessage(`Watch error: ${err.message}`);
          },
          { enableHighAccuracy: true, maximumAge: 15000, timeout: 30000 }
        );

        // Backup polling every 30 seconds
        gpsIntervalRef.current = setInterval(() => {
          navigator.geolocation.getCurrentPosition(
            sendLocationUpdate,
            () => {},
            { enableHighAccuracy: true, timeout: 20000 }
          );
        }, 30000);
      },
      (err) => {
        setGpsStatus('error');
        if (err.code === 1) {
          setGpsMessage('Permission denied - enable location in browser settings');
        } else if (err.code === 2) {
          setGpsMessage('GPS unavailable - enable location services');
        } else if (err.code === 3) {
          setGpsMessage('GPS timeout - trying again...');
          setTimeout(startGpsTracking, 3000);
        } else {
          setGpsMessage(`GPS error: ${err.message}`);
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  }, [sendLocationUpdate]);

  // Stop GPS tracking
  const stopGpsTracking = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    if (gpsIntervalRef.current) {
      clearInterval(gpsIntervalRef.current);
      gpsIntervalRef.current = null;
    }
  }, []);

  // Handle logout
  const handleLogout = () => {
    stopGpsTracking();
    localStorage.removeItem('counselor_bus');
    busNumberRef.current = null;
    setIsLoggedIn(false);
    setBusData(null);
    setAttendance({});
    setPin('');
    setLocationCount(0);
    setGpsStatus('idle');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => stopGpsTracking();
  }, [stopGpsTracking]);

  // Mark attendance
  const markAttendance = async (camperId, status) => {
    if (!busData) return;
    setAttendance(prev => ({ ...prev, [camperId]: status }));

    try {
      await fetch(`${API_URL}/api/bus-tracking/attendance?bus_number=${encodeURIComponent(busData.bus_number)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camper_id: camperId, status })
      });
    } catch (err) {
      // Revert on error
      setAttendance(prev => {
        const newState = { ...prev };
        delete newState[camperId];
        return newState;
      });
    }
  };

  // PWA install prompt
  useEffect(() => {
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || 
                         window.navigator.standalone === true;
    if (!isStandalone && !localStorage.getItem('pwa_prompt_dismissed')) {
      const timer = setTimeout(() => setShowInstallPrompt(true), 3000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Loading screen
  if (loading && !isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center">
        <div className="text-center text-white">
          <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Login Screen
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Bus className="w-10 h-10 text-blue-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-800">Bus Tracker</h1>
            <p className="text-gray-500 mt-1">Enter your bus number</p>
          </div>

          <form onSubmit={handleLogin}>
            <div className="mb-6">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="Bus #"
                className="w-full px-4 py-4 text-3xl text-center font-bold border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition"
                autoFocus
              />
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm text-center">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !pin}
              className="w-full py-4 bg-blue-600 text-white text-lg font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition"
            >
              {loading ? <Loader2 className="w-6 h-6 animate-spin" /> : 'Go'}
            </button>
          </form>

          <p className="text-center text-xs text-gray-400 mt-6">
            Tip: Add to Home Screen for quick access
          </p>
        </div>
      </div>
    );
  }

  // Main Dashboard
  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const unmarkedCount = (busData?.campers?.length || 0) - presentCount - absentCount;

  return (
    <div className="fixed inset-0 flex flex-col bg-gray-100">
      {/* Install Prompt Banner */}
      {showInstallPrompt && (
        <div className="bg-blue-700 text-white p-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2 text-sm">
            <Share className="w-4 h-4" />
            <span>Add to Home Screen</span>
          </div>
          <button 
            onClick={() => {
              setShowInstallPrompt(false);
              localStorage.setItem('pwa_prompt_dismissed', 'true');
            }}
            className="text-white/80 hover:text-white text-sm px-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Header - Fixed */}
      <header className="bg-blue-600 text-white p-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">{busData?.bus_number}</h1>
          </div>
          <button onClick={handleLogout} className="p-2 hover:bg-blue-700 rounded-lg">
            <LogOut className="w-5 h-5" />
          </button>
        </div>

        {/* GPS Status */}
        <div className="mt-2 flex items-center gap-2">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
            gpsStatus === 'tracking' ? 'bg-green-500' :
            gpsStatus === 'requesting' ? 'bg-yellow-500' :
            gpsStatus === 'error' ? 'bg-red-500' : 'bg-gray-500'
          }`}>
            <Navigation className={`w-3 h-3 ${gpsStatus === 'tracking' ? 'animate-pulse' : ''}`} />
            {gpsStatus === 'tracking' ? `Active (${locationCount})` : 
             gpsStatus === 'requesting' ? 'Starting...' :
             gpsStatus === 'error' ? 'Error' : 'Off'}
          </div>
          {gpsStatus === 'error' && (
            <button onClick={startGpsTracking} className="px-2 py-1 bg-white/20 rounded-full text-xs">
              Retry
            </button>
          )}
        </div>
        {gpsMessage && <p className="text-xs text-blue-200 mt-1 truncate">{gpsMessage}</p>}
      </header>

      {/* Stats Bar - Fixed */}
      <div className="bg-white border-b p-2 flex justify-around flex-shrink-0">
        <div className="text-center">
          <div className="text-xl font-bold text-green-600">{presentCount}</div>
          <div className="text-[10px] text-gray-500">Present</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-bold text-red-600">{absentCount}</div>
          <div className="text-[10px] text-gray-500">Absent</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-bold text-gray-400">{unmarkedCount}</div>
          <div className="text-[10px] text-gray-500">Unmarked</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-bold text-blue-600">{busData?.campers?.length || 0}</div>
          <div className="text-[10px] text-gray-500">Total</div>
        </div>
      </div>

      {/* Camper List - Scrollable */}
      <div className="flex-1 overflow-y-auto overscroll-contain p-2" style={{ WebkitOverflowScrolling: 'touch' }}>
        <div className="space-y-2 pb-4">
          {busData?.campers?.map((camper, index) => {
            const status = attendance[camper.id];
            return (
              <div
                key={camper.id}
                className={`bg-white rounded-lg shadow-sm border-2 ${
                  status === 'present' ? 'border-green-400 bg-green-50' :
                  status === 'absent' ? 'border-red-400 bg-red-50' :
                  'border-gray-200'
                }`}
              >
                <div className="p-2 flex items-center justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="text-gray-400 text-xs w-5">#{index + 1}</span>
                      <span className="font-medium text-sm text-gray-800 truncate">
                        {camper.first_name} {camper.last_name}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
                    <button
                      onClick={() => markAttendance(camper.id, 'present')}
                      className={`p-2 rounded-lg ${
                        status === 'present'
                          ? 'bg-green-500 text-white'
                          : 'bg-gray-100 text-gray-400 active:bg-green-200'
                      }`}
                    >
                      <CheckCircle className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => markAttendance(camper.id, 'absent')}
                      className={`p-2 rounded-lg ${
                        status === 'absent'
                          ? 'bg-red-500 text-white'
                          : 'bg-gray-100 text-gray-400 active:bg-red-200'
                      }`}
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {(!busData?.campers || busData.campers.length === 0) && (
          <div className="text-center py-12 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No campers on this bus</p>
          </div>
        )}
      </div>

      {/* Footer - Fixed */}
      <div className="bg-white border-t p-2 text-center text-xs text-gray-400 flex-shrink-0 safe-area-pb">
        {busData?.date}
      </div>
    </div>
  );
}

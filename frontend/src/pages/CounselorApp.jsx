import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, MapPin, Bus, Users, LogOut, Loader2, Navigation } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function CounselorApp() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busData, setBusData] = useState(null);
  const [attendance, setAttendance] = useState({});
  const [gpsStatus, setGpsStatus] = useState('idle'); // idle, tracking, error
  const [lastGpsUpdate, setLastGpsUpdate] = useState(null);
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);

  // Handle login
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

      setBusData(data);
      setAttendance(data.attendance || {});
      setIsLoggedIn(true);
      
      // Start GPS tracking after successful login
      startGpsTracking(data.bus_number);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Start GPS tracking
  const startGpsTracking = useCallback((busNumber) => {
    if (!navigator.geolocation) {
      setGpsStatus('error');
      console.error('Geolocation not supported');
      return;
    }

    setGpsStatus('tracking');

    // Function to send location update
    const sendLocationUpdate = async (position) => {
      try {
        await fetch(`${API_URL}/api/bus-tracking/location`, {
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
        setLastGpsUpdate(new Date());
      } catch (err) {
        console.error('Failed to send location:', err);
      }
    };

    // Watch position continuously
    watchIdRef.current = navigator.geolocation.watchPosition(
      sendLocationUpdate,
      (err) => {
        console.error('GPS error:', err);
        setGpsStatus('error');
      },
      {
        enableHighAccuracy: true,
        maximumAge: 10000,
        timeout: 30000
      }
    );

    // Also send updates every 30 seconds as backup
    gpsIntervalRef.current = setInterval(() => {
      navigator.geolocation.getCurrentPosition(
        sendLocationUpdate,
        (err) => console.error('GPS interval error:', err),
        { enableHighAccuracy: true, timeout: 20000 }
      );
    }, 30000);

  }, []);

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
    setGpsStatus('idle');
  }, []);

  // Handle logout
  const handleLogout = () => {
    stopGpsTracking();
    setIsLoggedIn(false);
    setBusData(null);
    setAttendance({});
    setPin('');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopGpsTracking();
    };
  }, [stopGpsTracking]);

  // Mark attendance
  const markAttendance = async (camperId, status) => {
    if (!busData) return;

    // Optimistic update
    setAttendance(prev => ({ ...prev, [camperId]: status }));

    try {
      await fetch(`${API_URL}/api/bus-tracking/attendance?bus_number=${encodeURIComponent(busData.bus_number)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          camper_id: camperId,
          status: status
        })
      });
    } catch (err) {
      console.error('Failed to update attendance:', err);
      // Revert on error
      setAttendance(prev => {
        const newState = { ...prev };
        delete newState[camperId];
        return newState;
      });
    }
  };

  // Login Screen
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-sm">
          <div className="text-center mb-8">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Bus className="w-10 h-10 text-blue-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-800">Bus Counselor</h1>
            <p className="text-gray-500 mt-1">Enter your bus number to start</p>
          </div>

          <form onSubmit={handleLogin}>
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bus Number (PIN)
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="e.g., 06"
                className="w-full px-4 py-3 text-2xl text-center font-bold border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition"
                autoFocus
              />
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !pin}
              className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Logging in...
                </>
              ) : (
                <>
                  <Bus className="w-5 h-5" />
                  Start Tracking
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // Main Counselor Dashboard
  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const unmarkedCount = (busData?.campers?.length || 0) - presentCount - absentCount;

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-blue-600 text-white p-4 sticky top-0 z-10 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">{busData?.bus_number}</h1>
            <p className="text-blue-100 text-sm">
              {busData?.driver && `Driver: ${busData.driver}`}
              {busData?.driver && busData?.counselor && ' • '}
              {busData?.counselor && `Counselor: ${busData.counselor}`}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 hover:bg-blue-700 rounded-lg transition"
            title="Logout"
          >
            <LogOut className="w-6 h-6" />
          </button>
        </div>

        {/* GPS Status Bar */}
        <div className="mt-3 flex items-center gap-2 text-sm">
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${
            gpsStatus === 'tracking' ? 'bg-green-500' :
            gpsStatus === 'error' ? 'bg-red-500' : 'bg-gray-500'
          }`}>
            <Navigation className="w-3 h-3" />
            {gpsStatus === 'tracking' ? 'GPS Active' : gpsStatus === 'error' ? 'GPS Error' : 'GPS Off'}
          </div>
          {lastGpsUpdate && (
            <span className="text-blue-100 text-xs">
              Last update: {lastGpsUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {/* Stats Bar */}
      <div className="bg-white border-b p-3 flex justify-around">
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{presentCount}</div>
          <div className="text-xs text-gray-500">Present</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-red-600">{absentCount}</div>
          <div className="text-xs text-gray-500">Absent</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-gray-400">{unmarkedCount}</div>
          <div className="text-xs text-gray-500">Unmarked</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">{busData?.campers?.length || 0}</div>
          <div className="text-xs text-gray-500">Total</div>
        </div>
      </div>

      {/* Camper List */}
      <div className="p-4">
        <div className="space-y-3">
          {busData?.campers?.map((camper, index) => {
            const status = attendance[camper.id];
            return (
              <div
                key={camper.id}
                className={`bg-white rounded-xl shadow-sm border-2 transition ${
                  status === 'present' ? 'border-green-400 bg-green-50' :
                  status === 'absent' ? 'border-red-400 bg-red-50' :
                  'border-gray-200'
                }`}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-gray-400 text-sm font-medium">#{index + 1}</span>
                        <h3 className="font-semibold text-gray-800 truncate">
                          {camper.first_name} {camper.last_name}
                        </h3>
                      </div>
                      {camper.address && (
                        <p className="text-sm text-gray-500 mt-1 flex items-start gap-1">
                          <MapPin className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span className="truncate">{camper.address}</span>
                        </p>
                      )}
                    </div>

                    {/* Attendance Buttons */}
                    <div className="flex gap-2 flex-shrink-0">
                      <button
                        onClick={() => markAttendance(camper.id, 'present')}
                        className={`p-3 rounded-xl transition ${
                          status === 'present'
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-100 text-gray-400 hover:bg-green-100 hover:text-green-600'
                        }`}
                        title="Present"
                      >
                        <CheckCircle className="w-6 h-6" />
                      </button>
                      <button
                        onClick={() => markAttendance(camper.id, 'absent')}
                        className={`p-3 rounded-xl transition ${
                          status === 'absent'
                            ? 'bg-red-500 text-white'
                            : 'bg-gray-100 text-gray-400 hover:bg-red-100 hover:text-red-600'
                        }`}
                        title="Absent"
                      >
                        <XCircle className="w-6 h-6" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {(!busData?.campers || busData.campers.length === 0) && (
          <div className="text-center py-12 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No campers assigned to this bus</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-3 text-center text-xs text-gray-400">
        {busData?.date && `Date: ${busData.date}`}
      </div>
    </div>
  );
}

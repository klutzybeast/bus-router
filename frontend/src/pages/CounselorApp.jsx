import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, Bus, Users, LogOut, Loader2, Navigation } from 'lucide-react';

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
  const [locationCount, setLocationCount] = useState(0);
  
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const busNumberRef = useRef(null);

  useEffect(() => {
    const savedBus = localStorage.getItem('counselor_bus');
    if (savedBus) {
      handleAutoLogin(savedBus);
    }
  }, []);

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
      if (!response.ok) throw new Error(data.detail || 'Invalid bus number');
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
        setGpsMessage('');
      }
    } catch (err) {
      setGpsMessage('Network error');
    }
  }, []);

  const startGpsTracking = useCallback(() => {
    setGpsStatus('requesting');
    setGpsMessage('Getting GPS...');
    if (!navigator.geolocation) {
      setGpsStatus('error');
      setGpsMessage('GPS not supported');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsStatus('tracking');
        setGpsMessage('');
        sendLocationUpdate(position);
        watchIdRef.current = navigator.geolocation.watchPosition(
          sendLocationUpdate,
          () => {},
          { enableHighAccuracy: true, maximumAge: 15000, timeout: 30000 }
        );
        gpsIntervalRef.current = setInterval(() => {
          navigator.geolocation.getCurrentPosition(sendLocationUpdate, () => {}, { enableHighAccuracy: true, timeout: 20000 });
        }, 30000);
      },
      (err) => {
        setGpsStatus('error');
        setGpsMessage(err.code === 1 ? 'Enable location in settings' : 'GPS unavailable');
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  }, [sendLocationUpdate]);

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

  useEffect(() => {
    return () => stopGpsTracking();
  }, [stopGpsTracking]);

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
      setAttendance(prev => {
        const newState = { ...prev };
        delete newState[camperId];
        return newState;
      });
    }
  };

  if (loading && !isLoggedIn) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #2563eb, #1e40af)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'white' }}>
          <Loader2 style={{ width: 48, height: 48, animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #2563eb, #1e40af)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
        <div style={{ background: 'white', borderRadius: 16, padding: 32, width: '100%', maxWidth: 320, boxShadow: '0 25px 50px rgba(0,0,0,0.25)' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{ width: 80, height: 80, background: '#dbeafe', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <Bus style={{ width: 40, height: 40, color: '#2563eb' }} />
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 'bold', color: '#1f2937', margin: 0 }}>Bus Tracker</h1>
            <p style={{ color: '#6b7280', marginTop: 4 }}>Enter your bus number</p>
          </div>
          <form onSubmit={handleLogin}>
            <input
              type="text"
              inputMode="numeric"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="Bus #"
              style={{ width: '100%', padding: 16, fontSize: 28, textAlign: 'center', fontWeight: 'bold', border: '2px solid #e5e7eb', borderRadius: 12, outline: 'none', boxSizing: 'border-box' }}
              autoFocus
            />
            {error && <div style={{ marginTop: 16, padding: 12, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#dc2626', fontSize: 14, textAlign: 'center' }}>{error}</div>}
            <button type="submit" disabled={loading || !pin} style={{ width: '100%', padding: 16, marginTop: 24, background: '#2563eb', color: 'white', fontSize: 18, fontWeight: 600, border: 'none', borderRadius: 12, cursor: 'pointer', opacity: loading || !pin ? 0.5 : 1 }}>
              {loading ? 'Loading...' : 'Go'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const unmarkedCount = (busData?.campers?.length || 0) - presentCount - absentCount;

  return (
    <div style={{ minHeight: '100vh', background: '#f3f4f6', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ background: '#2563eb', color: 'white', padding: 12, flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 'bold' }}>{busData?.bus_number}</h1>
          <button onClick={handleLogout} style={{ background: 'transparent', border: 'none', color: 'white', padding: 8, cursor: 'pointer' }}>
            <LogOut style={{ width: 20, height: 20 }} />
          </button>
        </div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ 
            display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 20, fontSize: 12, fontWeight: 500,
            background: gpsStatus === 'tracking' ? '#22c55e' : gpsStatus === 'error' ? '#ef4444' : '#eab308'
          }}>
            <Navigation style={{ width: 12, height: 12 }} />
            {gpsStatus === 'tracking' ? `GPS (${locationCount})` : gpsStatus === 'error' ? 'GPS Off' : 'Starting...'}
          </span>
          {gpsStatus === 'error' && <button onClick={startGpsTracking} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', padding: '4px 10px', borderRadius: 20, fontSize: 12, cursor: 'pointer' }}>Retry</button>}
        </div>
        {gpsMessage && <p style={{ margin: '4px 0 0', fontSize: 11, color: '#bfdbfe' }}>{gpsMessage}</p>}
      </div>

      {/* Stats */}
      <div style={{ background: 'white', borderBottom: '1px solid #e5e7eb', padding: 8, display: 'flex', justifyContent: 'space-around', flexShrink: 0 }}>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 20, fontWeight: 'bold', color: '#22c55e' }}>{presentCount}</div><div style={{ fontSize: 10, color: '#6b7280' }}>Present</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 20, fontWeight: 'bold', color: '#ef4444' }}>{absentCount}</div><div style={{ fontSize: 10, color: '#6b7280' }}>Absent</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 20, fontWeight: 'bold', color: '#9ca3af' }}>{unmarkedCount}</div><div style={{ fontSize: 10, color: '#6b7280' }}>Unmarked</div></div>
        <div style={{ textAlign: 'center' }}><div style={{ fontSize: 20, fontWeight: 'bold', color: '#2563eb' }}>{busData?.campers?.length || 0}</div><div style={{ fontSize: 10, color: '#6b7280' }}>Total</div></div>
      </div>

      {/* Scrollable Camper List */}
      <div style={{ flex: 1, overflow: 'auto', WebkitOverflowScrolling: 'touch', padding: 8 }}>
        {busData?.campers?.map((camper, index) => {
          const status = attendance[camper.id];
          return (
            <div
              key={camper.id}
              style={{
                background: status === 'present' ? '#f0fdf4' : status === 'absent' ? '#fef2f2' : 'white',
                border: `2px solid ${status === 'present' ? '#86efac' : status === 'absent' ? '#fca5a5' : '#e5e7eb'}`,
                borderRadius: 10,
                padding: 10,
                marginBottom: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: '#9ca3af', fontSize: 12, width: 24 }}>#{index + 1}</span>
                  <span style={{ fontWeight: 500, fontSize: 14, color: '#1f2937', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {camper.first_name} {camper.last_name}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  onClick={() => markAttendance(camper.id, 'present')}
                  style={{
                    width: 44, height: 44, borderRadius: 10, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: status === 'present' ? '#22c55e' : '#f3f4f6',
                    color: status === 'present' ? 'white' : '#9ca3af'
                  }}
                >
                  <CheckCircle style={{ width: 24, height: 24 }} />
                </button>
                <button
                  onClick={() => markAttendance(camper.id, 'absent')}
                  style={{
                    width: 44, height: 44, borderRadius: 10, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: status === 'absent' ? '#ef4444' : '#f3f4f6',
                    color: status === 'absent' ? 'white' : '#9ca3af'
                  }}
                >
                  <XCircle style={{ width: 24, height: 24 }} />
                </button>
              </div>
            </div>
          );
        })}
        {(!busData?.campers || busData.campers.length === 0) && (
          <div style={{ textAlign: 'center', padding: 48, color: '#6b7280' }}>
            <Users style={{ width: 48, height: 48, margin: '0 auto 12px', opacity: 0.5 }} />
            <p>No campers on this bus</p>
          </div>
        )}
        {/* Bottom padding for safe area */}
        <div style={{ height: 40 }} />
      </div>
    </div>
  );
}

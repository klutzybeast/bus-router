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
  const [locationCount, setLocationCount] = useState(0);
  
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const busNumberRef = useRef(null);

  useEffect(() => {
    const savedBus = localStorage.getItem('counselor_bus');
    if (savedBus) handleAutoLogin(savedBus);
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
    } catch {
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
        setLocationCount(prev => prev + 1);
        setGpsMessage(`Sent! ${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`);
        setGpsStatus('tracking');
      } else {
        const errText = await response.text();
        setGpsMessage(`Server error: ${response.status}`);
        console.error('Location update failed:', response.status, errText);
      }
    } catch (err) {
      setGpsMessage(`Network error: ${err.message}`);
      console.error('Location send error:', err);
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
        watchIdRef.current = navigator.geolocation.watchPosition(sendLocationUpdate, () => {}, { enableHighAccuracy: true, maximumAge: 15000, timeout: 30000 });
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
    if (watchIdRef.current !== null) { navigator.geolocation.clearWatch(watchIdRef.current); watchIdRef.current = null; }
    if (gpsIntervalRef.current) { clearInterval(gpsIntervalRef.current); gpsIntervalRef.current = null; }
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

  useEffect(() => () => stopGpsTracking(), [stopGpsTracking]);

  const markAttendance = async (camperId, status) => {
    if (!busData) return;
    setAttendance(prev => ({ ...prev, [camperId]: status }));
    try {
      await fetch(`${API_URL}/api/bus-tracking/attendance?bus_number=${encodeURIComponent(busData.bus_number)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camper_id: camperId, status })
      });
    } catch {
      setAttendance(prev => { const n = { ...prev }; delete n[camperId]; return n; });
    }
  };

  // Login Screen
  if (!isLoggedIn) {
    return (
      <div className="login-screen">
        <style>{`
          .login-screen { min-height: 100vh; min-height: 100dvh; background: linear-gradient(135deg, #2563eb, #1e40af); display: flex; align-items: center; justify-content: center; padding: 16px; }
          .login-card { background: white; border-radius: 16px; padding: 32px; width: 100%; max-width: 320px; box-shadow: 0 25px 50px rgba(0,0,0,0.25); }
          .login-icon { width: 80px; height: 80px; background: #dbeafe; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
          .login-title { font-size: 24px; font-weight: bold; color: #1f2937; text-align: center; margin: 0; }
          .login-subtitle { color: #6b7280; text-align: center; margin-top: 4px; }
          .login-input { width: 100%; padding: 16px; font-size: 28px; text-align: center; font-weight: bold; border: 2px solid #e5e7eb; border-radius: 12px; outline: none; box-sizing: border-box; margin-top: 24px; }
          .login-input:focus { border-color: #2563eb; }
          .login-error { margin-top: 16px; padding: 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #dc2626; font-size: 14px; text-align: center; }
          .login-btn { width: 100%; padding: 16px; margin-top: 24px; background: #2563eb; color: white; font-size: 18px; font-weight: 600; border: none; border-radius: 12px; cursor: pointer; }
          .login-btn:disabled { opacity: 0.5; }
        `}</style>
        <div className="login-card">
          <div className="login-icon"><Bus size={40} color="#2563eb" /></div>
          <h1 className="login-title">Bus Tracker</h1>
          <p className="login-subtitle">Enter your bus number</p>
          <form onSubmit={handleLogin}>
            <input type="text" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="Bus #" className="login-input" autoFocus />
            {error && <div className="login-error">{error}</div>}
            <button type="submit" disabled={loading || !pin} className="login-btn">{loading ? 'Loading...' : 'Go'}</button>
          </form>
        </div>
      </div>
    );
  }

  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const unmarkedCount = (busData?.campers?.length || 0) - presentCount - absentCount;

  // Main Dashboard with fixed header and scrollable body
  return (
    <>
      <style>{`
        html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; }
        .app-container { position: fixed; top: 0; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; background: #f3f4f6; }
        .app-header { flex-shrink: 0; background: #2563eb; color: white; padding: 12px; }
        .header-row { display: flex; justify-content: space-between; align-items: center; }
        .header-title { margin: 0; font-size: 18px; font-weight: bold; }
        .logout-btn { background: transparent; border: none; color: white; padding: 8px; cursor: pointer; }
        .gps-row { margin-top: 8px; display: flex; align-items: center; gap: 8px; }
        .gps-badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
        .gps-tracking { background: #22c55e; }
        .gps-error { background: #ef4444; }
        .gps-requesting { background: #eab308; }
        .retry-btn { background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; cursor: pointer; }
        .gps-message { margin: 4px 0 0; font-size: 11px; color: #bfdbfe; }
        .stats-bar { flex-shrink: 0; background: white; border-bottom: 1px solid #e5e7eb; padding: 8px; display: flex; justify-content: space-around; }
        .stat { text-align: center; }
        .stat-num { font-size: 20px; font-weight: bold; }
        .stat-num-green { color: #22c55e; }
        .stat-num-red { color: #ef4444; }
        .stat-num-gray { color: #9ca3af; }
        .stat-num-blue { color: #2563eb; }
        .stat-label { font-size: 10px; color: #6b7280; }
        .camper-list { flex: 1; overflow-y: scroll; -webkit-overflow-scrolling: touch; padding: 8px; }
        .camper-card { background: white; border: 2px solid #e5e7eb; border-radius: 10px; padding: 10px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; }
        .camper-card-present { background: #f0fdf4; border-color: #86efac; }
        .camper-card-absent { background: #fef2f2; border-color: #fca5a5; }
        .camper-info { flex: 1; min-width: 0; }
        .camper-name-row { display: flex; align-items: center; gap: 6px; }
        .camper-num { color: #9ca3af; font-size: 12px; width: 24px; }
        .camper-name { font-weight: 500; font-size: 14px; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .camper-btns { display: flex; gap: 6px; flex-shrink: 0; }
        .att-btn { width: 44px; height: 44px; border-radius: 10px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .att-btn-default { background: #f3f4f6; color: #9ca3af; }
        .att-btn-present { background: #22c55e; color: white; }
        .att-btn-absent { background: #ef4444; color: white; }
        .empty-state { text-align: center; padding: 48px; color: #6b7280; }
        .list-end-spacer { height: 20px; }
      `}</style>
      <div className="app-container">
        <div className="app-header">
          <div className="header-row">
            <h1 className="header-title">{busData?.bus_number}</h1>
            <button onClick={handleLogout} className="logout-btn"><LogOut size={20} /></button>
          </div>
          <div className="gps-row">
            <span className={`gps-badge ${gpsStatus === 'tracking' ? 'gps-tracking' : gpsStatus === 'error' ? 'gps-error' : 'gps-requesting'}`}>
              <Navigation size={12} />
              {gpsStatus === 'tracking' ? `GPS (${locationCount})` : gpsStatus === 'error' ? 'GPS Off' : 'Starting...'}
            </span>
            {gpsStatus === 'error' && <button onClick={startGpsTracking} className="retry-btn">Retry</button>}
          </div>
          {gpsMessage && <p className="gps-message">{gpsMessage}</p>}
        </div>

        <div className="stats-bar">
          <div className="stat"><div className="stat-num stat-num-green">{presentCount}</div><div className="stat-label">Present</div></div>
          <div className="stat"><div className="stat-num stat-num-red">{absentCount}</div><div className="stat-label">Absent</div></div>
          <div className="stat"><div className="stat-num stat-num-gray">{unmarkedCount}</div><div className="stat-label">Unmarked</div></div>
          <div className="stat"><div className="stat-num stat-num-blue">{busData?.campers?.length || 0}</div><div className="stat-label">Total</div></div>
        </div>

        <div className="camper-list">
          {busData?.campers?.map((camper, index) => {
            const status = attendance[camper.id];
            return (
              <div key={camper.id} className={`camper-card ${status === 'present' ? 'camper-card-present' : status === 'absent' ? 'camper-card-absent' : ''}`}>
                <div className="camper-info">
                  <div className="camper-name-row">
                    <span className="camper-num">#{index + 1}</span>
                    <span className="camper-name">{camper.first_name} {camper.last_name}</span>
                  </div>
                </div>
                <div className="camper-btns">
                  <button onClick={() => markAttendance(camper.id, 'present')} className={`att-btn ${status === 'present' ? 'att-btn-present' : 'att-btn-default'}`}>
                    <CheckCircle size={24} />
                  </button>
                  <button onClick={() => markAttendance(camper.id, 'absent')} className={`att-btn ${status === 'absent' ? 'att-btn-absent' : 'att-btn-default'}`}>
                    <XCircle size={24} />
                  </button>
                </div>
              </div>
            );
          })}
          {(!busData?.campers || busData.campers.length === 0) && (
            <div className="empty-state">
              <Users size={48} style={{ opacity: 0.5, marginBottom: 12 }} />
              <p>No campers on this bus</p>
            </div>
          )}
          <div className="list-end-spacer" />
        </div>
      </div>
    </>
  );
}

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, Bus, Users, LogOut, Navigation, Calendar, Trash2, ArrowLeft, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const APP_VERSION = "v2.7";
const ADMIN_PIN = "admin";

function getTodayEST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}

function isAttendanceClosed() {
  const now = new Date().toLocaleString('en-US', { timeZone: 'America/New_York', hour12: false, hour: '2-digit', minute: '2-digit' });
  const [h, m] = now.split(':').map(Number);
  return h > 9 || (h === 9 && m >= 30);
}

export default function CounselorApp() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [pin, setPin] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busData, setBusData] = useState(null);
  const [attendance, setAttendance] = useState({});
  const [selectedDate, setSelectedDate] = useState(getTodayEST());
  const [gpsStatus, setGpsStatus] = useState('idle');
  const [gpsMessage, setGpsMessage] = useState('');
  const [locationCount, setLocationCount] = useState(0);
  const [wakeLockActive, setWakeLockActive] = useState(false);
  const [attendanceClosed, setAttendanceClosed] = useState(isAttendanceClosed());
  const [attendanceUnlocked, setAttendanceUnlocked] = useState(() => localStorage.getItem('attendance_unlocked') === 'true');
  // Admin state
  const [adminDates, setAdminDates] = useState([]);
  const [adminBus, setAdminBus] = useState('');
  const [adminResult, setAdminResult] = useState(null);
  const [adminLoading, setAdminLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const busNumberRef = useRef(null);
  const wakeLockRef = useRef(null);
  const lastSentRef = useRef(null);

  // Ensure scrolling works on mobile - remove any overflow restrictions from parents
  useEffect(() => {
    const rootEl = document.getElementById('root');
    const appEl = document.querySelector('.App');
    // Remove any fixed/overflow constraints that could trap scrolling
    [document.body, document.documentElement, rootEl, appEl].forEach(el => {
      if (el) {
        el.style.overflow = 'visible';
        el.style.height = 'auto';
        el.style.position = 'static';
      }
    });
    return () => {
      [document.body, document.documentElement, rootEl, appEl].forEach(el => {
        if (el) {
          el.style.overflow = '';
          el.style.height = '';
          el.style.position = '';
        }
      });
    };
  }, []);

  // Check attendance cutoff every 30s
  useEffect(() => {
    const timer = setInterval(() => setAttendanceClosed(isAttendanceClosed()), 30000);
    return () => clearInterval(timer);
  }, []);

  const requestWakeLock = async () => {
    if ('wakeLock' in navigator) {
      try {
        wakeLockRef.current = await navigator.wakeLock.request('screen');
        setWakeLockActive(true);
        wakeLockRef.current.addEventListener('release', () => setWakeLockActive(false));
      } catch (err) {
        setWakeLockActive(false);
      }
    }
  };

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && isLoggedIn && !wakeLockRef.current) {
        requestWakeLock();
        if (busNumberRef.current && navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(sendLocationUpdate, () => {}, { enableHighAccuracy: true, timeout: 10000 });
        }
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [isLoggedIn]);

  useEffect(() => {
    return () => { if (wakeLockRef.current) wakeLockRef.current.release(); };
  }, []);

  useEffect(() => {
    const savedBus = localStorage.getItem('counselor_bus');
    if (savedBus) handleAutoLogin(savedBus);
  }, []);

  const handleAutoLogin = async (savedPin) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: savedPin })
      });
      const data = await response.json();
      if (response.ok) {
        setBusData(data); setAttendance(data.attendance || {}); setIsLoggedIn(true);
        busNumberRef.current = data.bus_number;
        await requestWakeLock(); startGpsTracking();
      } else { localStorage.removeItem('counselor_bus'); }
    } catch { localStorage.removeItem('counselor_bus'); }
    finally { setLoading(false); }
  };

  const handleLogin = async (e) => {
    e.preventDefault(); setLoading(true); setError('');
    // Admin mode
    if (pin.toLowerCase() === ADMIN_PIN) {
      setIsAdmin(true); setIsLoggedIn(true); setLoading(false);
      return;
    }
    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Invalid bus number');
      localStorage.setItem('counselor_bus', pin);
      setBusData(data); setAttendance(data.attendance || {}); setIsLoggedIn(true);
      busNumberRef.current = data.bus_number;
      await requestWakeLock(); startGpsTracking();
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const sendLocationUpdate = useCallback(async (position) => {
    const busNumber = busNumberRef.current;
    if (!busNumber) return;
    const now = Date.now();
    if (lastSentRef.current && now - lastSentRef.current < 5000) return;
    lastSentRef.current = now;
    try {
      const response = await fetch(`${API_URL}/api/bus-tracking/location`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bus_number: busNumber, latitude: position.coords.latitude, longitude: position.coords.longitude,
          accuracy: position.coords.accuracy, speed: position.coords.speed, heading: position.coords.heading
        })
      });
      if (response.ok) {
        setLocationCount(prev => prev + 1);
        setGpsMessage(`Sent! ${position.coords.latitude.toFixed(4)}, ${position.coords.longitude.toFixed(4)}`);
        setGpsStatus('tracking');
      } else { setGpsMessage(`Server error: ${response.status}`); }
    } catch (err) { setGpsMessage(`Network error: ${err.message}`); }
  }, []);

  const startGpsTracking = useCallback(() => {
    setGpsStatus('requesting'); setGpsMessage('Getting GPS...');
    if (!navigator.geolocation) { setGpsStatus('error'); setGpsMessage('GPS not supported'); return; }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsStatus('tracking'); setGpsMessage(''); sendLocationUpdate(position);
        watchIdRef.current = navigator.geolocation.watchPosition(sendLocationUpdate, () => {}, { enableHighAccuracy: true, maximumAge: 10000, timeout: 30000 });
        gpsIntervalRef.current = setInterval(() => {
          navigator.geolocation.getCurrentPosition(sendLocationUpdate, () => {}, { enableHighAccuracy: true, timeout: 20000, maximumAge: 15000 });
        }, 15000);
      },
      (err) => { setGpsStatus('error'); setGpsMessage(err.code === 1 ? 'Location permission denied' : 'GPS unavailable'); },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  }, [sendLocationUpdate]);

  const stopGpsTracking = useCallback(() => {
    if (watchIdRef.current !== null) { navigator.geolocation.clearWatch(watchIdRef.current); watchIdRef.current = null; }
    if (gpsIntervalRef.current) { clearInterval(gpsIntervalRef.current); gpsIntervalRef.current = null; }
    if (wakeLockRef.current) { wakeLockRef.current.release(); wakeLockRef.current = null; }
  }, []);

  const handleLogout = () => {
    stopGpsTracking(); localStorage.removeItem('counselor_bus'); busNumberRef.current = null;
    setIsLoggedIn(false); setIsAdmin(false); setBusData(null); setAttendance({}); setPin(''); setLocationCount(0); setGpsStatus('idle'); setWakeLockActive(false);
    setSelectedDate(getTodayEST()); setAdminDates([]); setAdminBus(''); setAdminResult(null); setShowConfirm(false);
  };

  useEffect(() => () => stopGpsTracking(), [stopGpsTracking]);

  // Fetch attendance when date changes
  const fetchAttendanceForDate = useCallback(async (date) => {
    if (!busData?.bus_number) return;
    try {
      const res = await fetch(`${API_URL}/api/bus-tracking/attendance/${encodeURIComponent(busData.bus_number)}?date=${date}`);
      const data = await res.json();
      if (res.ok) {
        const attMap = {};
        (data.records || []).forEach(r => { attMap[r.camper_id] = r.status; });
        setAttendance(attMap);
      } else {
        setAttendance({});
      }
    } catch {
      setAttendance({});
    }
  }, [busData?.bus_number]);

  const handleDateChange = (newDate) => {
    setSelectedDate(newDate);
    setAttendance({});
    fetchAttendanceForDate(newDate);
  };

  const toggleAdminDate = (date) => {
    setAdminDates(prev => prev.includes(date) ? prev.filter(d => d !== date) : [...prev, date]);
  };

  const toggleAttendanceLock = () => {
    const newVal = !attendanceUnlocked;
    setAttendanceUnlocked(newVal);
    localStorage.setItem('attendance_unlocked', newVal ? 'true' : 'false');
  };

  const clearAttendance = async () => {
    if (adminDates.length === 0) return;
    setShowConfirm(false);
    setAdminLoading(true); setAdminResult(null);
    try {
      const busParam = adminBus.trim() || null;
      let endpoint = `${API_URL}/api/bus-tracking/clear-attendance`;
      if (busParam) endpoint += `?bus_number=${encodeURIComponent(busParam)}`;
      const res = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(adminDates)
      });
      const data = await res.json();
      if (res.ok) {
        setAdminResult({ success: true, message: `Cleared ${data.deleted} record(s) for ${data.bus_number}` });
        setAdminDates([]);
      } else {
        setAdminResult({ success: false, message: data.detail || 'Failed' });
      }
    } catch (err) {
      setAdminResult({ success: false, message: err.message });
    }
    setAdminLoading(false);
  };

  const markAttendance = async (camperId, status) => {
    if (!busData) return;
    setAttendance(prev => ({ ...prev, [camperId]: status }));
    try {
      await fetch(`${API_URL}/api/bus-tracking/attendance?bus_number=${encodeURIComponent(busData.bus_number)}&date=${selectedDate}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camper_id: camperId, status })
      });
    } catch { setAttendance(prev => { const n = { ...prev }; delete n[camperId]; return n; }); }
  };

  // Login screen
  if (!isLoggedIn) {
    return (
      <div data-testid="counselor-login" style={{minHeight:'100vh',background:'linear-gradient(135deg,#2563eb,#1e40af)',display:'flex',alignItems:'center',justifyContent:'center',padding:16}}>
        <div style={{background:'white',borderRadius:16,padding:32,width:'100%',maxWidth:320}}>
          <div style={{textAlign:'center',marginBottom:24}}>
            <div style={{width:80,height:80,background:'#dbeafe',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',margin:'0 auto 16px'}}><Bus size={40} color="#2563eb" /></div>
            <h1 style={{fontSize:24,fontWeight:'bold',margin:0}}>Bus Tracker</h1>
            <p style={{color:'#6b7280',margin:'4px 0 0'}}>Enter your bus number</p>
          </div>
          <form onSubmit={handleLogin}>
            <input data-testid="bus-pin-input" type="text" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="Bus # or admin" 
              style={{width:'100%',padding:16,fontSize:28,textAlign:'center',fontWeight:'bold',border:'2px solid #e5e7eb',borderRadius:12,boxSizing:'border-box'}} autoFocus />
            {error && <div data-testid="login-error" style={{marginTop:16,padding:12,background:'#fef2f2',borderRadius:8,color:'#dc2626',textAlign:'center'}}>{error}</div>}
            <button data-testid="login-submit-btn" type="submit" disabled={loading||!pin} style={{width:'100%',padding:16,marginTop:16,background:'#2563eb',color:'white',fontSize:18,fontWeight:600,border:'none',borderRadius:12,opacity:loading||!pin?0.5:1}}>{loading?'Loading...':'Go'}</button>
          </form>
          <p style={{textAlign:'center',fontSize:10,color:'#999',marginTop:16}}>{APP_VERSION}</p>
        </div>
      </div>
    );
  }

  // Admin panel
  if (isAdmin) {
    const generateDates = () => {
      const dates = [];
      const start = new Date('2026-06-29T12:00:00');
      const end = new Date('2026-08-20T12:00:00');
      const excluded = ['2026-07-03'];
      const d = new Date(start);
      while (d <= end) {
        const day = d.getDay();
        const iso = d.toISOString().split('T')[0];
        if (day >= 1 && day <= 5 && !excluded.includes(iso)) {
          dates.push(iso);
        }
        d.setDate(d.getDate() + 1);
      }
      return dates;
    };
    const campDates = generateDates();
    const today = getTodayEST();

    return (
      <div data-testid="admin-panel" className="counselor-page" style={{minHeight:'100vh',background:'#111827',paddingBottom:20}}>
        <div style={{position:'sticky',top:0,zIndex:100,background:'#dc2626',color:'white',padding:'12px',paddingTop:'max(env(safe-area-inset-top, 12px), 40px)'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <Shield size={20} />
              <h1 style={{margin:0,fontSize:18,fontWeight:'bold'}}>Admin: Clear Attendance</h1>
            </div>
            <button data-testid="admin-logout-btn" onClick={handleLogout} style={{background:'none',border:'none',color:'white',padding:8,cursor:'pointer'}}><LogOut size={20} /></button>
          </div>
        </div>

        <div style={{padding:12}}>
          {/* Attendance Lock Toggle */}
          <div data-testid="admin-lock-toggle" style={{
            marginBottom:12,padding:12,borderRadius:10,
            background:attendanceUnlocked?'#422006':'#1f2937',
            border:attendanceUnlocked?'2px solid #f59e0b':'1px solid #374151',
            display:'flex',alignItems:'center',justifyContent:'space-between'
          }}>
            <div>
              <div style={{color:'white',fontSize:14,fontWeight:600}}>
                {attendanceUnlocked ? 'Attendance Unlocked' : 'Attendance Locked (after 9:30)'}
              </div>
              <div style={{color:'#9ca3af',fontSize:11,marginTop:2}}>
                {attendanceUnlocked ? 'Counselors can mark attendance' : 'Counselors cannot mark attendance'}
              </div>
            </div>
            <button
              data-testid="admin-toggle-lock-btn"
              onClick={toggleAttendanceLock}
              style={{
                padding:'8px 16px',borderRadius:8,border:'none',fontWeight:700,fontSize:13,cursor:'pointer',
                background:attendanceUnlocked?'#dc2626':'#f59e0b',
                color:attendanceUnlocked?'white':'#000'
              }}>
              {attendanceUnlocked ? 'Re-Lock' : 'Unlock'}
            </button>
          </div>

          {/* Bus filter */}
          <div style={{marginBottom:12}}>
            <label style={{color:'#9ca3af',fontSize:12,fontWeight:600,display:'block',marginBottom:4}}>BUS (leave empty for ALL buses)</label>
            <input
              data-testid="admin-bus-input"
              type="text"
              value={adminBus}
              onChange={(e) => setAdminBus(e.target.value)}
              placeholder="e.g. Bus #14"
              style={{width:'100%',padding:10,background:'#1f2937',border:'1px solid #374151',borderRadius:8,color:'white',fontSize:14,boxSizing:'border-box'}}
            />
          </div>

          {/* Quick select */}
          <div style={{display:'flex',gap:8,marginBottom:12,flexWrap:'wrap'}}>
            <button data-testid="admin-select-today" onClick={() => setAdminDates([today])}
              style={{padding:'6px 12px',background:'#374151',border:'none',borderRadius:6,color:'white',fontSize:12,cursor:'pointer'}}>Today</button>
            <button data-testid="admin-select-all" onClick={() => setAdminDates([...campDates])}
              style={{padding:'6px 12px',background:'#374151',border:'none',borderRadius:6,color:'white',fontSize:12,cursor:'pointer'}}>All Camp Days</button>
            <button data-testid="admin-select-none" onClick={() => setAdminDates([])}
              style={{padding:'6px 12px',background:'#374151',border:'none',borderRadius:6,color:'white',fontSize:12,cursor:'pointer'}}>Clear Selection</button>
          </div>

          {/* Custom date */}
          <div style={{marginBottom:12,display:'flex',gap:8}}>
            <input
              data-testid="admin-custom-date"
              type="date"
              style={{flex:1,padding:8,background:'#1f2937',border:'1px solid #374151',borderRadius:8,color:'white',fontSize:13,colorScheme:'dark'}}
              onChange={(e) => { if (e.target.value && !adminDates.includes(e.target.value)) setAdminDates(prev => [...prev, e.target.value]); }}
            />
          </div>

          {/* Date grid */}
          <label style={{color:'#9ca3af',fontSize:12,fontWeight:600,display:'block',marginBottom:8}}>
            CAMP DAYS ({adminDates.length} selected)
          </label>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(105px, 1fr))',gap:6,marginBottom:16}}>
            {campDates.map(date => {
              const selected = adminDates.includes(date);
              const d = new Date(date + 'T12:00:00');
              const label = d.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
              return (
                <button key={date} data-testid={`admin-date-${date}`} onClick={() => toggleAdminDate(date)}
                  style={{
                    padding:'8px 4px',fontSize:11,fontWeight:selected?700:400,
                    background:selected?'#dc2626':'#1f2937',
                    color:selected?'white':'#9ca3af',
                    border:selected?'2px solid #f87171':'1px solid #374151',
                    borderRadius:8,cursor:'pointer',textAlign:'center'
                  }}>
                  {label}
                </button>
              );
            })}
          </div>

          {/* Result message */}
          {adminResult && (
            <div data-testid="admin-result" style={{
              marginBottom:12,padding:12,borderRadius:8,
              background:adminResult.success?'#052e16':'#450a0a',
              color:adminResult.success?'#4ade80':'#f87171',
              fontSize:14,fontWeight:500
            }}>
              {adminResult.message}
            </div>
          )}

          {/* Confirmation dialog */}
          {showConfirm && (
            <div data-testid="admin-confirm-dialog" style={{marginBottom:12,padding:16,background:'#450a0a',border:'2px solid #dc2626',borderRadius:12}}>
              <p style={{color:'#fca5a5',fontSize:14,fontWeight:600,margin:'0 0 8px'}}>
                Clear attendance for {adminBus.trim() || 'ALL buses'} on {adminDates.length} date(s)?
              </p>
              <p style={{color:'#9ca3af',fontSize:12,margin:'0 0 12px'}}>This cannot be undone.</p>
              <div style={{display:'flex',gap:8}}>
                <button data-testid="admin-confirm-yes" onClick={clearAttendance}
                  style={{flex:1,padding:12,background:'#dc2626',color:'white',fontWeight:700,border:'none',borderRadius:8,cursor:'pointer',fontSize:14}}>
                  Yes, Clear
                </button>
                <button data-testid="admin-confirm-no" onClick={() => setShowConfirm(false)}
                  style={{flex:1,padding:12,background:'#374151',color:'white',fontWeight:600,border:'none',borderRadius:8,cursor:'pointer',fontSize:14}}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Clear button */}
          <button
            data-testid="admin-clear-btn"
            onClick={() => setShowConfirm(true)}
            disabled={adminDates.length === 0 || adminLoading}
            style={{
              width:'100%',padding:16,background:adminDates.length === 0?'#374151':'#dc2626',
              color:'white',fontSize:16,fontWeight:700,border:'none',borderRadius:12,
              cursor:adminDates.length===0?'not-allowed':'pointer',
              opacity:adminLoading?0.5:1,
              display:'flex',alignItems:'center',justifyContent:'center',gap:8
            }}>
            <Trash2 size={20} />
            {adminLoading ? 'Clearing...' : `Clear ${adminDates.length} Date(s)`}
          </button>
        </div>
      </div>
    );
  }

  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const campers = busData?.campers || [];

  return (
    <div data-testid="counselor-main" className="counselor-page" style={{
      minHeight:'100vh',
      background:'#f3f4f6',
      paddingBottom:20
    }}>
      {/* Sticky Header */}
      <div data-testid="counselor-header" style={{
        position: 'sticky', 
        top: 0, 
        zIndex: 100, 
        background: '#2563eb', 
        color: 'white', 
        padding: '12px 12px 12px 12px',
        paddingTop: 'max(env(safe-area-inset-top, 12px), 40px)'
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <h1 data-testid="bus-number-title" style={{margin:0,fontSize:18,fontWeight:'bold'}}>{busData?.bus_number}</h1>
          <button data-testid="logout-btn" onClick={handleLogout} style={{background:'none',border:'none',color:'white',padding:8,cursor:'pointer'}}><LogOut size={20} /></button>
        </div>
        <div style={{marginTop:8,display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
          <span data-testid="gps-status" style={{display:'inline-flex',alignItems:'center',gap:4,padding:'4px 10px',borderRadius:20,fontSize:12,fontWeight:500,
            background:gpsStatus==='tracking'?'#22c55e':gpsStatus==='error'?'#ef4444':'#eab308'}}>
            <Navigation size={12} />
            {gpsStatus==='tracking'?`GPS (${locationCount})`:gpsStatus==='error'?'GPS Off':'Starting...'}
          </span>
          {wakeLockActive && <span style={{fontSize:10,background:'rgba(255,255,255,0.2)',padding:'4px 8px',borderRadius:20}}>🔒</span>}
          {gpsStatus==='error' && <button data-testid="gps-retry-btn" onClick={startGpsTracking} style={{background:'rgba(255,255,255,0.2)',border:'none',color:'white',padding:'4px 10px',borderRadius:20,fontSize:12,cursor:'pointer'}}>Retry</button>}
        </div>
        {gpsMessage && <p data-testid="gps-message" style={{margin:'4px 0 0',fontSize:11,color:'#bfdbfe'}}>{gpsMessage}</p>}
        {/* Date Selector */}
        <div data-testid="date-selector" style={{marginTop:8,display:'flex',alignItems:'center',gap:8}}>
          <Calendar size={14} />
          <input
            data-testid="date-input"
            type="date"
            value={selectedDate}
            onChange={(e) => handleDateChange(e.target.value)}
            style={{
              background:'rgba(255,255,255,0.15)',
              border:'1px solid rgba(255,255,255,0.3)',
              borderRadius:8,
              color:'white',
              padding:'4px 8px',
              fontSize:13,
              fontWeight:500,
              flex:1,
              colorScheme:'dark'
            }}
          />
          {selectedDate !== getTodayEST() && (
            <button
              data-testid="date-today-btn"
              onClick={() => handleDateChange(getTodayEST())}
              style={{background:'rgba(255,255,255,0.2)',border:'none',color:'white',padding:'4px 10px',borderRadius:8,fontSize:11,cursor:'pointer',whiteSpace:'nowrap'}}
            >
              Today
            </button>
          )}
        </div>
        {selectedDate !== getTodayEST() && (
          <div style={{marginTop:4,padding:'3px 8px',background:'#f59e0b',borderRadius:6,fontSize:11,fontWeight:600,color:'#000',textAlign:'center'}}>
            Testing: {new Date(selectedDate + 'T12:00:00').toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'})}
          </div>
        )}
      </div>

      {/* Attendance Closed Banner */}
      {attendanceClosed && !attendanceUnlocked && (
        <div data-testid="attendance-closed-banner" style={{background:'#dc2626',color:'white',padding:'8px 12px',textAlign:'center',fontSize:13,fontWeight:600}}>
          Attendance closed at 9:30 AM
        </div>
      )}
      {attendanceClosed && attendanceUnlocked && (
        <div data-testid="attendance-unlocked-banner" style={{background:'#f59e0b',color:'#000',padding:'8px 12px',textAlign:'center',fontSize:13,fontWeight:600}}>
          Attendance unlocked by admin
        </div>
      )}

      {/* Stats Bar */}
      <div data-testid="stats-bar" style={{background:'white',borderBottom:'1px solid #e5e7eb',padding:8,display:'flex',justifyContent:'space-around'}}>
        <div style={{textAlign:'center'}}><div data-testid="present-count" style={{fontSize:20,fontWeight:'bold',color:'#22c55e'}}>{presentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Present</div></div>
        <div style={{textAlign:'center'}}><div data-testid="absent-count" style={{fontSize:20,fontWeight:'bold',color:'#ef4444'}}>{absentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Absent</div></div>
        <div style={{textAlign:'center'}}><div data-testid="unmarked-count" style={{fontSize:20,fontWeight:'bold',color:'#9ca3af'}}>{campers.length-presentCount-absentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Unmarked</div></div>
        <div style={{textAlign:'center'}}><div data-testid="total-count" style={{fontSize:20,fontWeight:'bold',color:'#2563eb'}}>{campers.length}</div><div style={{fontSize:10,color:'#6b7280'}}>Total</div></div>
      </div>

      {/* Camper List */}
      <div data-testid="camper-list" style={{padding:8}}>
        {campers.map((camper, index) => {
          const status = attendance[camper.id];
          return (
            <div key={camper.id} data-testid={`camper-row-${index}`} style={{
              background:status==='present'?'#f0fdf4':status==='absent'?'#fef2f2':'white',
              border:`2px solid ${status==='present'?'#86efac':status==='absent'?'#fca5a5':'#e5e7eb'}`,
              borderRadius:10,padding:10,marginBottom:8,display:'flex',alignItems:'center',justifyContent:'space-between'
            }}>
              <div style={{flex:1,minWidth:0}}>
                <div style={{display:'flex',alignItems:'center',gap:6}}>
                  <span style={{color:'#9ca3af',fontSize:12,width:24}}>#{index+1}</span>
                  <span data-testid={`camper-name-${index}`} style={{fontWeight:500,fontSize:14,color:'#1f2937',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{camper.first_name} {camper.last_name}</span>
                </div>
              </div>
              <div style={{display:'flex',gap:6,flexShrink:0}}>
                {(() => { const locked = attendanceClosed && !attendanceUnlocked; return (<>
                <button data-testid={`mark-present-${index}`} onClick={()=>!locked && markAttendance(camper.id,'present')} disabled={locked} style={{width:44,height:44,borderRadius:10,border:'none',display:'flex',alignItems:'center',justifyContent:'center',cursor:locked?'not-allowed':'pointer',
                  background:status==='present'?'#22c55e':'#f3f4f6',color:status==='present'?'white':'#9ca3af',opacity:locked?0.4:1}}>
                  <CheckCircle size={24} />
                </button>
                <button data-testid={`mark-absent-${index}`} onClick={()=>!locked && markAttendance(camper.id,'absent')} disabled={locked} style={{width:44,height:44,borderRadius:10,border:'none',display:'flex',alignItems:'center',justifyContent:'center',cursor:locked?'not-allowed':'pointer',
                  background:status==='absent'?'#ef4444':'#f3f4f6',color:status==='absent'?'white':'#9ca3af',opacity:locked?0.4:1}}>
                  <XCircle size={24} />
                </button>
                </>); })()}
              </div>
            </div>
          );
        })}
        {campers.length===0 && (
          <div style={{textAlign:'center',padding:48,color:'#6b7280'}}>
            <Users size={48} style={{opacity:0.5,marginBottom:12}} />
            <p>No campers on this bus</p>
          </div>
        )}
        <p style={{textAlign:'center',fontSize:10,color:'#999',padding:16}}>{APP_VERSION}</p>
      </div>
    </div>
  );
}

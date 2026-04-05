import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, Bus, Users, LogOut, Navigation } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const APP_VERSION = "v2.5";

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
  const [wakeLockActive, setWakeLockActive] = useState(false);
  
  const gpsIntervalRef = useRef(null);
  const watchIdRef = useRef(null);
  const busNumberRef = useRef(null);
  const wakeLockRef = useRef(null);
  const lastSentRef = useRef(null);

  // Enable scrolling when component mounts - critical for mobile devices
  useEffect(() => {
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    document.body.style.position = 'static';
    document.body.style.WebkitOverflowScrolling = 'touch';
    document.documentElement.style.overflow = 'auto';
    document.documentElement.style.height = 'auto';
    const appDiv = document.querySelector('.App');
    if (appDiv) {
      appDiv.style.overflow = 'auto';
      appDiv.style.height = 'auto';
      appDiv.style.position = 'static';
    }
    
    return () => {
      document.body.style.overflow = '';
      document.body.style.height = '';
      document.body.style.position = '';
      document.body.style.WebkitOverflowScrolling = '';
      document.documentElement.style.overflow = '';
      document.documentElement.style.height = '';
      if (appDiv) {
        appDiv.style.overflow = '';
        appDiv.style.height = '';
        appDiv.style.position = '';
      }
    };
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
    setIsLoggedIn(false); setBusData(null); setAttendance({}); setPin(''); setLocationCount(0); setGpsStatus('idle'); setWakeLockActive(false);
  };

  useEffect(() => () => stopGpsTracking(), [stopGpsTracking]);

  const markAttendance = async (camperId, status) => {
    if (!busData) return;
    setAttendance(prev => ({ ...prev, [camperId]: status }));
    try {
      await fetch(`${API_URL}/api/bus-tracking/attendance?bus_number=${encodeURIComponent(busData.bus_number)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camper_id: camperId, status })
      });
    } catch { setAttendance(prev => { const n = { ...prev }; delete n[camperId]; return n; }); }
  };

  // Login screen
  if (!isLoggedIn) {
    return (
      <div style={{minHeight:'100vh',background:'linear-gradient(135deg,#2563eb,#1e40af)',display:'flex',alignItems:'center',justifyContent:'center',padding:16}}>
        <div style={{background:'white',borderRadius:16,padding:32,width:'100%',maxWidth:320}}>
          <div style={{textAlign:'center',marginBottom:24}}>
            <div style={{width:80,height:80,background:'#dbeafe',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',margin:'0 auto 16px'}}><Bus size={40} color="#2563eb" /></div>
            <h1 style={{fontSize:24,fontWeight:'bold',margin:0}}>Bus Tracker</h1>
            <p style={{color:'#6b7280',margin:'4px 0 0'}}>Enter your bus number</p>
          </div>
          <form onSubmit={handleLogin}>
            <input type="text" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="Bus #" 
              style={{width:'100%',padding:16,fontSize:28,textAlign:'center',fontWeight:'bold',border:'2px solid #e5e7eb',borderRadius:12,boxSizing:'border-box'}} autoFocus />
            {error && <div style={{marginTop:16,padding:12,background:'#fef2f2',borderRadius:8,color:'#dc2626',textAlign:'center'}}>{error}</div>}
            <button type="submit" disabled={loading||!pin} style={{width:'100%',padding:16,marginTop:16,background:'#2563eb',color:'white',fontSize:18,fontWeight:600,border:'none',borderRadius:12,opacity:loading||!pin?0.5:1}}>{loading?'Loading...':'Go'}</button>
          </form>
          <p style={{textAlign:'center',fontSize:10,color:'#999',marginTop:16}}>{APP_VERSION}</p>
        </div>
      </div>
    );
  }

  const presentCount = Object.values(attendance).filter(s => s === 'present').length;
  const absentCount = Object.values(attendance).filter(s => s === 'absent').length;
  const campers = busData?.campers || [];

  return (
    <div style={{minHeight:'100vh',background:'#f3f4f6',paddingBottom:20,WebkitOverflowScrolling:'touch',overscrollBehavior:'contain'}}>
      {/* Sticky Header */}
      <div style={{
        position: 'sticky', 
        top: 0, 
        zIndex: 100, 
        background: '#2563eb', 
        color: 'white', 
        padding: '12px 12px 12px 12px',
        paddingTop: 'max(env(safe-area-inset-top, 12px), 40px)'
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <h1 style={{margin:0,fontSize:18,fontWeight:'bold'}}>{busData?.bus_number}</h1>
          <button onClick={handleLogout} style={{background:'none',border:'none',color:'white',padding:8,cursor:'pointer'}}><LogOut size={20} /></button>
        </div>
        <div style={{marginTop:8,display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
          <span style={{display:'inline-flex',alignItems:'center',gap:4,padding:'4px 10px',borderRadius:20,fontSize:12,fontWeight:500,
            background:gpsStatus==='tracking'?'#22c55e':gpsStatus==='error'?'#ef4444':'#eab308'}}>
            <Navigation size={12} />
            {gpsStatus==='tracking'?`GPS (${locationCount})`:gpsStatus==='error'?'GPS Off':'Starting...'}
          </span>
          {wakeLockActive && <span style={{fontSize:10,background:'rgba(255,255,255,0.2)',padding:'4px 8px',borderRadius:20}}>🔒</span>}
          {gpsStatus==='error' && <button onClick={startGpsTracking} style={{background:'rgba(255,255,255,0.2)',border:'none',color:'white',padding:'4px 10px',borderRadius:20,fontSize:12,cursor:'pointer'}}>Retry</button>}
        </div>
        {gpsMessage && <p style={{margin:'4px 0 0',fontSize:11,color:'#bfdbfe'}}>{gpsMessage}</p>}
      </div>

      {/* Stats Bar */}
      <div style={{background:'white',borderBottom:'1px solid #e5e7eb',padding:8,display:'flex',justifyContent:'space-around'}}>
        <div style={{textAlign:'center'}}><div style={{fontSize:20,fontWeight:'bold',color:'#22c55e'}}>{presentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Present</div></div>
        <div style={{textAlign:'center'}}><div style={{fontSize:20,fontWeight:'bold',color:'#ef4444'}}>{absentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Absent</div></div>
        <div style={{textAlign:'center'}}><div style={{fontSize:20,fontWeight:'bold',color:'#9ca3af'}}>{campers.length-presentCount-absentCount}</div><div style={{fontSize:10,color:'#6b7280'}}>Unmarked</div></div>
        <div style={{textAlign:'center'}}><div style={{fontSize:20,fontWeight:'bold',color:'#2563eb'}}>{campers.length}</div><div style={{fontSize:10,color:'#6b7280'}}>Total</div></div>
      </div>

      {/* Camper List */}
      <div style={{padding:8}}>
        {campers.map((camper, index) => {
          const status = attendance[camper.id];
          return (
            <div key={camper.id} style={{
              background:status==='present'?'#f0fdf4':status==='absent'?'#fef2f2':'white',
              border:`2px solid ${status==='present'?'#86efac':status==='absent'?'#fca5a5':'#e5e7eb'}`,
              borderRadius:10,padding:10,marginBottom:8,display:'flex',alignItems:'center',justifyContent:'space-between'
            }}>
              <div style={{flex:1,minWidth:0}}>
                <div style={{display:'flex',alignItems:'center',gap:6}}>
                  <span style={{color:'#9ca3af',fontSize:12,width:24}}>#{index+1}</span>
                  <span style={{fontWeight:500,fontSize:14,color:'#1f2937',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{camper.first_name} {camper.last_name}</span>
                </div>
              </div>
              <div style={{display:'flex',gap:6,flexShrink:0}}>
                <button onClick={()=>markAttendance(camper.id,'present')} style={{width:44,height:44,borderRadius:10,border:'none',display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',
                  background:status==='present'?'#22c55e':'#f3f4f6',color:status==='present'?'white':'#9ca3af'}}>
                  <CheckCircle size={24} />
                </button>
                <button onClick={()=>markAttendance(camper.id,'absent')} style={{width:44,height:44,borderRadius:10,border:'none',display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',
                  background:status==='absent'?'#ef4444':'#f3f4f6',color:status==='absent'?'white':'#9ca3af'}}>
                  <XCircle size={24} />
                </button>
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

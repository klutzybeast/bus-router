import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MapPin, Clock, ArrowLeft, Bus, Navigation } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

function getTodayEST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
}

export default function AdminRouteHistory() {
  const [selectedDate, setSelectedDate] = useState(getTodayEST());
  const [buses, setBuses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedBus, setSelectedBus] = useState(null);
  const [routeData, setRouteData] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const polylineRef = useRef(null);

  const fetchDailySummary = useCallback(async (date) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/bus-tracking/daily-summary?date=${date}`);
      const data = await res.json();
      if (res.ok) setBuses(data.buses || []);
      else setBuses([]);
    } catch { setBuses([]); }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDailySummary(selectedDate);
  }, [selectedDate, fetchDailySummary]);

  const handleBusClick = async (busNumber) => {
    setSelectedBus(busNumber);
    setRouteLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/bus-tracking/route/${encodeURIComponent(busNumber)}?date=${selectedDate}`);
      const data = await res.json();
      if (res.ok) setRouteData(data);
      else setRouteData(null);
    } catch { setRouteData(null); }
    setRouteLoading(false);
  };

  // Load Google Maps script
  useEffect(() => {
    if (!MAPS_KEY) return;
    if (window.google && window.google.maps) return;
    const existing = document.querySelector('script[src*="maps.googleapis.com"]');
    if (existing) return;
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_KEY}`;
    script.async = true;
    document.head.appendChild(script);
  }, []);

  // Render map when route data loads
  useEffect(() => {
    if (!routeData || !routeData.route || routeData.route.length === 0) return;
    if (!window.google || !window.google.maps) return;
    if (!mapRef.current) return;

    const google = window.google;
    const points = routeData.route;
    const center = { lat: points[0].latitude, lng: points[0].longitude };

    // Clear old markers/polyline
    markersRef.current.forEach(m => m.setMap(null));
    markersRef.current = [];
    if (polylineRef.current) polylineRef.current.setMap(null);

    // Create or reuse map
    if (!mapInstanceRef.current) {
      mapInstanceRef.current = new google.maps.Map(mapRef.current, {
        center, zoom: 13, mapTypeControl: false, streetViewControl: false,
        fullscreenControl: false, zoomControl: true,
        styles: [{ featureType: 'poi', stylers: [{ visibility: 'off' }] }]
      });
    } else {
      mapInstanceRef.current.setCenter(center);
    }
    const map = mapInstanceRef.current;

    // Draw route polyline
    const path = points.map(p => ({ lat: p.latitude, lng: p.longitude }));
    polylineRef.current = new google.maps.Polyline({
      path, geodesic: true, strokeColor: '#2563eb', strokeOpacity: 0.8, strokeWeight: 4, map
    });

    // Add stop markers
    const stops = routeData.stops || [];
    stops.forEach((stop, i) => {
      const marker = new google.maps.Marker({
        position: { lat: stop.latitude, lng: stop.longitude },
        map,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#dc2626',
          fillOpacity: 1,
          strokeColor: '#fff',
          strokeWeight: 2
        },
        title: `Stop ${i + 1}: ${stop.duration_formatted || ''}`
      });
      const infoWindow = new google.maps.InfoWindow({
        content: `<div style="font-size:12px;font-weight:600">Stop ${i+1}</div><div style="font-size:11px">${stop.duration_formatted || 'Unknown'}</div>`
      });
      marker.addListener('click', () => infoWindow.open(map, marker));
      markersRef.current.push(marker);
    });

    // Add start/end markers
    if (points.length > 1) {
      const startMarker = new google.maps.Marker({
        position: { lat: points[0].latitude, lng: points[0].longitude },
        map,
        icon: { path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: '#22c55e', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 },
        title: 'Start'
      });
      const endMarker = new google.maps.Marker({
        position: { lat: points[points.length-1].latitude, lng: points[points.length-1].longitude },
        map,
        icon: { path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: '#f59e0b', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 },
        title: 'End'
      });
      markersRef.current.push(startMarker, endMarker);
    }

    // Fit bounds
    const bounds = new google.maps.LatLngBounds();
    path.forEach(p => bounds.extend(p));
    map.fitBounds(bounds);

  }, [routeData]);

  // Bus detail view
  if (selectedBus && routeData) {
    const formatTime = (isoStr) => {
      if (!isoStr) return '';
      const d = new Date(isoStr);
      return d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit', hour12: true });
    };

    return (
      <div data-testid="route-detail-view">
        <button data-testid="route-back-btn" onClick={() => { setSelectedBus(null); setRouteData(null); mapInstanceRef.current = null; }}
          style={{ display:'flex',alignItems:'center',gap:6,background:'none',border:'none',color:'#9ca3af',fontSize:13,padding:'8px 0',cursor:'pointer',marginBottom:8 }}>
          <ArrowLeft size={16} /> Back to all buses
        </button>

        <div style={{ background:'#1f2937',borderRadius:10,padding:12,marginBottom:12 }}>
          <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
            <Bus size={18} color="#3b82f6" />
            <h3 style={{ margin:0,color:'white',fontSize:16,fontWeight:700 }}>{selectedBus}</h3>
          </div>
          <div style={{ color:'#9ca3af',fontSize:12 }}>
            {routeData.point_count} GPS points &middot; {routeData.stop_count} stops &middot; {new Date(selectedDate + 'T12:00:00').toLocaleDateString('en-US', { weekday:'short', month:'short', day:'numeric' })}
          </div>
        </div>

        {/* Map */}
        <div data-testid="route-map" ref={mapRef} style={{ width:'100%',height:280,borderRadius:10,overflow:'hidden',marginBottom:12,background:'#374151' }}>
          {!MAPS_KEY && <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'#9ca3af',fontSize:13}}>Google Maps API key required</div>}
        </div>

        {/* Legend */}
        <div style={{ display:'flex',gap:12,marginBottom:12,fontSize:11,color:'#9ca3af' }}>
          <span style={{display:'flex',alignItems:'center',gap:4}}><span style={{width:10,height:10,borderRadius:'50%',background:'#22c55e',display:'inline-block'}}></span> Start</span>
          <span style={{display:'flex',alignItems:'center',gap:4}}><span style={{width:10,height:10,borderRadius:'50%',background:'#f59e0b',display:'inline-block'}}></span> End</span>
          <span style={{display:'flex',alignItems:'center',gap:4}}><span style={{width:10,height:10,borderRadius:'50%',background:'#dc2626',display:'inline-block'}}></span> Stop</span>
          <span style={{display:'flex',alignItems:'center',gap:4}}><span style={{width:3,height:10,background:'#2563eb',display:'inline-block'}}></span> Route</span>
        </div>

        {/* Stops list */}
        <h4 style={{ color:'#9ca3af',fontSize:12,fontWeight:600,marginBottom:8 }}>STOPS ({routeData.stops?.length || 0})</h4>
        {routeData.stops && routeData.stops.length > 0 ? (
          routeData.stops.map((stop, i) => (
            <div key={i} data-testid={`stop-row-${i}`} style={{
              background:'#1f2937',borderRadius:8,padding:10,marginBottom:6,
              display:'flex',alignItems:'center',gap:10
            }}>
              <div style={{width:28,height:28,borderRadius:'50%',background:'#dc2626',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
                <span style={{color:'white',fontSize:11,fontWeight:700}}>{i+1}</span>
              </div>
              <div style={{flex:1,minWidth:0}}>
                <div style={{color:'white',fontSize:13,fontWeight:500}}>
                  {stop.latitude?.toFixed(5)}, {stop.longitude?.toFixed(5)}
                </div>
                <div style={{color:'#9ca3af',fontSize:11,marginTop:2}}>
                  {formatTime(stop.stop_started_at)}
                </div>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:4,color:'#f59e0b',fontSize:13,fontWeight:600,flexShrink:0}}>
                <Clock size={14} />
                {stop.duration_formatted || '—'}
              </div>
            </div>
          ))
        ) : (
          <div style={{color:'#6b7280',fontSize:13,textAlign:'center',padding:20}}>No stops recorded (bus may not have stopped for 30+ seconds)</div>
        )}
      </div>
    );
  }

  // Loading route
  if (selectedBus && routeLoading) {
    return (
      <div style={{textAlign:'center',padding:40,color:'#9ca3af'}}>
        <Navigation size={32} style={{opacity:0.5,marginBottom:8}} />
        <p>Loading route for {selectedBus}...</p>
      </div>
    );
  }

  // Main view - date picker + bus cards
  return (
    <div data-testid="route-history-section">
      {/* Date picker */}
      <div style={{ marginBottom:12 }}>
        <label style={{color:'#9ca3af',fontSize:12,fontWeight:600,display:'block',marginBottom:4}}>SELECT DATE</label>
        <input
          data-testid="route-date-input"
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          style={{width:'100%',padding:10,background:'#1f2937',border:'1px solid #374151',borderRadius:8,color:'white',fontSize:14,boxSizing:'border-box',colorScheme:'dark'}}
        />
      </div>

      {/* Bus cards */}
      {loading ? (
        <div style={{textAlign:'center',padding:30,color:'#9ca3af'}}>Loading...</div>
      ) : buses.length === 0 ? (
        <div style={{textAlign:'center',padding:40,color:'#6b7280'}}>
          <Bus size={40} style={{opacity:0.4,marginBottom:8}} />
          <p style={{margin:0}}>No buses tracked on this date</p>
        </div>
      ) : (
        <div>
          <div style={{color:'#9ca3af',fontSize:12,fontWeight:600,marginBottom:8}}>
            {buses.length} BUS{buses.length > 1 ? 'ES' : ''} TRACKED
          </div>
          {buses.map(bus => {
            const formatTime = (isoStr) => {
              if (!isoStr) return '';
              const d = new Date(isoStr);
              return d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit', hour12: true });
            };
            return (
              <button key={bus.bus_number} data-testid={`route-bus-card-${bus.bus_number}`}
                onClick={() => handleBusClick(bus.bus_number)}
                style={{
                  width:'100%',background:'#1f2937',border:'1px solid #374151',borderRadius:10,
                  padding:12,marginBottom:8,cursor:'pointer',textAlign:'left',display:'flex',alignItems:'center',gap:12
                }}>
                <div style={{width:40,height:40,borderRadius:10,background:'#2563eb',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
                  <Bus size={20} color="white" />
                </div>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{color:'white',fontSize:14,fontWeight:600}}>{bus.bus_number}</div>
                  <div style={{color:'#9ca3af',fontSize:11,marginTop:2}}>
                    {bus.point_count} points &middot; {bus.stop_count} stops &middot; {formatTime(bus.first_point)} - {formatTime(bus.last_point)}
                  </div>
                </div>
                <Navigation size={16} color="#6b7280" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

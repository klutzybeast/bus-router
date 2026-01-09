import React, { useState, useEffect, useCallback } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

const BusRoutingMap = () => {
  const [campers, setCampers] = useState([]);
  const [selectedCamper, setSelectedCamper] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mapCenter, setMapCenter] = useState({ lat: 40.7128, lng: -73.7949 });
  const [uniqueBuses, setUniqueBuses] = useState([]);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [selectedBusFilter, setSelectedBusFilter] = useState(null);

  const fetchCampers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/campers`);
      setCampers(response.data);
      
      const buses = [...new Set(response.data.map(c => c.bus_number))].sort();
      setUniqueBuses(buses);
      
      if (response.data.length > 0) {
        setMapCenter({
          lat: response.data[0].location.latitude,
          lng: response.data[0].location.longitude
        });
      }
      
      toast.success(`Loaded ${response.data.length} camper locations`);
    } catch (error) {
      console.error("Error fetching campers:", error);
      toast.error("Failed to load camper data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampers();
    
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(6, 0, 0, 0);
    
    const timeUntilMorning = tomorrow.getTime() - now.getTime();
    
    const timeout = setTimeout(() => {
      fetchCampers();
      
      const interval = setInterval(() => {
        fetchCampers();
      }, 24 * 60 * 60 * 1000);
      
      return () => clearInterval(interval);
    }, timeUntilMorning);
    
    return () => clearTimeout(timeout);
  }, [fetchCampers]);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    try {
      const text = await file.text();
      
      toast.loading("Processing CSV and geocoding addresses...");
      
      const response = await axios.post(`${API}/sync-campers`, {
        csv_content: text
      });
      
      toast.dismiss();
      toast.success(`Successfully synced ${response.data.count} camper locations`);
      
      await fetchCampers();
    } catch (error) {
      toast.dismiss();
      console.error("Error uploading file:", error);
      toast.error("Failed to process CSV file");
    }
  };

  const handleMarkerClick = useCallback((camper) => {
    setSelectedCamper(camper);
    if (window.innerWidth < 768) {
      setIsPanelOpen(false);
    }
  }, []);

  const handleBusFilter = (busNumber) => {
    if (selectedBusFilter === busNumber) {
      setSelectedBusFilter(null);
    } else {
      setSelectedBusFilter(busNumber);
      const busStop = campers.find(c => c.bus_number === busNumber);
      if (busStop) {
        setMapCenter({
          lat: busStop.location.latitude,
          lng: busStop.location.longitude
        });
      }
    }
  };

  const filteredCampers = selectedBusFilter 
    ? campers.filter(c => c.bus_number === selectedBusFilter)
    : campers;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-600" />
          <div className="text-lg text-gray-700">Loading bus routes...</div>
        </div>
      </div>
    );
  }

  return (
    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
      <div className="relative w-full h-screen overflow-hidden">
        {/* Mobile Menu Button */}
        <Button
          className="md:hidden fixed top-4 left-4 z-50 bg-blue-600 hover:bg-blue-700 shadow-lg h-12 w-12 rounded-full p-0"
          onClick={() => setIsPanelOpen(!isPanelOpen)}
          data-testid="mobile-menu-btn"
        >
          {isPanelOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </Button>

        <Map
          style={{ width: "100%", height: "100%" }}
          center={mapCenter}
          defaultZoom={11}
          mapId="bus-routing-map"
          gestureHandling="greedy"
        >
          {filteredCampers.map((camper, index) => (
            <AdvancedMarker
              key={`${camper.first_name}-${camper.last_name}-${index}`}
              position={{
                lat: camper.location.latitude,
                lng: camper.location.longitude
              }}
              onClick={() => handleMarkerClick(camper)}
            >
              <div 
                className="w-10 h-10 md:w-8 md:h-8 rounded-full flex items-center justify-center text-white font-bold text-xs shadow-lg border-2 border-white cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                style={{ backgroundColor: camper.bus_color }}
                data-testid={`bus-marker-${camper.bus_number}`}
              >
                {camper.bus_number.replace('Bus #', '').substring(0, 2)}
              </div>
            </AdvancedMarker>
          ))}

          {selectedCamper && (
            <InfoWindow
              position={{
                lat: selectedCamper.location.latitude,
                lng: selectedCamper.location.longitude
              }}
              onCloseClick={() => setSelectedCamper(null)}
            >
              <div className="p-2" data-testid="camper-info-window">
                <h3 className="font-bold text-base mb-2">
                  {selectedCamper.first_name} {selectedCamper.last_name}
                </h3>
                <div className="space-y-1 text-sm">
                  <div>
                    <span className="font-semibold">Bus:</span> {selectedCamper.bus_number}
                  </div>
                  <div>
                    <span className="font-semibold">Session:</span> {selectedCamper.session}
                  </div>
                  <div>
                    <span className="font-semibold">Type:</span> {selectedCamper.pickup_type}
                  </div>
                  <div>
                    <span className="font-semibold">Address:</span> {selectedCamper.location.address}
                  </div>
                  {selectedCamper.town && (
                    <div>
                      <span className="font-semibold">Town:</span> {selectedCamper.town}
                    </div>
                  )}
                  {selectedCamper.zip_code && (
                    <div>
                      <span className="font-semibold">Zip:</span> {selectedCamper.zip_code}
                    </div>
                  )}
                </div>
              </div>
            </InfoWindow>
          )}
        </Map>

        <Card className="absolute top-4 left-4 w-80 shadow-xl border-0" data-testid="control-panel">
          <div className="p-4 bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-t-lg">
            <h2 className="text-xl font-bold">Camp Bus Routing</h2>
            <p className="text-sm text-blue-100 mt-1">33 Bus Routes</p>
          </div>
          
          <div className="p-4 space-y-4">
            <div className="space-y-2">
              <label htmlFor="csv-upload" className="block">
                <Button
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  onClick={() => document.getElementById('csv-upload').click()}
                  data-testid="upload-csv-btn"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Upload CSV Data
                </Button>
              </label>
              <input
                id="csv-upload"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileUpload}
              />
              
              <Button
                variant="outline"
                className="w-full"
                onClick={fetchCampers}
                data-testid="refresh-btn"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh Data
              </Button>
            </div>
            
            <div className="border-t pt-4">
              <h3 className="font-semibold mb-2 text-sm text-gray-700">Active Buses ({uniqueBuses.length})</h3>
              <div className="max-h-96 overflow-y-auto space-y-1">
                {uniqueBuses.map((bus) => {
                  const busColor = campers.find(c => c.bus_number === bus)?.bus_color || '#000000';
                  const busCount = campers.filter(c => c.bus_number === bus).length;
                  return (
                    <div
                      key={bus}
                      className="flex items-center justify-between p-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
                      data-testid={`bus-list-item-${bus}`}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-4 h-4 rounded-full border-2 border-white shadow"
                          style={{ backgroundColor: busColor }}
                        />
                        <span className="font-medium text-sm">{bus}</span>
                      </div>
                      <span className="text-xs text-gray-600">{busCount} stops</span>
                    </div>
                  );
                })}
              </div>
            </div>
            
            <div className="border-t pt-4 text-center text-sm text-gray-600">
              <p>Total Campers: <span className="font-bold text-gray-800">{campers.length}</span></p>
              <p className="text-xs text-gray-500 mt-1">Auto-refreshes daily at 6:00 AM</p>
            </div>
          </div>
        </Card>
      </div>
    </APIProvider>
  );
};

export default BusRoutingMap;
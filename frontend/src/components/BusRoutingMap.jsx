import React, { useState, useEffect, useCallback } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin, Printer, Filter } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
  const [sessionFilter, setSessionFilter] = useState("all");
  const [mapInstance, setMapInstance] = useState(null);

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
      if (busStop && mapInstance) {
        mapInstance.panTo({
          lat: busStop.location.latitude,
          lng: busStop.location.longitude
        });
        mapInstance.setZoom(13);
      }
    }
  };

  const filteredCampers = selectedBusFilter 
    ? campers.filter(c => c.bus_number === selectedBusFilter)
    : campers;

  const sessionFilteredCampers = sessionFilter === "all" 
    ? filteredCampers
    : filteredCampers.filter(c => {
        const session = c.session.toLowerCase();
        if (sessionFilter === "full") return session.includes("full season");
        if (sessionFilter === "half1") return session.includes("half season 1") || session.includes("half 1");
        if (sessionFilter === "half2") return session.includes("half season 2") || session.includes("half 2");
        if (sessionFilter === "flex") return session.includes("flex");
        return true;
      });

  const handlePrintRoute = (busNumber) => {
    window.open(`${API}/route-sheet/${busNumber}/print`, '_blank');
  };

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
          style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0 }}
          defaultCenter={mapCenter}
          defaultZoom={11}
          mapId="bus-routing-map"
          gestureHandling="greedy"
          disableDefaultUI={false}
          clickableIcons={true}
          onLoad={(map) => setMapInstance(map)}
        >
          {sessionFilteredCampers.map((camper, index) => (
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
              <div className="p-2 max-w-xs" data-testid="camper-info-window">
                <h3 className="font-bold text-base md:text-lg mb-2">
                  {selectedCamper.first_name} {selectedCamper.last_name}
                </h3>
                <div className="space-y-1 text-xs md:text-sm">
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="font-semibold">Bus:</span> 
                    <span 
                      className="px-2 py-0.5 rounded text-white text-xs font-medium"
                      style={{ backgroundColor: selectedCamper.bus_color }}
                    >
                      {selectedCamper.bus_number}
                    </span>
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

        {/* Control Panel - Responsive */}
        <Card 
          className={`
            fixed md:absolute 
            top-0 md:top-4 
            left-0 md:left-4 
            w-full md:w-96 
            h-full md:h-auto md:max-h-[calc(100vh-2rem)]
            shadow-2xl md:shadow-xl 
            border-0 md:border
            transition-transform duration-300 ease-in-out
            z-40 md:z-10
            ${isPanelOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          `}
          style={{ pointerEvents: 'auto' }}
          data-testid="control-panel"
        >
          <div className="h-full md:h-auto flex flex-col">
            {/* Header */}
            <div className="p-4 md:p-4 bg-gradient-to-br from-blue-600 to-blue-700 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl md:text-2xl font-bold">Camp Bus Routing</h2>
                  <p className="text-sm text-blue-100 mt-1">33 Bus Routes</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="md:hidden text-white hover:bg-blue-700"
                  onClick={() => setIsPanelOpen(false)}
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>
            
            {/* Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Action Buttons */}
              <div className="space-y-2">
                <label htmlFor="csv-upload" className="block">
                  <Button
                    className="w-full bg-blue-600 hover:bg-blue-700 h-12 text-base"
                    onClick={() => document.getElementById('csv-upload').click()}
                    data-testid="upload-csv-btn"
                  >
                    <Upload className="w-5 h-5 mr-2" />
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
                  className="w-full h-12 text-base"
                  onClick={fetchCampers}
                  data-testid="refresh-btn"
                >
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Refresh Data
                </Button>

                {selectedBusFilter && (
                  <Button
                    variant="outline"
                    className="w-full h-12 text-base border-blue-600 text-blue-600 hover:bg-blue-50"
                    onClick={() => setSelectedBusFilter(null)}
                  >
                    <MapPin className="w-5 h-5 mr-2" />
                    Show All Buses
                  </Button>
                )}
              </div>
              
              {/* Filters */}
              <div className="border-t pt-4 space-y-3">
                <h3 className="font-semibold text-sm text-gray-700 flex items-center gap-2">
                  <Filter className="w-4 h-4" />
                  Filters
                </h3>
                
                <div>
                  <label className="text-xs text-gray-600 mb-1 block">Session Type</label>
                  <Select value={sessionFilter} onValueChange={setSessionFilter}>
                    <SelectTrigger className="w-full" data-testid="session-filter">
                      <SelectValue placeholder="All Sessions" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Sessions</SelectItem>
                      <SelectItem value="full">Full Season</SelectItem>
                      <SelectItem value="half1">Half Season 1</SelectItem>
                      <SelectItem value="half2">Half Season 2</SelectItem>
                      <SelectItem value="flex">Flex Days</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              {/* Bus List */}
              <div className="border-t pt-4">
                <h3 className="font-semibold mb-3 text-sm text-gray-700 flex items-center justify-between">
                  <span>Active Buses ({uniqueBuses.length})</span>
                  {selectedBusFilter && (
                    <span className="text-xs text-blue-600">Filtered</span>
                  )}
                </h3>
                <div className="space-y-2 max-h-96 md:max-h-[40vh] overflow-y-auto">
                  {uniqueBuses.map((bus) => {
                    const busColor = campers.find(c => c.bus_number === bus)?.bus_color || '#000000';
                    const busCount = campers.filter(c => c.bus_number === bus).length;
                    const isSelected = selectedBusFilter === bus;
                    
                    return (
                      <button
                        key={bus}
                        onClick={() => handleBusFilter(bus)}
                        className={`
                          w-full flex items-center justify-between p-3 rounded-lg
                          transition-all duration-200 active:scale-98
                          ${isSelected 
                            ? 'bg-blue-100 border-2 border-blue-600 shadow-md' 
                            : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                          }
                        `}
                        data-testid={`bus-list-item-${bus}`}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className="w-6 h-6 md:w-5 md:h-5 rounded-full border-2 border-white shadow flex-shrink-0"
                            style={{ backgroundColor: busColor }}
                          />
                          <div className="text-left">
                            <div className={`font-medium text-sm md:text-base ${isSelected ? 'text-blue-700 font-bold' : ''}`}>
                              {bus}
                            </div>
                            <div className="text-xs text-gray-500">{busCount} stops</div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePrintRoute(bus);
                          }}
                          title="Print Route Sheet"
                        >
                          <Printer className="w-4 h-4" />
                        </Button>
                      </button>
                    );
                  })}
                </div>
              </div>
              
              {/* Stats Footer */}
              <div className="border-t pt-4 text-center space-y-2">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <p className="text-gray-600 text-xs mb-1">Total Campers</p>
                    <p className="font-bold text-blue-700 text-xl">{campers.length}</p>
                  </div>
                  <div className="bg-green-50 p-3 rounded-lg">
                    <p className="text-gray-600 text-xs mb-1">Active Buses</p>
                    <p className="font-bold text-green-700 text-xl">{uniqueBuses.length}</p>
                  </div>
                </div>
                <p className="text-xs text-gray-500">Auto-refreshes daily at 6:00 AM</p>
              </div>
            </div>
          </div>
        </Card>

        {/* Overlay for mobile when panel is open */}
        {isPanelOpen && (
          <div 
            className="md:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
            onClick={() => setIsPanelOpen(false)}
          />
        )}
      </div>
    </APIProvider>
  );
};

export default BusRoutingMap;
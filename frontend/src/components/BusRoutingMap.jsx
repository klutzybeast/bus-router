import React, { useState, useEffect, useCallback } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin, Printer, Filter, Download, Search, UserPlus } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

const BUS_COLORS = {
  'Bus #01': '#e6194b', 'Bus #02': '#3cb44b', 'Bus #03': '#ffe119', 'Bus #04': '#4363d8',
  'Bus #05': '#f58231', 'Bus #06': '#911eb4', 'Bus #07': '#46f0f0', 'Bus #08': '#f032e6',
  'Bus #09': '#bcf60c', 'Bus #10': '#fabebe', 'Bus #11': '#008080', 'Bus #12': '#e6beff',
  'Bus #13': '#9a6324', 'Bus #14': '#000000', 'Bus #15': '#800000', 'Bus #16': '#aaffc3',
  'Bus #17': '#808000', 'Bus #18': '#ffd8b1', 'Bus #19': '#000075', 'Bus #20': '#808080',
  'Bus #21': '#FFB6C1', 'Bus #22': '#FF69B4', 'Bus #23': '#FF1493', 'Bus #24': '#FFD700',
  'Bus #25': '#FFA500', 'Bus #26': '#FF4500', 'Bus #27': '#DC143C', 'Bus #28': '#8B0000',
  'Bus #29': '#006400', 'Bus #30': '#228B22', 'Bus #31': '#20B2AA', 'Bus #32': '#00CED1',
  'Bus #33': '#191970', 'Bus #34': '#e6194b'
};

const getBusColor = (busNumber) => BUS_COLORS[busNumber] || '#000000';

const BusRoutingMap = () => {
  const [campers, setCampers] = useState([]);
  const [selectedCamper, setSelectedCamper] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mapCenter, setMapCenter] = useState({ lat: 40.7128, lng: -73.7949 });
  const [uniqueBuses, setUniqueBuses] = useState([]);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [selectedBusFilter, setSelectedBusFilter] = useState(null);
  const [sessionFilter, setSessionFilter] = useState("all");
  const [newAmBus, setNewAmBus] = useState("");
  const [newPmBus, setNewPmBus] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [mapInstance, setMapInstance] = useState(null);
  const [showAddCamper, setShowAddCamper] = useState(false);
  const [newCamper, setNewCamper] = useState({
    first_name: "",
    last_name: "",
    address: "",
    town: "",
    zip_code: "",
    am_bus_number: "NONE",
    pm_bus_number: ""
  });

  const fetchCampers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/campers`);
      setCampers(response.data);
      
      // Calculate unique buses from am_bus_number and pm_bus_number
      const busSet = new Set();
      response.data.forEach(c => {
        if (c.am_bus_number) busSet.add(c.am_bus_number);
        if (c.pm_bus_number && c.pm_bus_number !== c.am_bus_number) busSet.add(c.pm_bus_number);
        if (c.bus_number) busSet.add(c.bus_number);  // Backwards compatibility
      });
      const buses = Array.from(busSet).sort();
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

  const handleSyncCampMinder = async () => {
    try {
      toast.loading("Refreshing from Google Sheet CSV...");
      
      const response = await axios.post(`${API}/trigger-sync`);
      
      toast.dismiss();
      toast.success("Data refreshed! Map updated with latest campers");
      
      await fetchCampers();
    } catch (error) {
      toast.dismiss();
      console.error("Error syncing:", error);
      toast.error("Failed to refresh data");
    }
  };

  const handleDownloadAssignments = () => {
    window.open(`${API}/download/bus-assignments`, '_blank');
    toast.success("Downloading bus assignments...");
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
    ? campers.filter(c => c.am_bus_number === selectedBusFilter || c.pm_bus_number === selectedBusFilter || c.bus_number === selectedBusFilter)
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

  const searchFilteredCampers = searchQuery.trim() === ""
    ? sessionFilteredCampers
    : sessionFilteredCampers.filter(c => {
        const query = searchQuery.toLowerCase();
        const fullName = `${c.first_name} ${c.last_name}`.toLowerCase();
        const address = c.location?.address?.toLowerCase() || '';
        const town = c.town?.toLowerCase() || '';
        return fullName.includes(query) || address.includes(query) || town.includes(query);
      });

  const handleSearchCamper = (query) => {
    setSearchQuery(query);
    if (query.trim() && searchFilteredCampers.length > 0) {
      const firstMatch = searchFilteredCampers[0];
      if (mapInstance && firstMatch.location) {
        mapInstance.panTo({
          lat: firstMatch.location.latitude,
          lng: firstMatch.location.longitude
        });
        mapInstance.setZoom(15);
        setSelectedCamper(firstMatch);
      }
    }
  };

  const handlePrintRoute = (busNumber) => {
    const encodedBusNumber = encodeURIComponent(busNumber);
    window.open(`${API}/route-sheet/${encodedBusNumber}/print`, '_blank');
  };

  const handleChangeBus = async (camperId, type) => {
    const busToUpdate = type === 'am' ? newAmBus : newPmBus;
    
    if (!busToUpdate) {
      toast.error("Please select a bus");
      return;
    }
    
    try {
      toast.loading(`Updating ${type.toUpperCase()} bus...`);
      
      const params = new URLSearchParams();
      if (type === 'am') {
        params.append('am_bus_number', newAmBus);
      } else {
        params.append('pm_bus_number', newPmBus);
      }
      
      await axios.post(`${API}/campers/${camperId}/change-bus?${params.toString()}`);
      
      toast.dismiss();
      toast.success(`${type.toUpperCase()} bus updated to ${busToUpdate}`);
      
      setNewAmBus("");
      setNewPmBus("");
      setSelectedCamper(null);
      await fetchCampers();
    } catch (error) {
      toast.dismiss();
      console.error("Error updating bus:", error);
      toast.error("Failed to update");
    }
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
          {searchFilteredCampers.map((camper, index) => {
            // Use AM bus for display unless it's PM-only
            const displayBus = camper.pickup_type === "PM Drop-off Only" 
              ? camper.pm_bus_number 
              : (camper.am_bus_number || camper.bus_number);
            const busColor = camper.pickup_type === "PM Drop-off Only"
              ? getBusColor(camper.pm_bus_number)
              : (camper.bus_color || getBusColor(camper.am_bus_number || camper.bus_number));
            
            return (
            <AdvancedMarker
              key={`${camper.first_name}-${camper.last_name}-${camper.pickup_type}-${index}`}
              position={{
                lat: camper.location.latitude,
                lng: camper.location.longitude
              }}
              onClick={() => handleMarkerClick(camper)}
            >
              <div 
                className="w-10 h-10 md:w-8 md:h-8 rounded-full flex items-center justify-center text-white font-bold text-xs shadow-lg border-2 border-white cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                style={{ backgroundColor: busColor }}
                data-testid={`bus-marker-${displayBus}`}
              >
                {displayBus ? displayBus.replace('Bus #', '').substring(0, 2) : '?'}
              </div>
            </AdvancedMarker>
            );
          })}

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
                    <span className="font-semibold">AM Bus:</span> 
                    <span 
                      className="px-2 py-0.5 rounded text-white text-xs font-medium"
                      style={{ backgroundColor: getBusColor(selectedCamper.am_bus_number || selectedCamper.bus_number) }}
                    >
                      {selectedCamper.am_bus_number || selectedCamper.bus_number}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="font-semibold">PM Bus:</span> 
                    <span 
                      className="px-2 py-0.5 rounded text-white text-xs font-medium"
                      style={{ backgroundColor: getBusColor(selectedCamper.pm_bus_number || selectedCamper.bus_number) }}
                    >
                      {selectedCamper.pm_bus_number || selectedCamper.bus_number}
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
                  
                  {/* Manual Bus Override - Separate for AM and PM */}
                  <div className="mt-3 pt-3 border-t">
                    <div className="text-xs font-semibold mb-2">Change Bus Assignments:</div>
                    <div className="space-y-2">
                      <div className="flex gap-2 items-center">
                        <span className="text-xs w-12">AM:</span>
                        <Select value={newAmBus} onValueChange={setNewAmBus}>
                          <SelectTrigger className="w-28 h-8 text-xs">
                            <SelectValue placeholder="AM Bus" />
                          </SelectTrigger>
                          <SelectContent>
                            {uniqueBuses.map(bus => (
                              <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          size="sm"
                          className="h-8 text-xs"
                          onClick={() => handleChangeBus(selectedCamper._id || `${selectedCamper.last_name}_${selectedCamper.first_name}_${selectedCamper.zip_code}`.replace(' ', '_'), 'am')}
                          disabled={!newAmBus}
                        >
                          Update AM
                        </Button>
                      </div>
                      <div className="flex gap-2 items-center">
                        <span className="text-xs w-12">PM:</span>
                        <Select value={newPmBus} onValueChange={setNewPmBus}>
                          <SelectTrigger className="w-28 h-8 text-xs">
                            <SelectValue placeholder="PM Bus" />
                          </SelectTrigger>
                          <SelectContent>
                            {uniqueBuses.map(bus => (
                              <SelectItem key={`pm-${bus}`} value={bus}>{bus}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button
                          size="sm"
                          className="h-8 text-xs"
                          onClick={() => handleChangeBus(selectedCamper._id || `${selectedCamper.last_name}_${selectedCamper.first_name}_${selectedCamper.zip_code}`.replace(' ', '_'), 'pm')}
                          disabled={!newPmBus}
                        >
                          Update PM
                        </Button>
                      </div>
                    </div>
                  </div>
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
                {/* Search Input */}
                <div className="relative">
                  <Input
                    type="text"
                    placeholder="Search camper, address, town..."
                    value={searchQuery}
                    onChange={(e) => handleSearchCamper(e.target.value)}
                    className="w-full h-12 pl-10"
                    data-testid="search-camper"
                  />
                  <Search className="absolute left-3 top-3.5 w-5 h-5 text-gray-400" />
                  {searchQuery && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-2 h-8 w-8 p-0"
                      onClick={() => {
                        setSearchQuery("");
                        setSelectedCamper(null);
                      }}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
                
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
                  className="w-full h-12 text-base bg-green-50 hover:bg-green-100 border-green-600 text-green-700"
                  onClick={handleSyncCampMinder}
                  data-testid="sync-campminder-btn"
                >
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Refresh from CSV Now
                </Button>
                
                <Button
                  variant="outline"
                  className="w-full h-12 text-base bg-purple-50 hover:bg-purple-100 border-purple-600 text-purple-700"
                  onClick={handleDownloadAssignments}
                  data-testid="download-assignments-btn"
                >
                  <Download className="w-5 h-5 mr-2" />
                  Download Bus Assignments
                </Button>
                
                <Button
                  variant="outline"
                  className="w-full h-12 text-base"
                  onClick={fetchCampers}
                  data-testid="refresh-btn"
                >
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Refresh Map Data
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
                    const busColor = getBusColor(bus);
                    const busCount = campers.filter(c => 
                      c.am_bus_number === bus || c.pm_bus_number === bus || c.bus_number === bus
                    ).length;
                    const isSelected = selectedBusFilter === bus;
                    
                    return (
                      <div
                        key={bus}
                        className={`
                          w-full flex items-center justify-between p-3 rounded-lg
                          transition-all duration-200
                          ${isSelected 
                            ? 'bg-blue-100 border-2 border-blue-600 shadow-md' 
                            : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                          }
                        `}
                        data-testid={`bus-list-item-${bus}`}
                      >
                        <button
                          onClick={() => handleBusFilter(bus)}
                          className="flex items-center gap-3 flex-1 text-left"
                        >
                          <div
                            className="w-6 h-6 md:w-5 md:h-5 rounded-full border-2 border-white shadow flex-shrink-0"
                            style={{ backgroundColor: busColor }}
                          />
                          <div>
                            <div className={`font-medium text-sm md:text-base ${isSelected ? 'text-blue-700 font-bold' : ''}`}>
                              {bus}
                            </div>
                            <div className="text-xs text-gray-500">{busCount} stops</div>
                          </div>
                        </button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePrintRoute(bus);
                          }}
                          title="Print Route Sheet"
                        >
                          <Printer className="w-4 h-4" />
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              {/* Stats Footer */}
              <div className="border-t pt-4 text-center space-y-2">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-blue-50 p-3 rounded-lg">
                    <p className="text-gray-600 text-xs mb-1">Total Campers</p>
                    <p className="font-bold text-blue-700 text-xl">{searchFilteredCampers.length}</p>
                    {(sessionFilter !== "all" || searchQuery) && (
                      <p className="text-xs text-gray-500">({campers.length} total)</p>
                    )}
                  </div>
                  <div className="bg-green-50 p-3 rounded-lg">
                    <p className="text-gray-600 text-xs mb-1">Active Buses</p>
                    <p className="font-bold text-green-700 text-xl">{uniqueBuses.length}</p>
                  </div>
                </div>
                <p className="text-xs text-gray-500">Auto-refreshes daily at 6:00 AM</p>
                <p className="text-xs text-gray-500">CampMinder sync: Every 15 min</p>
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
import React, { useState, useEffect, useCallback } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin, Printer, Filter, Download, Search, UserPlus, FileSpreadsheet } from "lucide-react";
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
  'Bus #01': '#FF0000', 'Bus #02': '#228B22', 'Bus #03': '#0000FF', 'Bus #04': '#B8860B',
  'Bus #05': '#FF00FF', 'Bus #06': '#008B8B', 'Bus #07': '#800000', 'Bus #08': '#008000',
  'Bus #09': '#000080', 'Bus #10': '#808000', 'Bus #11': '#800080', 'Bus #12': '#008080',
  'Bus #13': '#FFA500', 'Bus #14': '#FF1493', 'Bus #15': '#00CED1', 'Bus #16': '#FF4500',
  'Bus #17': '#9400D3', 'Bus #18': '#32CD32', 'Bus #19': '#DC143C', 'Bus #20': '#4169E1',
  'Bus #21': '#FF8C00', 'Bus #22': '#8B4513', 'Bus #23': '#6B8E23', 'Bus #24': '#2E8B57',
  'Bus #25': '#FF69B4', 'Bus #26': '#4682B4', 'Bus #27': '#D2691E', 'Bus #28': '#DAA520',
  'Bus #29': '#8A2BE2', 'Bus #30': '#5F9EA0', 'Bus #31': '#A52A2A', 'Bus #32': '#DEB887',
  'Bus #33': '#6495ED', 'Bus #34': '#FF7F50'
};

const getBusColor = (busNumber) => BUS_COLORS[busNumber] || '#000000';

const BusRoutingMap = () => {
  const [campers, setCampers] = useState([]);
  const [campersNeedingAddress, setCampersNeedingAddress] = useState([]);
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
      const [campersResponse, needsAddressResponse] = await Promise.all([
        axios.get(`${API}/campers`),
        axios.get(`${API}/campers/needs-address`)
      ]);
      
      setCampers(campersResponse.data);
      setCampersNeedingAddress(needsAddressResponse.data);
      
      // Calculate unique buses from am_bus_number and pm_bus_number
      // Only include valid bus assignments (not NONE or empty)
      const busSet = new Set();
      campersResponse.data.forEach(c => {
        if (c.am_bus_number && c.am_bus_number !== 'NONE' && c.am_bus_number.startsWith('Bus')) {
          busSet.add(c.am_bus_number);
        }
        if (c.pm_bus_number && c.pm_bus_number !== 'NONE' && c.pm_bus_number.startsWith('Bus')) {
          busSet.add(c.pm_bus_number);
        }
      });
      const buses = Array.from(busSet).sort();
      setUniqueBuses(buses);
      
      if (campersResponse.data.length > 0) {
        setMapCenter({
          lat: campersResponse.data[0].location.latitude,
          lng: campersResponse.data[0].location.longitude
        });
      }
      
      toast.success(`Loaded ${campersResponse.data.length} campers (${needsAddressResponse.data.length} need addresses)`);
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

  const handleTestCampMinderAPI = async () => {
    try {
      toast.loading("Testing CampMinder API connectivity...");
      
      const response = await axios.get(`${API}/test-campminder-api`);
      
      toast.dismiss();
      
      if (response.data.status === "success") {
        toast.success("CampMinder API fully operational!");
      } else if (response.data.status === "partial") {
        toast.warning(response.data.message);
      } else {
        toast.error(response.data.message);
      }
      
      // Log detailed results for debugging
      console.log("CampMinder API Test Results:", response.data);
    } catch (error) {
      toast.dismiss();
      console.error("Error testing CampMinder API:", error);
      toast.error("Failed to test CampMinder API");
    }
  };

  const handleDownloadAssignments = () => {
    window.open(`${API}/download/bus-assignments`, '_blank');
    toast.success("Downloading bus assignments...");
  };

  const handleDownloadSeatAvailability = async () => {
    try {
      toast.loading("Preparing download...");
      const response = await fetch(`${API}/download/seat-availability`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `seat_availability_${new Date().toISOString().slice(0,10)}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.dismiss();
      toast.success("Download complete!");
    } catch (error) {
      toast.dismiss();
      console.error("Download error:", error);
      toast.error("Download failed. Try opening in new tab.");
      window.open(`${API}/download/seat-availability`, '_blank');
    }
  };

  const handleRefreshSeatAvailabilitySheet = async () => {
    try {
      toast.loading("Updating Google Sheet...");
      const response = await axios.post(`${API}/push-seat-availability-to-sheet`);
      toast.dismiss();
      if (response.data.status === 'success') {
        toast.success(response.data.message);
      } else {
        toast.error(response.data.message || "Failed to update sheet");
      }
    } catch (error) {
      toast.dismiss();
      console.error("Error updating sheet:", error);
      toast.error("Failed to update Google Sheet");
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

  const handleAddCamper = async () => {
    if (!newCamper.first_name || !newCamper.last_name || !newCamper.address || !newCamper.town || !newCamper.zip_code) {
      toast.error("Please fill in all required fields");
      return;
    }

    try {
      toast.loading("Adding camper...");
      const response = await axios.post(`${API}/campers/add`, {
        ...newCamper,
        pm_bus_number: newCamper.pm_bus_number || newCamper.am_bus_number
      });
      
      toast.dismiss();
      toast.success(`Added ${newCamper.first_name} ${newCamper.last_name}`);
      
      // Reset form and close dialog
      setNewCamper({
        first_name: "",
        last_name: "",
        address: "",
        town: "",
        zip_code: "",
        am_bus_number: "NONE",
        pm_bus_number: ""
      });
      setShowAddCamper(false);
      
      // Refresh the map
      await fetchCampers();
    } catch (error) {
      toast.dismiss();
      console.error("Error adding camper:", error);
      toast.error(error.response?.data?.detail || "Failed to add camper");
    }
  };

  const handleDeleteCamper = async (camperId, camperName) => {
    if (!window.confirm(`Are you sure you want to delete ${camperName}?`)) {
      return;
    }
    
    try {
      toast.loading("Deleting camper...");
      await axios.delete(`${API}/campers/${camperId}`);
      
      toast.dismiss();
      toast.success(`Deleted ${camperName}`);
      setSelectedCamper(null);
      await fetchCampers();
    } catch (error) {
      toast.dismiss();
      console.error("Error deleting camper:", error);
      toast.error(error.response?.data?.detail || "Failed to delete camper");
    }
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
            // Determine which bus to display on the pin
            // Rule: Show AM bus if valid, otherwise show PM bus if valid
            const hasValidAmBus = camper.am_bus_number && camper.am_bus_number !== 'NONE' && camper.am_bus_number.startsWith('Bus');
            const hasValidPmBus = camper.pm_bus_number && camper.pm_bus_number !== 'NONE' && camper.pm_bus_number.startsWith('Bus');
            
            // Skip campers with no valid bus at all
            if (!hasValidAmBus && !hasValidPmBus) {
              return null;
            }
            
            // Check if this is a PM-specific entry (different PM address)
            const isPmSpecificEntry = camper._id && camper._id.endsWith('_PM');
            
            // For PM-specific entries, show PM bus. Otherwise prefer AM bus.
            let displayBus, busColor;
            
            if (isPmSpecificEntry) {
              // This is a PM dropoff location - show PM bus
              displayBus = camper.pm_bus_number;
              busColor = getBusColor(camper.pm_bus_number);
            } else if (hasValidAmBus) {
              // Regular entry with AM bus - show AM bus
              displayBus = camper.am_bus_number;
              busColor = camper.bus_color || getBusColor(camper.am_bus_number);
            } else {
              // No AM bus, show PM bus
              displayBus = camper.pm_bus_number;
              busColor = getBusColor(camper.pm_bus_number);
            }
            
            // Get display text (bus number only)
            const displayText = displayBus ? displayBus.replace('Bus #', '').substring(0, 2) : '?';
            
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
                {displayText}
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
                {/* Helper function to check valid bus */}
                {(() => {
                  const hasValidAmBus = selectedCamper.am_bus_number && 
                    selectedCamper.am_bus_number !== 'NONE' && 
                    selectedCamper.am_bus_number.startsWith('Bus');
                  const hasValidPmBus = selectedCamper.pm_bus_number && 
                    selectedCamper.pm_bus_number !== 'NONE' && 
                    selectedCamper.pm_bus_number.startsWith('Bus');
                  
                  // Check if this is a PM-specific location
                  const isPmLocation = selectedCamper._id && selectedCamper._id.endsWith('_PM');
                  
                  return (
                    <>
                      <h3 className="font-bold text-base md:text-lg mb-2">
                        {selectedCamper.first_name} {selectedCamper.last_name}
                      </h3>
                      
                      {/* Show location type badge */}
                      {isPmLocation ? (
                        <div className="mb-2 px-2 py-1 bg-orange-100 text-orange-800 text-xs rounded inline-block font-semibold">
                          📍 PM Drop-off Location
                        </div>
                      ) : hasValidAmBus && hasValidPmBus && selectedCamper.am_bus_number !== selectedCamper.pm_bus_number ? (
                        <div className="mb-2 px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded inline-block font-semibold">
                          📍 AM Pickup Location
                        </div>
                      ) : null}
                      
                      <div className="space-y-1 text-xs md:text-sm">
                        {/* Only show AM Bus if valid */}
                        {hasValidAmBus && (
                          <div className="flex flex-wrap items-center gap-1">
                            <span className="font-semibold">AM Bus:</span> 
                            <span 
                              className="px-2 py-0.5 rounded text-white text-xs font-medium"
                              style={{ backgroundColor: getBusColor(selectedCamper.am_bus_number) }}
                            >
                              {selectedCamper.am_bus_number}
                            </span>
                          </div>
                        )}
                        {/* Only show PM Bus if valid */}
                        {hasValidPmBus && (
                          <div className="flex flex-wrap items-center gap-1">
                            <span className="font-semibold">PM Bus:</span> 
                            <span 
                              className="px-2 py-0.5 rounded text-white text-xs font-medium"
                              style={{ backgroundColor: getBusColor(selectedCamper.pm_bus_number) }}
                            >
                              {selectedCamper.pm_bus_number}
                            </span>
                          </div>
                        )}
                        {/* Show message if no buses assigned */}
                        {!hasValidAmBus && !hasValidPmBus && (
                          <div className="text-red-600 font-semibold">No bus assigned</div>
                        )}
                        <div>
                          <span className="font-semibold">Session:</span> {selectedCamper.session}
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
                                  {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
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
                                  {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
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
                  
                        {/* Delete Button */}
                        <div className="border-t pt-2 mt-2">
                          <Button
                            variant="destructive"
                            size="sm"
                            className="w-full h-8 text-xs"
                            onClick={() => handleDeleteCamper(
                              selectedCamper._id || `${selectedCamper.last_name}_${selectedCamper.first_name}_${selectedCamper.zip_code}`.replace(' ', '_'),
                              `${selectedCamper.first_name} ${selectedCamper.last_name}`
                            )}
                          >
                            Delete Camper
                          </Button>
                        </div>
                      </div>
                    </>
                  );
                })()}
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
          <div className="h-full md:h-auto flex flex-col md:max-h-[calc(100vh-2rem)] overflow-hidden">
            {/* Header */}
            <div className="p-4 md:p-4 bg-gradient-to-br from-blue-600 to-blue-700 text-white flex-shrink-0">
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

                <Dialog open={showAddCamper} onOpenChange={setShowAddCamper}>
                  <DialogTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full h-12 text-base bg-orange-50 hover:bg-orange-100 border-orange-600 text-orange-700"
                      data-testid="add-camper-btn"
                    >
                      <UserPlus className="w-5 h-5 mr-2" />
                      Add Camper Manually
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                      <DialogTitle>Add Camper</DialogTitle>
                      <DialogDescription>
                        Manually add a camper to the map. They will appear as a pin once added.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="first_name">First Name *</Label>
                          <Input
                            id="first_name"
                            value={newCamper.first_name}
                            onChange={(e) => setNewCamper({...newCamper, first_name: e.target.value})}
                            placeholder="John"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="last_name">Last Name *</Label>
                          <Input
                            id="last_name"
                            value={newCamper.last_name}
                            onChange={(e) => setNewCamper({...newCamper, last_name: e.target.value})}
                            placeholder="Doe"
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="address">Address *</Label>
                        <Input
                          id="address"
                          value={newCamper.address}
                          onChange={(e) => setNewCamper({...newCamper, address: e.target.value})}
                          placeholder="123 Main St"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="town">Town *</Label>
                          <Input
                            id="town"
                            value={newCamper.town}
                            onChange={(e) => setNewCamper({...newCamper, town: e.target.value})}
                            placeholder="Rockville Centre"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="zip_code">Zip Code *</Label>
                          <Input
                            id="zip_code"
                            value={newCamper.zip_code}
                            onChange={(e) => setNewCamper({...newCamper, zip_code: e.target.value})}
                            placeholder="11570"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="am_bus">AM Bus</Label>
                          <Select
                            value={newCamper.am_bus_number}
                            onValueChange={(value) => setNewCamper({...newCamper, am_bus_number: value})}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select bus" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="NONE">NONE (Assign Later)</SelectItem>
                              {Array.from({length: 34}, (_, i) => `Bus #${String(i + 1).padStart(2, '0')}`).map(bus => (
                                <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="pm_bus">PM Bus</Label>
                          <Select
                            value={newCamper.pm_bus_number || newCamper.am_bus_number}
                            onValueChange={(value) => setNewCamper({...newCamper, pm_bus_number: value})}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Same as AM" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="NONE">NONE</SelectItem>
                              {Array.from({length: 34}, (_, i) => `Bus #${String(i + 1).padStart(2, '0')}`).map(bus => (
                                <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowAddCamper(false)}>Cancel</Button>
                      <Button onClick={handleAddCamper}>Add Camper</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
                
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
                  className="w-full h-12 text-base bg-teal-50 hover:bg-teal-100 border-teal-600 text-teal-700"
                  onClick={handleDownloadSeatAvailability}
                  data-testid="download-seat-availability-btn"
                >
                  <FileSpreadsheet className="w-5 h-5 mr-2" />
                  Download Seat Availability
                </Button>

                <Button
                  variant="outline"
                  className="w-full h-12 text-base bg-orange-50 hover:bg-orange-100 border-orange-600 text-orange-700"
                  onClick={handleRefreshSeatAvailabilitySheet}
                  data-testid="refresh-seat-sheet-btn"
                >
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Update Seat Availability Sheet
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
              <div className="border-t pt-4 flex-1 min-h-0 flex flex-col">
                <h3 className="font-semibold mb-3 text-sm text-gray-700 flex items-center justify-between flex-shrink-0">
                  <span>Active Buses ({uniqueBuses.length})</span>
                  {selectedBusFilter && (
                    <span className="text-xs text-blue-600">Filtered</span>
                  )}
                </h3>
                <div className="space-y-2 overflow-y-auto flex-1" style={{maxHeight: '300px'}}>
                  {uniqueBuses.filter(bus => bus.startsWith('Bus')).map((bus) => {
                    const busColor = getBusColor(bus);
                    // Count only valid bus assignments (not NONE)
                    const busCount = campers.filter(c => 
                      (c.am_bus_number === bus && c.am_bus_number !== 'NONE') || 
                      (c.pm_bus_number === bus && c.pm_bus_number !== 'NONE')
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
              
              {/* Needs Address Section */}
              {campersNeedingAddress.length > 0 && (
                <div className="border-t pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <span className="font-semibold text-red-700">Needs Address ({campersNeedingAddress.length})</span>
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {campersNeedingAddress.map((camper, idx) => (
                      <div 
                        key={idx}
                        className="text-xs p-2 bg-red-50 rounded border border-red-200"
                      >
                        <div className="font-medium text-red-800">
                          {camper.first_name} {camper.last_name}
                        </div>
                        <div className="text-red-600">
                          AM: {camper.am_bus_number || 'None'} | PM: {camper.pm_bus_number || 'None'}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-red-600 mt-2 italic">
                    Add addresses in Google Sheet to show on map
                  </p>
                </div>
              )}
              
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
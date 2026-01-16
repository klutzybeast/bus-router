import React, { useState, useEffect, useCallback, useMemo } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow, useMap } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin, Printer, Filter, Download, Search, UserPlus, FileSpreadsheet, Settings, Trash2, Layers, Eye, EyeOff } from "lucide-react";
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
import EditableBusZone from "./EditableBusZone";
import ZoneCreator from "./ZoneCreator";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
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

// Component to handle map controls using the useMap hook
const MapController = ({ selectedCamper, onMapReady }) => {
  const map = useMap();
  
  useEffect(() => {
    if (map) {
      onMapReady(map);
    }
  }, [map, onMapReady]);
  
  useEffect(() => {
    if (map && selectedCamper && selectedCamper.location) {
      // Zoom in and center on the selected pin
      // Use zoom 17 to show more surrounding area while still readable
      // Offset center south so the pin and InfoWindow are both visible
      const latOffset = -0.001; // Shift center south to show pin below InfoWindow
      map.setZoom(17);
      map.panTo({
        lat: selectedCamper.location.latitude + latOffset,
        lng: selectedCamper.location.longitude
      });
    }
  }, [map, selectedCamper]);
  
  return null;
};

const BusRoutingMap = () => {
  const [campers, setCampers] = useState([]);
  const [campersNeedingAddress, setCampersNeedingAddress] = useState([]);
  const [selectedCamper, setSelectedCamper] = useState(null);
  const [loading, setLoading] = useState(true);
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
  
  // Multiple search results dialog state
  const [showMultipleResults, setShowMultipleResults] = useState(false);
  const [multipleResultsCampers, setMultipleResultsCampers] = useState([]);
  
  // Fixed initial map center (Long Island area) - never changes
  const INITIAL_MAP_CENTER = { lat: 40.7128, lng: -73.7949 };
  const INITIAL_ZOOM = 11;
  
  // Bus Staff Configuration State
  const [showStaffConfig, setShowStaffConfig] = useState(false);
  const [busStaffList, setBusStaffList] = useState({});
  const [selectedStaffBus, setSelectedStaffBus] = useState("");
  const [staffForm, setStaffForm] = useState({
    driver_name: "",
    counselor_name: "",
    home_address: "",
    capacity: "",
    location_name: ""
  });

  // Bus Zone State - User-defined zones
  const [showBusZones, setShowBusZones] = useState(false);
  const [selectedZoneBus, setSelectedZoneBus] = useState(null);
  const [userZones, setUserZones] = useState({}); // { busNumber: { points: [], color, name } }
  const [isCreatingZone, setIsCreatingZone] = useState(false);
  const [creatingZoneBus, setCreatingZoneBus] = useState(null);
  const [newZonePoints, setNewZonePoints] = useState([]);
  const [editingZoneBus, setEditingZoneBus] = useState(null);

  // Bus Info State (capacities)
  const [busInfoMap, setBusInfoMap] = useState({});

  // Seat availability from backend (accurate counts including campers without addresses)
  const [busSeatAvailability, setBusSeatAvailability] = useState({});

  // Shadow staff state
  const [shadows, setShadows] = useState({}); // { camper_id: shadow_info }
  const [shadowsList, setShadowsList] = useState([]); // Array of all shadows
  const [showShadowDialog, setShowShadowDialog] = useState(false);
  const [shadowName, setShadowName] = useState("");
  const [selectedShadowBus, setSelectedShadowBus] = useState("");
  const [selectedShadowCamper, setSelectedShadowCamper] = useState("");

  // Fetch shadows from backend
  const fetchShadows = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/shadows`);
      const shadowsArray = response.data.shadows || [];
      const shadowsMap = {};
      shadowsArray.forEach(shadow => {
        shadowsMap[shadow.camper_id] = shadow;
      });
      setShadows(shadowsMap);
      setShadowsList(shadowsArray);
    } catch (error) {
      console.error("Error fetching shadows:", error);
    }
  }, []);

  // Get campers on a specific bus (for shadow dropdown)
  // Only shows campers who are actually on that bus for their route
  // - For PM-specific entries (_PM suffix), only show if pm_bus matches
  // - For regular entries, only show if am_bus matches (or pm_bus if no am_bus)
  const getCampersOnBus = useCallback((busNumber) => {
    if (!busNumber) return [];
    
    return campers.filter(c => {
      const isPmEntry = c._id && c._id.endsWith('_PM');
      
      if (isPmEntry) {
        // PM-specific entry - only show if this is their PM bus
        return c.pm_bus_number === busNumber;
      } else {
        // Regular entry - show if this is their AM bus
        // OR if they have no AM bus but this is their PM bus
        const hasAmBus = c.am_bus_number && c.am_bus_number !== 'NONE' && c.am_bus_number.startsWith('Bus');
        if (hasAmBus) {
          return c.am_bus_number === busNumber;
        } else {
          return c.pm_bus_number === busNumber;
        }
      }
    }).map(c => {
      // Add route info for display
      const isPmEntry = c._id && c._id.endsWith('_PM');
      const routeType = isPmEntry ? 'PM' : 'AM';
      const town = c.town || '';
      return {
        ...c,
        routeType,
        displayName: `${c.last_name}, ${c.first_name}`,
        displayDetail: town ? `${routeType} - ${town}` : routeType
      };
    }).sort((a, b) => 
      a.displayName.localeCompare(b.displayName)
    );
  }, [campers]);

  // Save shadow from dialog
  const handleSaveShadowDialog = async () => {
    if (!shadowName.trim()) {
      toast.error("Please enter a shadow name");
      return;
    }
    if (!selectedShadowBus) {
      toast.error("Please select a bus");
      return;
    }
    if (!selectedShadowCamper) {
      toast.error("Please select a child to link");
      return;
    }
    try {
      toast.loading("Saving shadow...");
      await axios.post(`${API}/shadows`, {
        shadow_name: shadowName.trim(),
        camper_id: selectedShadowCamper,
        bus_number: selectedShadowBus  // Pass the selected bus explicitly
      });
      toast.dismiss();
      toast.success("Shadow saved successfully");
      // Reset form
      setShadowName("");
      setSelectedShadowBus("");
      setSelectedShadowCamper("");
      // Refresh data
      await fetchShadows();
      await fetchSeatAvailability(); // Update seat counts
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || "Failed to save shadow");
    }
  };

  // Delete shadow
  const handleDeleteShadow = async (shadowId) => {
    try {
      toast.loading("Removing shadow...");
      await axios.delete(`${API}/shadows/${shadowId}`);
      toast.dismiss();
      toast.success("Shadow removed");
      await fetchShadows();
      await fetchSeatAvailability(); // Update seat counts
    } catch (error) {
      toast.dismiss();
      toast.error("Failed to remove shadow");
    }
  };

  // Fetch user-defined zones from backend
  const fetchUserZones = useCallback(async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/bus-zones`);
      const zonesArray = response.data.zones || [];
      const zonesMap = {};
      zonesArray.forEach(zone => {
        zonesMap[zone.bus_number] = {
          points: zone.points || [],
          color: zone.color || getBusColor(zone.bus_number),
          name: zone.name || `${zone.bus_number} Zone`
        };
      });
      setUserZones(zonesMap);
    } catch (error) {
      console.error("Error fetching user zones:", error);
    }
  }, []);

  // Save a zone to the backend
  const saveZone = useCallback(async (busNumber, points, isNew = false) => {
    try {
      const color = getBusColor(busNumber);
      if (isNew) {
        await axios.post(`${BACKEND_URL}/api/bus-zones`, {
          bus_number: busNumber,
          points: points,
          color: color,
          name: `${busNumber} Zone`
        });
        toast.success(`Zone created for ${busNumber}`);
      } else {
        await axios.put(`${BACKEND_URL}/api/bus-zones/${encodeURIComponent(busNumber)}`, {
          points: points
        });
        toast.success(`Zone updated for ${busNumber}`);
      }
      // Refresh zones
      await fetchUserZones();
    } catch (error) {
      console.error("Error saving zone:", error);
      toast.error(`Failed to save zone: ${error.response?.data?.detail || error.message}`);
    }
  }, [fetchUserZones]);

  // Delete a zone
  const deleteZone = useCallback(async (busNumber) => {
    try {
      await axios.delete(`${BACKEND_URL}/api/bus-zones/${encodeURIComponent(busNumber)}`);
      toast.success(`Zone deleted for ${busNumber}`);
      await fetchUserZones();
    } catch (error) {
      console.error("Error deleting zone:", error);
      toast.error(`Failed to delete zone: ${error.response?.data?.detail || error.message}`);
    }
  }, [fetchUserZones]);

  // Group campers by bus number (for reference, not for auto-zones anymore)
  const campersByBus = useMemo(() => {
    const grouped = {};
    campers.forEach(camper => {
      // Group by AM bus
      if (camper.am_bus_number && camper.am_bus_number !== 'NONE' && camper.am_bus_number.startsWith('Bus')) {
        if (!grouped[camper.am_bus_number]) {
          grouped[camper.am_bus_number] = [];
        }
        grouped[camper.am_bus_number].push(camper);
      }
      // Also consider PM bus if different (for overlapping zones)
      if (camper.pm_bus_number && camper.pm_bus_number !== 'NONE' && 
          camper.pm_bus_number.startsWith('Bus') && camper.pm_bus_number !== camper.am_bus_number) {
        if (!grouped[camper.pm_bus_number]) {
          grouped[camper.pm_bus_number] = [];
        }
        // Only add if not already in this bus group
        if (!grouped[camper.pm_bus_number].some(c => c._id === camper._id)) {
          grouped[camper.pm_bus_number].push(camper);
        }
      }
    });
    return grouped;
  }, [campers]);

  // Handle zone click - select/deselect bus (with optional pan)
  const handleZoneClick = useCallback((busNumber, shouldPan = true) => {
    if (selectedZoneBus === busNumber) {
      setSelectedZoneBus(null);
      setSelectedBusFilter(null);
    } else {
      setSelectedZoneBus(busNumber);
      setSelectedBusFilter(busNumber);
      // Only pan to the zone if explicitly requested
      if (shouldPan) {
        const busCampers = campersByBus[busNumber];
        if (busCampers && busCampers.length > 0 && mapInstance) {
          const avgLat = busCampers.reduce((sum, c) => sum + c.location.latitude, 0) / busCampers.length;
          const avgLng = busCampers.reduce((sum, c) => sum + c.location.longitude, 0) / busCampers.length;
          mapInstance.panTo({ lat: avgLat, lng: avgLng });
        }
      }
    }
  }, [selectedZoneBus, campersByBus, mapInstance]);

  const fetchBusStaff = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/bus-staff`);
      if (response.data.status === 'success') {
        setBusStaffList(response.data.staff || {});
      }
    } catch (error) {
      console.error("Error fetching bus staff:", error);
    }
  }, []);

  const fetchBusInfo = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/buses`);
      if (response.data.status === 'success' && response.data.buses) {
        const infoMap = {};
        response.data.buses.forEach(bus => {
          infoMap[bus.bus_number] = bus;
        });
        setBusInfoMap(infoMap);
      }
    } catch (error) {
      console.error("Error fetching bus info:", error);
    }
  }, []);

  const fetchSeatAvailability = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/seat-availability-json`);
      if (response.data.status === 'success' && response.data.buses) {
        // Transform backend data to frontend format
        const availability = {};
        Object.entries(response.data.buses).forEach(([busNumber, data]) => {
          availability[busNumber] = {
            capacity: data.capacity,
            h1AmAvailable: data.h1_am_available,
            h1PmAvailable: data.h1_pm_available,
            h2AmAvailable: data.h2_am_available,
            h2PmAvailable: data.h2_pm_available,
            h1AmCount: data.h1_am,
            h1PmCount: data.h1_pm,
            h2AmCount: data.h2_am,
            h2PmCount: data.h2_pm,
          };
        });
        setBusSeatAvailability(availability);
      }
    } catch (error) {
      console.error("Error fetching seat availability:", error);
    }
  }, []);

  const fetchCampers = useCallback(async (preserveSelection = false) => {
    try {
      // Only show loading spinner on initial load, not on refresh
      if (!preserveSelection) {
        setLoading(true);
      }
      const [campersResponse, needsAddressResponse] = await Promise.all([
        axios.get(`${API}/campers`),
        axios.get(`${API}/campers/needs-address`)
      ]);
      
      setCampers(campersResponse.data);
      setCampersNeedingAddress(needsAddressResponse.data);
      
      // If we have a selected camper, update it with fresh data
      if (preserveSelection && selectedCamper) {
        const updatedSelectedCamper = campersResponse.data.find(
          c => c._id === selectedCamper._id
        );
        if (updatedSelectedCamper) {
          setSelectedCamper(updatedSelectedCamper);
        }
      }
      
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
      
      if (!preserveSelection) {
        toast.success(`Loaded ${campersResponse.data.length} campers (${needsAddressResponse.data.length} need addresses)`);
      }
    } catch (error) {
      console.error("Error fetching campers:", error);
      if (!preserveSelection) {
        toast.error("Failed to load camper data");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampers();
    fetchBusStaff();
    fetchBusInfo();
    fetchSeatAvailability();
    fetchUserZones(); // Fetch user-defined zones
    fetchShadows(); // Fetch shadow staff
    
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(6, 0, 0, 0);
    
    const timeUntilMorning = tomorrow.getTime() - now.getTime();
    
    const timeout = setTimeout(() => {
      fetchCampers();
      fetchSeatAvailability();
      
      const interval = setInterval(() => {
        fetchCampers();
        fetchSeatAvailability();
      }, 24 * 60 * 60 * 1000);
      
      return () => clearInterval(interval);
    }, timeUntilMorning);
    
    return () => clearTimeout(timeout);
  }, [fetchCampers, fetchBusInfo, fetchSeatAvailability, fetchUserZones]);

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

  const handleDownloadAssignments = async () => {
    // Check if mobile device
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
      // For mobile: direct navigation works best
      toast.success("Opening download...");
      window.location.href = `${API}/download/bus-assignments`;
      return;
    }
    
    // Desktop: use fetch/blob approach
    const toastId = toast.loading("Downloading bus assignments...");
    
    try {
      const response = await fetch(`${API}/download/bus-assignments`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const blob = await response.blob();
      const filename = `bus-assignments-${new Date().toISOString().split('T')[0]}.csv`;
      
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      toast.dismiss(toastId);
      toast.success(`Downloaded ${filename}`);
    } catch (error) {
      console.error("Download error:", error);
      toast.dismiss(toastId);
      // Fallback: direct URL navigation
      window.location.href = `${API}/download/bus-assignments`;
    }
  };

  const handleDownloadSeatAvailability = async () => {
    // Check if mobile device
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
      // For mobile: direct navigation works best
      toast.success("Opening download...");
      window.location.href = `${API}/download/seat-availability`;
      return;
    }
    
    // Desktop: use fetch/blob approach
    const toastId = toast.loading("Downloading seat availability...");
    
    try {
      const response = await fetch(`${API}/download/seat-availability`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const blob = await response.blob();
      const filename = `seat-availability-${new Date().toISOString().split('T')[0]}.xlsx`;
      
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      toast.dismiss(toastId);
      toast.success(`Downloaded ${filename}`);
    } catch (error) {
      console.error("Download error:", error);
      toast.dismiss(toastId);
      // Fallback: direct URL navigation
      window.location.href = `${API}/download/seat-availability`;
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

  // Bus Staff Configuration Functions
  const loadStaffForBus = async (busNumber) => {
    setSelectedStaffBus(busNumber);
    if (busStaffList[busNumber]) {
      const staff = busStaffList[busNumber];
      setStaffForm({
        driver_name: staff.driver_name || "",
        counselor_name: staff.counselor_name || "",
        home_address: staff.home_address || "",
        capacity: staff.capacity?.toString() || "",
        location_name: staff.location_name || ""
      });
    } else {
      // Load defaults from API
      try {
        const response = await axios.get(`${API}/bus-staff/${encodeURIComponent(busNumber)}`);
        if (response.data.status === 'success') {
          setStaffForm({
            driver_name: response.data.driver_name || "",
            counselor_name: response.data.counselor_name || "",
            home_address: response.data.home_address || "",
            capacity: response.data.capacity?.toString() || "",
            location_name: response.data.location_name || ""
          });
        }
      } catch (error) {
        setStaffForm({
          driver_name: "",
          counselor_name: "",
          home_address: "",
          capacity: "",
          location_name: ""
        });
      }
    }
  };

  const handleSaveStaff = async () => {
    if (!selectedStaffBus) {
      toast.error("Please select a bus");
      return;
    }
    if (!staffForm.driver_name.trim()) {
      toast.error("Please enter driver name");
      return;
    }
    if (!staffForm.counselor_name.trim()) {
      toast.error("Please enter counselor name");
      return;
    }

    try {
      toast.loading("Saving configuration...");
      const response = await axios.post(`${API}/bus-staff`, {
        bus_number: selectedStaffBus,
        driver_name: staffForm.driver_name.trim(),
        counselor_name: staffForm.counselor_name.trim(),
        home_address: staffForm.home_address.trim(),
        capacity: staffForm.capacity ? parseInt(staffForm.capacity) : null,
        location_name: staffForm.location_name.trim()
      });
      toast.dismiss();

      if (response.data.status === 'success') {
        toast.success(`Saved: ${selectedStaffBus} - Driver: ${staffForm.driver_name}, Counselor: ${staffForm.counselor_name}`);
        await fetchBusStaff();
        // Clear form
        setSelectedStaffBus("");
        setStaffForm({
          driver_name: "",
          counselor_name: "",
          home_address: "",
          capacity: "",
          location_name: ""
        });
      } else {
        toast.error(response.data.message || "Failed to save");
      }
    } catch (error) {
      toast.dismiss();
      console.error("Error saving staff:", error);
      toast.error("Failed to save configuration");
    }
  };

  const handleDeleteStaff = async (busNumber) => {
    if (!window.confirm(`Delete configuration for ${busNumber}?`)) {
      return;
    }

    try {
      const response = await axios.delete(`${API}/bus-staff/${encodeURIComponent(busNumber)}`);
      if (response.data.status === 'success') {
        toast.success(`Deleted configuration for ${busNumber}`);
        await fetchBusStaff();
      } else {
        toast.error(response.data.message || "Failed to delete");
      }
    } catch (error) {
      console.error("Error deleting staff:", error);
      toast.error("Failed to delete configuration");
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
      setSelectedZoneBus(null);
    } else {
      setSelectedBusFilter(busNumber);
      setSelectedZoneBus(busNumber);
      const busStop = campers.find(c => c.bus_number === busNumber || c.am_bus_number === busNumber);
      if (busStop && mapInstance) {
        mapInstance.panTo({
          lat: busStop.location.latitude,
          lng: busStop.location.longitude
        });
        mapInstance.setZoom(13);
      }
    }
  };

  // Filter campers by selected bus
  // For campers with different AM/PM addresses (separate entries), only show the entry for the correct route
  const filteredCampers = selectedBusFilter 
    ? campers.filter(c => {
        const isPmEntry = c._id && c._id.endsWith('_PM');
        
        if (isPmEntry) {
          // PM-specific entry - only show if the selected bus is their PM bus
          return c.pm_bus_number === selectedBusFilter;
        } else {
          // Regular entry - check if this is an AM entry for a camper with different AM/PM buses
          const hasDifferentPmBus = c.am_bus_number && c.pm_bus_number && 
                                     c.am_bus_number !== c.pm_bus_number &&
                                     c.am_bus_number !== 'NONE' && c.pm_bus_number !== 'NONE';
          
          if (hasDifferentPmBus) {
            // This camper has separate AM/PM addresses - only show on AM bus
            return c.am_bus_number === selectedBusFilter;
          } else {
            // Normal camper - show if either AM or PM bus matches
            return c.am_bus_number === selectedBusFilter || 
                   c.pm_bus_number === selectedBusFilter || 
                   c.bus_number === selectedBusFilter;
          }
        }
      })
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

  // Search matches - used only for navigation, NOT for filtering map pins
  const searchMatches = searchQuery.trim() === ""
    ? []
    : sessionFilteredCampers.filter(c => {
        const query = searchQuery.toLowerCase();
        const fullName = `${c.first_name} ${c.last_name}`.toLowerCase();
        const address = c.location?.address?.toLowerCase() || '';
        const town = c.town?.toLowerCase() || '';
        return fullName.includes(query) || address.includes(query) || town.includes(query);
      });

  const handleSearchCamper = (query) => {
    setSearchQuery(query);
    // Just update search text, don't filter pins
  };

  const handleSearchSubmit = () => {
    // Pan to the matching camper when Enter is pressed
    if (searchQuery.trim() && searchMatches.length > 0) {
      // If multiple matches found, show selection dialog
      if (searchMatches.length > 1) {
        // Sort matches by last name, then first name, then AM/PM
        const sortedMatches = [...searchMatches].sort((a, b) => {
          const lastNameCompare = a.last_name.localeCompare(b.last_name);
          if (lastNameCompare !== 0) return lastNameCompare;
          const firstNameCompare = a.first_name.localeCompare(b.first_name);
          if (firstNameCompare !== 0) return firstNameCompare;
          // Sort AM before PM
          const aIsPm = a._id && a._id.endsWith('_PM');
          const bIsPm = b._id && b._id.endsWith('_PM');
          return aIsPm === bIsPm ? 0 : aIsPm ? 1 : -1;
        });
        
        setMultipleResultsCampers(sortedMatches);
        setShowMultipleResults(true);
        return;
      }
      
      // Single match - navigate directly
      const firstMatch = searchMatches[0];
      if (mapInstance && firstMatch.location) {
        mapInstance.panTo({
          lat: firstMatch.location.latitude,
          lng: firstMatch.location.longitude
        });
        mapInstance.setZoom(17);
        setSelectedCamper(firstMatch);
        toast.success(`Found: ${firstMatch.first_name} ${firstMatch.last_name}`);
      }
    } else if (searchQuery.trim()) {
      toast.error("No campers found matching your search");
    }
  };

  const handleSelectSearchResult = (camper) => {
    setShowMultipleResults(false);
    setMultipleResultsCampers([]);
    if (mapInstance && camper.location) {
      mapInstance.panTo({
        lat: camper.location.latitude,
        lng: camper.location.longitude
      });
      mapInstance.setZoom(17);
      setSelectedCamper(camper);
      const isPm = camper._id && camper._id.endsWith('_PM');
      const routeType = isPm ? 'PM' : 'AM';
      toast.success(`Found: ${camper.first_name} ${camper.last_name} (${routeType} - ${camper.town || 'Unknown'})`);
    }
  };

  // Navigate to a camper's other location (AM <-> PM)
  const handleNavigateToOtherStop = (currentCamper, targetRoute) => {
    const currentId = currentCamper._id || '';
    const firstName = currentCamper.first_name;
    const lastName = currentCamper.last_name;
    
    // Find the other entry for this camper
    let otherEntry = null;
    
    if (targetRoute === 'PM') {
      // Looking for PM entry - should end with _PM
      otherEntry = campers.find(c => 
        c.first_name === firstName && 
        c.last_name === lastName && 
        c._id && c._id.endsWith('_PM') &&
        c._id !== currentId
      );
    } else {
      // Looking for AM entry - should NOT end with _PM
      otherEntry = campers.find(c => 
        c.first_name === firstName && 
        c.last_name === lastName && 
        c._id && !c._id.endsWith('_PM') &&
        c._id !== currentId
      );
    }
    
    if (otherEntry && mapInstance && otherEntry.location) {
      mapInstance.panTo({
        lat: otherEntry.location.latitude,
        lng: otherEntry.location.longitude
      });
      mapInstance.setZoom(17);
      setSelectedCamper(otherEntry);
      toast.success(`Switched to ${targetRoute} stop: ${otherEntry.town || 'Unknown'}`);
    } else {
      toast.error(`No ${targetRoute} location found for this camper`);
    }
  };

  // Check if a camper has a separate entry for the other route
  const hasOtherRouteEntry = (camper, targetRoute) => {
    const firstName = camper.first_name;
    const lastName = camper.last_name;
    const currentId = camper._id || '';
    
    if (targetRoute === 'PM') {
      return campers.some(c => 
        c.first_name === firstName && 
        c.last_name === lastName && 
        c._id && c._id.endsWith('_PM') &&
        c._id !== currentId
      );
    } else {
      return campers.some(c => 
        c.first_name === firstName && 
        c.last_name === lastName && 
        c._id && !c._id.endsWith('_PM') &&
        c._id !== currentId
      );
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
      
      // Update the selected camper locally without closing the popup
      if (selectedCamper) {
        const updatedCamper = {
          ...selectedCamper,
          ...(type === 'am' ? { am_bus_number: newAmBus, bus_color: getBusColor(newAmBus) } : { pm_bus_number: newPmBus })
        };
        setSelectedCamper(updatedCamper);
        
        // Update the camper in the local campers array - this triggers zone recalculation
        setCampers(prevCampers => 
          prevCampers.map(c => 
            c._id === camperId ? updatedCamper : c
          )
        );
        
        // Update zone filter WITHOUT panning the map
        if (showBusZones) {
          const newBus = type === 'am' ? newAmBus : newPmBus;
          // Just update the filter state, don't trigger pan
          setSelectedBusFilter(newBus);
          setSelectedZoneBus(newBus);
        }
      }
      
      // Clear the selection dropdowns but keep popup open
      setNewAmBus("");
      setNewPmBus("");
      
      // Fetch updated data in background without resetting selection
      fetchCampers(true);
      fetchSeatAvailability();
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
          defaultCenter={INITIAL_MAP_CENTER}
          defaultZoom={INITIAL_ZOOM}
          mapId="bus-routing-map"
          gestureHandling="greedy"
          disableDefaultUI={false}
          clickableIcons={true}
        >
          <MapController 
            selectedCamper={selectedCamper} 
            onMapReady={setMapInstance}
          />
          {sessionFilteredCampers.map((camper, index) => {
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
              disableAutoPan={false}
              options={{
                pixelOffset: new window.google.maps.Size(0, -5),
                maxWidth: 320
              }}
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
                  
                  // Get staff info for the relevant bus
                  const relevantBus = isPmLocation ? selectedCamper.pm_bus_number : selectedCamper.am_bus_number;
                  const staffInfo = busStaffList[relevantBus] || {};
                  
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
                            {/* Make clickable if viewing PM location and AM entry exists */}
                            {isPmLocation && hasOtherRouteEntry(selectedCamper, 'AM') ? (
                              <button
                                onClick={() => handleNavigateToOtherStop(selectedCamper, 'AM')}
                                className="px-2 py-0.5 rounded text-white text-xs font-medium cursor-pointer hover:opacity-80 hover:ring-2 hover:ring-offset-1 transition-all"
                                style={{ backgroundColor: getBusColor(selectedCamper.am_bus_number) }}
                                title="Click to view AM pickup location"
                              >
                                {selectedCamper.am_bus_number} →
                              </button>
                            ) : (
                              <span 
                                className="px-2 py-0.5 rounded text-white text-xs font-medium"
                                style={{ backgroundColor: getBusColor(selectedCamper.am_bus_number) }}
                              >
                                {selectedCamper.am_bus_number}
                              </span>
                            )}
                          </div>
                        )}
                        {/* Only show PM Bus if valid */}
                        {hasValidPmBus && (
                          <div className="flex flex-wrap items-center gap-1">
                            <span className="font-semibold">PM Bus:</span> 
                            {/* Make clickable if viewing AM location and PM entry exists */}
                            {!isPmLocation && hasOtherRouteEntry(selectedCamper, 'PM') ? (
                              <button
                                onClick={() => handleNavigateToOtherStop(selectedCamper, 'PM')}
                                className="px-2 py-0.5 rounded text-white text-xs font-medium cursor-pointer hover:opacity-80 hover:ring-2 hover:ring-offset-1 transition-all"
                                style={{ backgroundColor: getBusColor(selectedCamper.pm_bus_number) }}
                                title="Click to view PM drop-off location"
                              >
                                {selectedCamper.pm_bus_number} →
                              </button>
                            ) : (
                              <span 
                                className="px-2 py-0.5 rounded text-white text-xs font-medium"
                                style={{ backgroundColor: getBusColor(selectedCamper.pm_bus_number) }}
                              >
                                {selectedCamper.pm_bus_number}
                              </span>
                            )}
                          </div>
                        )}
                        {/* Show message if no buses assigned */}
                        {!hasValidAmBus && !hasValidPmBus && (
                          <div className="text-red-600 font-semibold">No bus assigned</div>
                        )}
                        
                        {/* Driver and Counselor Info */}
                        {(hasValidAmBus || hasValidPmBus) && (
                          <div className="mt-2 pt-2 border-t border-gray-200">
                            <div className="flex items-center gap-1">
                              <span className="font-semibold">👤 Driver:</span> 
                              <span>{staffInfo.driver_name || 'TBD'}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="font-semibold">🏫 Counselor:</span> 
                              <span>{staffInfo.counselor_name || 'TBD'}</span>
                            </div>
                          </div>
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
                        
                        {/* Shadow Staff Display (read-only in InfoWindow) */}
                        {(() => {
                          const camperId = selectedCamper._id || `${selectedCamper.last_name}_${selectedCamper.first_name}_${selectedCamper.zip_code}`.replace(' ', '_');
                          const existingShadow = shadows[camperId];
                          if (existingShadow) {
                            return (
                              <div className="mt-3 pt-3 border-t">
                                <div className="flex items-center justify-between bg-purple-50 p-2 rounded">
                                  <div className="text-xs">
                                    <span className="text-gray-500">Shadow: </span>
                                    <span className="font-medium text-purple-700">{existingShadow.shadow_name}</span>
                                  </div>
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()}
                  
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

          {/* User-Defined Bus Zone Polygons */}
          {showBusZones && Object.entries(userZones).map(([busNumber, zone]) => (
            <EditableBusZone
              key={`zone-${busNumber}`}
              busNumber={busNumber}
              points={zone.points}
              color={zone.color || getBusColor(busNumber)}
              isEditing={editingZoneBus === busNumber}
              isSelected={selectedBusFilter === busNumber || selectedZoneBus === busNumber}
              showZone={!selectedBusFilter || selectedBusFilter === busNumber}
              onPointsChange={(newPoints) => {
                setUserZones(prev => ({
                  ...prev,
                  [busNumber]: { ...prev[busNumber], points: newPoints }
                }));
              }}
              onZoneClick={handleZoneClick}
            />
          ))}

          {/* Zone Creator - Active when creating a new zone */}
          {isCreatingZone && creatingZoneBus && (
            <ZoneCreator
              isActive={isCreatingZone}
              points={newZonePoints}
              color={getBusColor(creatingZoneBus)}
              onPointsChange={setNewZonePoints}
            />
          )}
        </Map>

        {/* Zone Control Panel - Shows when zones are enabled */}
        {showBusZones && (
          <div 
            className="absolute bottom-20 right-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 z-10 max-h-80 overflow-y-auto"
            style={{ maxWidth: '240px' }}
          >
            <h4 className="font-semibold text-sm text-gray-700 mb-2 border-b pb-1">Bus Zones</h4>
            
            {/* Zone Creation Mode Indicator */}
            {isCreatingZone && (
              <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-xs">
                <div className="font-semibold text-blue-700 mb-1">Creating Zone for {creatingZoneBus}</div>
                <div className="text-blue-600">Click on map to add points ({newZonePoints.length} points)</div>
                <div className="text-gray-500 text-xs mt-1">
                  • Drag points to adjust position
                  • Right-click to delete a point
                  • Need at least 3 points
                </div>
                {newZonePoints.length >= 3 && (
                  <div className="text-green-600 mt-1 font-medium">Ready to save! Click "Save Zone" to complete.</div>
                )}
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      if (newZonePoints.length >= 3) {
                        saveZone(creatingZoneBus, newZonePoints, true);
                      }
                      setIsCreatingZone(false);
                      setCreatingZoneBus(null);
                      setNewZonePoints([]);
                    }}
                    disabled={newZonePoints.length < 3}
                    className={`flex-1 px-2 py-1 rounded text-xs ${
                      newZonePoints.length >= 3 
                        ? 'bg-green-500 text-white hover:bg-green-600' 
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    Save Zone
                  </button>
                  <button
                    onClick={() => {
                      setIsCreatingZone(false);
                      setCreatingZoneBus(null);
                      setNewZonePoints([]);
                    }}
                    className="flex-1 px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Edit Mode Indicator */}
            {editingZoneBus && (
              <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs">
                <div className="font-semibold text-amber-700 mb-1">Editing Zone for {editingZoneBus}</div>
                <div className="text-amber-600">Drag points to adjust. Right-click to delete point.</div>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      const zone = userZones[editingZoneBus];
                      if (zone && zone.points.length >= 3) {
                        saveZone(editingZoneBus, zone.points, false);
                      }
                      setEditingZoneBus(null);
                    }}
                    className="flex-1 px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
                  >
                    Save Changes
                  </button>
                  <button
                    onClick={() => {
                      fetchUserZones(); // Revert changes
                      setEditingZoneBus(null);
                    }}
                    className="flex-1 px-2 py-1 bg-gray-200 text-gray-600 rounded text-xs hover:bg-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
            
            <div className="space-y-1">
              {uniqueBuses.filter(bus => bus.startsWith('Bus')).slice(0, 25).map((bus) => {
                const busColor = getBusColor(bus);
                const hasZone = !!userZones[bus];
                const isActive = selectedBusFilter === bus || selectedZoneBus === bus;
                const isEditing = editingZoneBus === bus;
                
                return (
                  <div
                    key={bus}
                    className={`flex items-center gap-2 px-1 py-1 rounded transition-colors ${
                      isActive ? 'bg-blue-50' : 'hover:bg-gray-50'
                    } ${isEditing ? 'bg-amber-50' : ''}`}
                  >
                    <div
                      className="w-3 h-3 rounded-sm border border-white shadow-sm flex-shrink-0"
                      style={{ backgroundColor: busColor, opacity: hasZone ? 1 : 0.3 }}
                    />
                    <span className={`text-xs flex-1 ${isActive ? 'font-bold text-blue-700' : 'text-gray-600'}`}>
                      {bus.replace('Bus #', '#')}
                    </span>
                    
                    {/* Zone Actions */}
                    {hasZone ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => setEditingZoneBus(editingZoneBus === bus ? null : bus)}
                          className={`px-1.5 py-0.5 text-xs rounded ${
                            isEditing 
                              ? 'bg-amber-500 text-white' 
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                          title="Edit zone"
                        >
                          ✎
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete zone for ${bus}?`)) {
                              deleteZone(bus);
                            }
                          }}
                          className="px-1.5 py-0.5 text-xs bg-red-100 text-red-600 rounded hover:bg-red-200"
                          title="Delete zone"
                        >
                          ×
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          setIsCreatingZone(true);
                          setCreatingZoneBus(bus);
                          setNewZonePoints([]);
                          setEditingZoneBus(null);
                          toast.info(`Click on the map to draw zone for ${bus}`);
                        }}
                        disabled={isCreatingZone}
                        className={`px-2 py-0.5 text-xs rounded ${
                          isCreatingZone 
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                            : 'bg-blue-100 text-blue-600 hover:bg-blue-200'
                        }`}
                        title="Create zone"
                      >
                        + Zone
                      </button>
                    )}
                  </div>
                );
              })}
              {uniqueBuses.length > 25 && (
                <div className="text-xs text-gray-400 text-center pt-1">
                  +{uniqueBuses.length - 25} more
                </div>
              )}
            </div>
          </div>
        )}

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
                    placeholder="Search camper, address... (Enter to find)"
                    value={searchQuery}
                    onChange={(e) => handleSearchCamper(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleSearchSubmit();
                      }
                    }}
                    className="w-full h-12 pl-10"
                    data-testid="search-camper"
                  />
                  <Search className="absolute left-3 top-3.5 w-5 h-5 text-gray-400" />
                  {searchQuery && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-2 h-8 w-8 p-0"
                      data-testid="clear-search-btn"
                      onClick={() => {
                        setSearchQuery("");
                        setSelectedCamper(null);
                        // Reset map to initial view
                        if (mapInstance) {
                          mapInstance.panTo(INITIAL_MAP_CENTER);
                          mapInstance.setZoom(INITIAL_ZOOM);
                        }
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

                {/* Bus Staff Configuration Dialog */}
                <Dialog open={showStaffConfig} onOpenChange={setShowStaffConfig}>
                  <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="text-xl">Configure Bus Staff</DialogTitle>
                      <DialogDescription>
                        Set driver and counselor names for each bus. Changes will update the seat availability report.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      {/* Bus Selection */}
                      <div className="space-y-2">
                        <Label htmlFor="staff_bus">Select Bus</Label>
                        <Select
                          value={selectedStaffBus}
                          onValueChange={(value) => loadStaffForBus(value)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="-- Select Bus --" />
                          </SelectTrigger>
                          <SelectContent>
                            {Array.from({length: 34}, (_, i) => `Bus #${String(i + 1).padStart(2, '0')}`).map(bus => (
                              <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Driver Name */}
                      <div className="space-y-2">
                        <Label htmlFor="driver_name">Driver Name</Label>
                        <Input
                          id="driver_name"
                          placeholder="Enter driver name"
                          value={staffForm.driver_name}
                          onChange={(e) => setStaffForm({...staffForm, driver_name: e.target.value})}
                        />
                      </div>

                      {/* Counselor Name */}
                      <div className="space-y-2">
                        <Label htmlFor="counselor_name">Counselor Name</Label>
                        <Input
                          id="counselor_name"
                          placeholder="Enter counselor name"
                          value={staffForm.counselor_name}
                          onChange={(e) => setStaffForm({...staffForm, counselor_name: e.target.value})}
                        />
                      </div>

                      {/* Home Address */}
                      <div className="space-y-2">
                        <Label htmlFor="home_address">Driver Home Address</Label>
                        <Input
                          id="home_address"
                          placeholder="123 Main St, City, NY 11518"
                          value={staffForm.home_address}
                          onChange={(e) => setStaffForm({...staffForm, home_address: e.target.value})}
                        />
                        <p className="text-xs text-gray-500">This will be the start/end point for route sheets</p>
                      </div>

                      {/* Location Name */}
                      <div className="space-y-2">
                        <Label htmlFor="location_name">Location/Area Name</Label>
                        <Input
                          id="location_name"
                          placeholder="e.g., Valley Stream, Oceanside"
                          value={staffForm.location_name}
                          onChange={(e) => setStaffForm({...staffForm, location_name: e.target.value})}
                        />
                      </div>

                      {/* Capacity */}
                      <div className="space-y-2">
                        <Label htmlFor="capacity">Bus Capacity</Label>
                        <Input
                          id="capacity"
                          type="number"
                          placeholder="19 or 30"
                          value={staffForm.capacity}
                          onChange={(e) => setStaffForm({...staffForm, capacity: e.target.value})}
                        />
                      </div>

                      {/* Save Button */}
                      <Button 
                        className="w-full bg-green-600 hover:bg-green-700"
                        onClick={handleSaveStaff}
                      >
                        Save Configuration
                      </Button>

                      {/* Configured Buses List */}
                      <div className="border-t pt-4 mt-4">
                        <h3 className="font-semibold mb-3">Configured Buses:</h3>
                        <div className="max-h-60 overflow-y-auto space-y-2">
                          {Object.keys(busStaffList).length === 0 ? (
                            <p className="text-gray-500 text-sm">No buses configured yet.</p>
                          ) : (
                            Object.entries(busStaffList)
                              .sort(([a], [b]) => {
                                const numA = parseInt(a.replace(/\D/g, ''));
                                const numB = parseInt(b.replace(/\D/g, ''));
                                return numA - numB;
                              })
                              .map(([busNum, staff]) => (
                                <div 
                                  key={busNum} 
                                  className="p-3 bg-gray-50 rounded-lg border-l-4 flex justify-between items-start"
                                  style={{ borderLeftColor: BUS_COLORS[busNum] || '#808080' }}
                                >
                                  <div>
                                    <div className="font-bold">{busNum}</div>
                                    <div className="text-sm">👤 Driver: {staff.driver_name || 'TBD'}</div>
                                    <div className="text-sm">🏫 Counselor: {staff.counselor_name || 'TBD'}</div>
                                    {staff.location_name && (
                                      <div className="text-xs text-gray-500">📍 {staff.location_name}</div>
                                    )}
                                  </div>
                                  <div className="flex gap-2">
                                    <Button 
                                      size="sm" 
                                      variant="outline"
                                      className="text-orange-600 border-orange-600"
                                      onClick={() => loadStaffForBus(busNum)}
                                    >
                                      Edit
                                    </Button>
                                    <Button 
                                      size="sm" 
                                      variant="outline"
                                      className="text-red-600 border-red-600"
                                      onClick={() => handleDeleteStaff(busNum)}
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  </div>
                                </div>
                              ))
                          )}
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowStaffConfig(false)}>Close</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                {/* Shadow Staff Dialog */}
                <Dialog open={showShadowDialog} onOpenChange={setShowShadowDialog}>
                  <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="text-xl">Add Shadow Staff</DialogTitle>
                      <DialogDescription>
                        Add a 1:1 shadow staff member for a specific camper. Shadows take a bus seat.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      {/* Shadow Name */}
                      <div className="space-y-2">
                        <Label htmlFor="shadow_name">Shadow Name</Label>
                        <Input
                          id="shadow_name"
                          placeholder="Enter shadow staff name"
                          value={shadowName}
                          onChange={(e) => setShadowName(e.target.value)}
                          data-testid="shadow-name-input"
                        />
                      </div>

                      {/* Bus Selection */}
                      <div className="space-y-2">
                        <Label htmlFor="shadow_bus">Select Bus</Label>
                        <Select
                          value={selectedShadowBus}
                          onValueChange={(value) => {
                            setSelectedShadowBus(value);
                            setSelectedShadowCamper(""); // Reset camper when bus changes
                          }}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="-- Select Bus --" />
                          </SelectTrigger>
                          <SelectContent>
                            {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
                              <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Child Selection (filtered by bus) */}
                      <div className="space-y-2">
                        <Label htmlFor="shadow_camper">Link to Child</Label>
                        <Select
                          value={selectedShadowCamper}
                          onValueChange={setSelectedShadowCamper}
                          disabled={!selectedShadowBus}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder={selectedShadowBus ? "-- Select Child --" : "Select a bus first"} />
                          </SelectTrigger>
                          <SelectContent>
                            {getCampersOnBus(selectedShadowBus).map(camper => {
                              const camperId = camper._id || `${camper.last_name}_${camper.first_name}_${camper.zip_code}`.replace(' ', '_');
                              const hasExistingShadow = shadows[camperId];
                              return (
                                <SelectItem 
                                  key={camperId} 
                                  value={camperId}
                                  disabled={hasExistingShadow}
                                >
                                  {camper.displayName} - {camper.displayDetail}
                                  {hasExistingShadow && " (has shadow)"}
                                </SelectItem>
                              );
                            })}
                          </SelectContent>
                        </Select>
                        {selectedShadowBus && getCampersOnBus(selectedShadowBus).length === 0 && (
                          <p className="text-xs text-gray-500">No campers on this bus</p>
                        )}
                      </div>

                      {/* Save Button */}
                      <Button 
                        className="w-full bg-purple-600 hover:bg-purple-700"
                        onClick={handleSaveShadowDialog}
                        disabled={!shadowName.trim() || !selectedShadowBus || !selectedShadowCamper}
                      >
                        Save Shadow
                      </Button>

                      {/* Existing Shadows List */}
                      <div className="border-t pt-4 mt-4">
                        <h3 className="font-semibold mb-3">Current Shadows ({shadowsList.length}):</h3>
                        <div className="max-h-60 overflow-y-auto space-y-2">
                          {shadowsList.length === 0 ? (
                            <p className="text-gray-500 text-sm">No shadows assigned yet.</p>
                          ) : (
                            shadowsList.map((shadow) => (
                              <div 
                                key={shadow.id}
                                className="flex items-center justify-between p-3 bg-purple-50 rounded-lg"
                              >
                                <div className="flex-1">
                                  <div className="font-medium text-purple-800">{shadow.shadow_name}</div>
                                  <div className="text-xs text-gray-600">
                                    For: {shadow.camper_name} • {shadow.bus_number}
                                  </div>
                                  <div className="text-xs text-gray-500">{shadow.session}</div>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                                  onClick={() => handleDeleteShadow(shadow.id)}
                                  title="Remove shadow"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => {
                        setShowShadowDialog(false);
                        setShadowName("");
                        setSelectedShadowBus("");
                        setSelectedShadowCamper("");
                      }}>Close</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                {/* Multiple Search Results Dialog */}
                <Dialog open={showMultipleResults} onOpenChange={setShowMultipleResults}>
                  <DialogContent className="sm:max-w-[450px] max-h-[80vh]">
                    <DialogHeader>
                      <DialogTitle className="text-lg">{multipleResultsCampers.length} Results Found</DialogTitle>
                      <DialogDescription>
                        Select which camper to view on the map:
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 mt-4 max-h-[50vh] overflow-y-auto">
                      {multipleResultsCampers.map((camper, index) => {
                        const isPm = camper._id && camper._id.endsWith('_PM');
                        const routeType = isPm ? 'PM' : 'AM';
                        const busNumber = isPm ? camper.pm_bus_number : camper.am_bus_number;
                        return (
                          <Button
                            key={camper._id || index}
                            variant="outline"
                            className="w-full h-auto py-3 px-4 justify-start text-left"
                            onClick={() => handleSelectSearchResult(camper)}
                          >
                            <div className="flex flex-col items-start w-full">
                              <div className="font-semibold">
                                {camper.last_name}, {camper.first_name}
                                <span className={`ml-2 px-2 py-0.5 rounded text-xs ${isPm ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'}`}>
                                  {routeType}
                                </span>
                              </div>
                              <div className="text-sm text-gray-600">
                                {camper.town || 'Unknown'} - {busNumber || 'No bus'}
                              </div>
                              <div className="text-xs text-gray-400 truncate w-full">
                                {camper.location?.address || 'No address'}
                              </div>
                            </div>
                          </Button>
                        );
                      })}
                    </div>
                    <DialogFooter className="mt-4">
                      <Button variant="outline" onClick={() => {
                        setShowMultipleResults(false);
                        setMultipleResultsCampers([]);
                      }}>Cancel</Button>
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
                  className="w-full h-12 text-base bg-indigo-50 hover:bg-indigo-100 border-indigo-600 text-indigo-700"
                  onClick={() => setShowStaffConfig(true)}
                  data-testid="configure-staff-btn"
                >
                  <Settings className="w-5 h-5 mr-2" />
                  Configure Bus Staff
                </Button>

                {/* Add Shadow Button */}
                <Button
                  variant="outline"
                  className="w-full h-12 text-base bg-purple-50 hover:bg-purple-100 border-purple-600 text-purple-700"
                  onClick={() => setShowShadowDialog(true)}
                  data-testid="add-shadow-btn"
                >
                  <UserPlus className="w-5 h-5 mr-2" />
                  Add Shadow Staff
                </Button>

                {/* Bus Zones Toggle */}
                <Button
                  variant="outline"
                  className={`w-full h-12 text-base ${
                    showBusZones 
                      ? 'bg-emerald-100 hover:bg-emerald-200 border-emerald-600 text-emerald-700' 
                      : 'bg-slate-50 hover:bg-slate-100 border-slate-400 text-slate-600'
                  }`}
                  onClick={() => {
                    setShowBusZones(!showBusZones);
                    if (!showBusZones) {
                      toast.success("Bus zones panel opened - create or edit zones for each bus");
                    } else {
                      setSelectedZoneBus(null);
                      setIsCreatingZone(false);
                      setEditingZoneBus(null);
                      toast.info("Bus zones hidden");
                    }
                  }}
                  data-testid="toggle-zones-btn"
                >
                  {showBusZones ? (
                    <>
                      <Eye className="w-5 h-5 mr-2" />
                      Hide Bus Zones
                    </>
                  ) : (
                    <>
                      <Layers className="w-5 h-5 mr-2" />
                      Manage Bus Zones
                    </>
                  )}
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
                    onClick={() => {
                      setSelectedBusFilter(null);
                      setSelectedZoneBus(null);
                    }}
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
                    const availability = busSeatAvailability[bus] || {};
                    const isSelected = selectedBusFilter === bus;
                    
                    // Determine color for availability numbers
                    const getAvailColor = (avail) => {
                      if (avail < 0) return 'text-red-600 font-bold';
                      if (avail <= 3) return 'text-orange-500';
                      return 'text-green-600';
                    };
                    
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
                          <div className="flex-1">
                            <div className={`font-medium text-sm md:text-base ${isSelected ? 'text-blue-700 font-bold' : ''}`}>
                              {bus}
                            </div>
                            <div className="text-xs space-y-0.5">
                              {/* Half 1 Row */}
                              <div className="flex gap-1 items-center">
                                <span className="text-gray-500 w-6">H1:</span>
                                <span className="text-gray-400">AM</span>
                                <span className={`w-8 ${getAvailColor(availability.h1AmAvailable)}`}>
                                  {availability.h1AmAvailable ?? '?'}
                                </span>
                                <span className="text-gray-400">PM</span>
                                <span className={`w-8 ${getAvailColor(availability.h1PmAvailable)}`}>
                                  {availability.h1PmAvailable ?? '?'}
                                </span>
                              </div>
                              {/* Half 2 Row */}
                              <div className="flex gap-1 items-center">
                                <span className="text-gray-500 w-6">H2:</span>
                                <span className="text-gray-400">AM</span>
                                <span className={`w-8 ${getAvailColor(availability.h2AmAvailable)}`}>
                                  {availability.h2AmAvailable ?? '?'}
                                </span>
                                <span className="text-gray-400">PM</span>
                                <span className={`w-8 ${getAvailColor(availability.h2PmAvailable)}`}>
                                  {availability.h2PmAvailable ?? '?'}
                                </span>
                              </div>
                              <div className="text-gray-400 text-[10px]">
                                Cap: {availability.capacity ?? '?'}
                              </div>
                            </div>
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
                    <p className="font-bold text-blue-700 text-xl">{sessionFilteredCampers.length}</p>
                    {sessionFilter !== "all" && (
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
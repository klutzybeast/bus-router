import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow, useMap } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, RefreshCw, Menu, X, MapPin, Printer, Filter, Download, Search, UserPlus, FileSpreadsheet, Settings, Trash2, Layers, Eye, EyeOff, Plus, Calendar, Pencil, Users, FileText, Navigation, Radio } from "lucide-react";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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

// Central Stops - fixed locations for bus pickup/dropoff
const CENTRAL_STOPS = [
  { id: 'cs1', name: 'Long Beach Central Stop', address: '410 East Broadway, Long Beach, NY', lat: 40.5844458, lng: -73.6517555 },
  { id: 'cs2', name: 'Bellmore Central Stop', address: '2273 Brody Lane, Bellmore, NY', lat: 40.6504792, lng: -73.5310111 },
  { id: 'cs3', name: 'Merrick Central Stop 1', address: '60 Petit Ave, Merrick, NY', lat: 40.6738188, lng: -73.5601845 },
  { id: 'cs4', name: 'Merrick Central Stop 2', address: '15 Fisher Ave, Merrick, NY', lat: 40.6639238, lng: -73.5531009 },
];

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
  
  // Ref to keep focus on search input
  const searchInputRef = useRef(null);
  
  // Season Management State
  const [seasons, setSeasons] = useState([]);
  const [activeSeason, setActiveSeason] = useState(null);
  const [showNewSeasonDialog, setShowNewSeasonDialog] = useState(false);
  const [newSeasonYear, setNewSeasonYear] = useState(new Date().getFullYear() + 1);
  const [copyFromSeason, setCopyFromSeason] = useState("");
  
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
  
  // Pickup/Dropoff state for camper card
  const [selectedPickupDropoff, setSelectedPickupDropoff] = useState("");
  
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

  // Central Stops State
  const [showCentralStops, setShowCentralStops] = useState(true);
  const [selectedCentralStop, setSelectedCentralStop] = useState(null);

  // Bus Info State (capacities)
  const [busInfoMap, setBusInfoMap] = useState({});

  // Seat availability from backend (accurate counts including campers without addresses)
  const [busSeatAvailability, setBusSeatAvailability] = useState({});

  // GPS Bus Tracking State
  const [trackingBus, setTrackingBus] = useState(null);
  const [trackingData, setTrackingData] = useState(null);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingStops, setTrackingStops] = useState([]); // Stops for tracked bus
  const [nearestStop, setNearestStop] = useState(null); // Current nearest stop
  const trackingIntervalRef = useRef(null);

  // Fetch seasons
  const fetchSeasons = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/seasons`);
      setSeasons(response.data.seasons || []);
    } catch (error) {
      console.error("Error fetching seasons:", error);
    }
  }, []);

  // Fetch active season
  const fetchActiveSeason = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/seasons/active`);
      setActiveSeason(response.data.season);
      return response.data.season;
    } catch (error) {
      console.error("Error fetching active season:", error);
      return null;
    }
  }, []);

  // Switch to a different season
  const handleSeasonChange = async (seasonId) => {
    try {
      toast.loading("Switching season...");
      await axios.put(`${API}/seasons/${seasonId}/activate`);
      toast.dismiss();
      const newSeason = await fetchActiveSeason();
      await fetchSeasons();
      // Reload campers for new season
      await fetchCampers();
      await fetchShadows();
      await fetchUserZones();
      await fetchBusStaff();
      toast.success(`Switched to ${newSeason?.name || 'new season'}`);
    } catch (error) {
      toast.dismiss();
      toast.error("Failed to switch season");
    }
  };

  // Create new season
  const handleCreateSeason = async () => {
    try {
      toast.loading("Creating new season...");
      const seasonName = `${newSeasonYear} Bus Route Management`;
      await axios.post(`${API}/seasons`, {
        name: seasonName,
        year: newSeasonYear,
        copy_from_season_id: copyFromSeason || null
      });
      toast.dismiss();
      toast.success(`Season '${seasonName}' created!`);
      setShowNewSeasonDialog(false);
      setNewSeasonYear(new Date().getFullYear() + 1);
      setCopyFromSeason("");
      await fetchActiveSeason();
      await fetchSeasons();
      await fetchCampers();
      await fetchShadows();
      await fetchUserZones();
      await fetchBusStaff();
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || "Failed to create season");
    }
  };

  // Shadow staff state
  const [shadows, setShadows] = useState({}); // { camper_id: shadow_info }
  const [shadowsList, setShadowsList] = useState([]); // Array of all shadows
  const [showShadowDialog, setShowShadowDialog] = useState(false);
  const [shadowName, setShadowName] = useState("");
  const [selectedShadowBus, setSelectedShadowBus] = useState("");
  const [selectedShadowCamper, setSelectedShadowCamper] = useState("");

  // Assigned Staff State (staff who ride the bus and take a seat)
  const [assignedStaffList, setAssignedStaffList] = useState([]);
  const [showAssignedStaffDialog, setShowAssignedStaffDialog] = useState(false);
  const [assignedStaffName, setAssignedStaffName] = useState("");
  const [assignedStaffBus, setAssignedStaffBus] = useState("");

  // Staff Zone Lookup State (staff with addresses)
  const [staffWithAddresses, setStaffWithAddresses] = useState([]);

  // Fetch staff with addresses
  const fetchStaffWithAddresses = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/staff-addresses`);
      setStaffWithAddresses(response.data.staff || []);
    } catch (error) {
      console.error("Error fetching staff with addresses:", error);
    }
  }, []);

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

  // Fetch assigned staff from backend
  const fetchAssignedStaff = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/bus-assigned-staff`);
      setAssignedStaffList(response.data.assigned_staff || []);
    } catch (error) {
      console.error("Error fetching assigned staff:", error);
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

  // Save assigned staff to a bus
  const handleSaveAssignedStaff = async () => {
    if (!assignedStaffName.trim() || !assignedStaffBus) {
      toast.error("Please enter staff name and select a bus");
      return;
    }
    
    try {
      toast.loading("Adding staff to bus...");
      await axios.post(`${API}/bus-assigned-staff`, {
        staff_name: assignedStaffName.trim(),
        bus_number: assignedStaffBus,
        session: "Full Season- 5 Days"
      });
      toast.dismiss();
      toast.success(`${assignedStaffName} added to ${assignedStaffBus}`);
      setShowAssignedStaffDialog(false);
      setAssignedStaffName("");
      setAssignedStaffBus("");
      await fetchAssignedStaff();
      await fetchSeatAvailability(); // Update seat counts
    } catch (error) {
      toast.dismiss();
      toast.error(error.response?.data?.detail || "Failed to add staff");
    }
  };

  // Delete assigned staff
  const handleDeleteAssignedStaff = async (staffId) => {
    try {
      toast.loading("Removing staff...");
      await axios.delete(`${API}/bus-assigned-staff/${staffId}`);
      toast.dismiss();
      toast.success("Staff removed from bus");
      await fetchAssignedStaff();
      await fetchSeatAvailability(); // Update seat counts
    } catch (error) {
      toast.dismiss();
      toast.error("Failed to remove staff");
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
      // Properly encode the bus number for the URL (e.g., "Bus #01" -> "Bus%20%2301")
      const encodedBusNumber = encodeURIComponent(busNumber);
      await axios.delete(`${BACKEND_URL}/api/bus-zones/${encodedBusNumber}`);
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
    // Initialize seasons first
    fetchActiveSeason();
    fetchSeasons();
    
    fetchCampers();
    fetchBusStaff();
    fetchBusInfo();
    fetchSeatAvailability();
    fetchUserZones(); // Fetch user-defined zones
    fetchShadows(); // Fetch shadow staff
    fetchAssignedStaff(); // Fetch assigned staff (staff who ride the bus)
    fetchStaffWithAddresses(); // Fetch staff with addresses (zone lookup)
    
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
  }, [fetchCampers, fetchBusInfo, fetchSeatAvailability, fetchUserZones, fetchStaffWithAddresses]);

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

  // State for address search results
  const [addressSearchResult, setAddressSearchResult] = useState(null);
  const [showAddressResult, setShowAddressResult] = useState(false);

  const handleSearchSubmit = async () => {
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
        // Keep focus on search input so user can continue typing
        setTimeout(() => searchInputRef.current?.focus(), 100);
      }
    } else if (searchQuery.trim()) {
      // No camper matches - try searching as an address
      toast.loading("Searching address...");
      try {
        const response = await axios.get(`${API}/search-address`, {
          params: { address: searchQuery }
        });
        toast.dismiss();
        
        if (response.data.status === "success") {
          const { location, address, servicing_buses, nearby_buses } = response.data;
          
          // Center map on the address
          if (mapInstance) {
            mapInstance.panTo({ lat: location.lat, lng: location.lng });
            mapInstance.setZoom(16);
          }
          
          // Store result for display
          setAddressSearchResult({
            address,
            location,
            servicing_buses: servicing_buses || [],
            nearby_buses: nearby_buses || []
          });
          setShowAddressResult(true);
          
          // Show info
          const busInfo = nearby_buses.length > 0 
            ? `Nearby buses: ${nearby_buses.join(", ")}`
            : "No buses currently service this exact area";
          toast.success(`Found: ${address}\n${busInfo}`, { duration: 5000 });
        }
      } catch (error) {
        toast.dismiss();
        if (error.response?.status === 404) {
          toast.error("Address not found. Try a more specific address.");
        } else {
          toast.error("No campers or addresses found matching your search");
        }
      }
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
      // Keep focus on search input so user can continue typing
      setTimeout(() => searchInputRef.current?.focus(), 100);
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

  const handleEditRoute = (busNumber) => {
    const encodedBusNumber = encodeURIComponent(busNumber);
    window.open(`${API}/route-sheet/${encodedBusNumber}/print?edit=true`, '_blank');
  };

  // GPS Bus Tracking Functions
  const handleTrackBus = async (busNumber) => {
    setTrackingBus(busNumber);
    setTrackingLoading(true);
    setTrackingData(null);
    setNearestStop(null);
    
    // Fetch stops for this bus (campers with their locations)
    const busStops = getBusStops(busNumber);
    setTrackingStops(busStops);
    
    // Fetch initial location
    await fetchBusLocation(busNumber, busStops);
    
    // Set up polling every 5 seconds for smoother tracking
    if (trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current);
    }
    trackingIntervalRef.current = setInterval(() => {
      fetchBusLocation(busNumber, busStops);
    }, 5000);
  };

  // Get stops (grouped campers by location) for a bus
  const getBusStops = (busNumber) => {
    const busCampers = campers.filter(c => 
      c.am_bus_number === busNumber || c.pm_bus_number === busNumber
    );
    
    // Group campers by location (stop)
    const stopMap = {};
    busCampers.forEach(camper => {
      if (camper.location?.lat && camper.location?.lng) {
        // Round to 5 decimal places to group nearby addresses
        const key = `${camper.location.lat.toFixed(5)}_${camper.location.lng.toFixed(5)}`;
        if (!stopMap[key]) {
          stopMap[key] = {
            lat: camper.location.lat,
            lng: camper.location.lng,
            address: camper.location.address || 'Unknown',
            campers: []
          };
        }
        stopMap[key].campers.push({
          id: camper._id,
          name: `${camper.first_name} ${camper.last_name}`,
          first_name: camper.first_name,
          last_name: camper.last_name
        });
      }
    });
    
    return Object.values(stopMap);
  };

  // Calculate distance between two points in meters
  const getDistanceMeters = (lat1, lng1, lat2, lng2) => {
    const R = 6371000; // Earth's radius in meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
  };

  // Find nearest stop to current bus location
  const findNearestStop = (busLat, busLng, stops) => {
    if (!stops || stops.length === 0) return null;
    
    let nearest = null;
    let minDistance = Infinity;
    
    stops.forEach(stop => {
      const distance = getDistanceMeters(busLat, busLng, stop.lat, stop.lng);
      if (distance < minDistance) {
        minDistance = distance;
        nearest = { ...stop, distance };
      }
    });
    
    // Only return if within 100 meters of a stop
    return minDistance <= 100 ? nearest : null;
  };

  const fetchBusLocation = async (busNumber, stops) => {
    try {
      const response = await axios.get(`${API}/bus-tracking/location/${encodeURIComponent(busNumber)}`);
      setTrackingData(response.data);
      
      // Check if bus is near a stop
      if (response.data.success && response.data.latitude && response.data.longitude) {
        const nearest = findNearestStop(response.data.latitude, response.data.longitude, stops || trackingStops);
        setNearestStop(nearest);
      }
    } catch (error) {
      console.error("Error fetching bus location:", error);
      setTrackingData({ success: false, message: "Failed to fetch location" });
    } finally {
      setTrackingLoading(false);
    }
  };

  const closeTracking = () => {
    if (trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current);
      trackingIntervalRef.current = null;
    }
    setTrackingBus(null);
    setTrackingData(null);
    setTrackingStops([]);
    setNearestStop(null);
  };

  // Cleanup tracking interval on unmount
  useEffect(() => {
    return () => {
      if (trackingIntervalRef.current) {
        clearInterval(trackingIntervalRef.current);
      }
    };
  }, []);

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

  // Handler for saving pickup/dropoff status
  const handleSavePickupDropoff = async (camperId) => {
    if (!selectedPickupDropoff) {
      toast.error("Please select a pickup/dropoff option");
      return;
    }
    
    try {
      toast.loading("Saving pickup/dropoff...");
      
      await axios.post(`${API}/campers/${camperId}/pickup-dropoff`, {
        pickup_dropoff: selectedPickupDropoff
      });
      
      toast.dismiss();
      
      // Handle CLEAR case
      const newStatus = selectedPickupDropoff === "CLEAR" ? "" : selectedPickupDropoff;
      toast.success(selectedPickupDropoff === "CLEAR" ? "Status cleared" : `Saved: ${selectedPickupDropoff}`);
      
      // Update the selected camper locally
      if (selectedCamper) {
        const updatedCamper = {
          ...selectedCamper,
          pickup_dropoff: newStatus
        };
        setSelectedCamper(updatedCamper);
        
        // Update in campers array
        setCampers(prevCampers => 
          prevCampers.map(c => 
            c._id === camperId ? updatedCamper : c
          )
        );
      }
      
      setSelectedPickupDropoff("");
    } catch (error) {
      toast.dismiss();
      console.error("Error saving pickup/dropoff:", error);
      toast.error("Failed to save pickup/dropoff");
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

          {/* Central Stops - Gray circles with CS label */}
          {showCentralStops && CENTRAL_STOPS.map((stop) => (
            <AdvancedMarker
              key={stop.id}
              position={{ lat: stop.lat, lng: stop.lng }}
              onClick={() => setSelectedCentralStop(stop)}
            >
              <div 
                className="w-12 h-12 rounded-full flex items-center justify-center text-gray-700 font-bold text-sm shadow-lg border-3 border-gray-500 cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                style={{ 
                  backgroundColor: 'rgba(156, 163, 175, 0.7)', 
                  borderWidth: '3px',
                  borderColor: '#6B7280'
                }}
                data-testid={`central-stop-${stop.id}`}
              >
                CS
              </div>
            </AdvancedMarker>
          ))}

          {/* Central Stop InfoWindow */}
          {selectedCentralStop && (
            <InfoWindow
              position={{ lat: selectedCentralStop.lat, lng: selectedCentralStop.lng }}
              onCloseClick={() => setSelectedCentralStop(null)}
              options={{ maxWidth: 280 }}
            >
              <div className="p-2" data-testid="central-stop-info-window">
                <h3 className="font-bold text-base mb-2 text-gray-800">
                  🚌 Central Stop
                </h3>
                <div className="space-y-1 text-sm text-gray-600">
                  <p><strong>Address:</strong> {selectedCentralStop.address}</p>
                </div>
              </div>
            </InfoWindow>
          )}

          {/* Staff with Addresses - Triangle markers */}
          {staffWithAddresses.filter(s => s.bus_number && s.lat && s.lng).map((staff) => {
            const busColor = getBusColor(staff.bus_number);
            const displayText = staff.bus_number.replace('Bus #', '');
            
            return (
              <AdvancedMarker
                key={`staff-${staff.id}`}
                position={{ lat: staff.lat, lng: staff.lng }}
                onClick={() => setSelectedCamper({
                  ...staff,
                  first_name: staff.name.split(' ')[0] || staff.name,
                  last_name: staff.name.split(' ').slice(1).join(' ') || '',
                  isStaff: true,
                  am_bus_number: staff.bus_number,
                  pm_bus_number: staff.bus_number,
                  session: staff.session || 'Full Season- 5 Days',
                  location: { latitude: staff.lat, longitude: staff.lng, address: staff.address }
                })}
              >
                {/* Staff Triangle with black outline */}
                <div 
                  className="relative cursor-pointer hover:scale-110 active:scale-95 transition-transform"
                  style={{ width: '40px', height: '40px' }}
                  data-testid={`staff-triangle-${staff.id}`}
                  title={`${staff.name} - ${staff.bus_number}`}
                >
                  {/* Black outline triangle */}
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '40px',
                      height: '40px',
                      backgroundColor: '#000000',
                      clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)',
                    }}
                  />
                  {/* Inner colored triangle */}
                  <div
                    className="flex items-center justify-center text-white font-bold text-xs"
                    style={{
                      position: 'absolute',
                      top: '3px',
                      left: '3px',
                      width: '34px',
                      height: '34px',
                      backgroundColor: busColor,
                      clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)',
                    }}
                  >
                    <span style={{ marginTop: '10px' }}>{displayText}</span>
                  </div>
                </div>
              </AdvancedMarker>
            );
          })}

          {/* Address Search Result Marker */}
          {addressSearchResult && showAddressResult && (
            <>
              <AdvancedMarker
                position={{ lat: addressSearchResult.location.lat, lng: addressSearchResult.location.lng }}
                onClick={() => setShowAddressResult(true)}
              >
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg shadow-lg border-3 cursor-pointer hover:scale-110 transition-transform"
                  style={{ 
                    backgroundColor: '#dc2626', 
                    borderWidth: '3px',
                    borderColor: '#fff'
                  }}
                  data-testid="address-search-marker"
                >
                  📍
                </div>
              </AdvancedMarker>
              <InfoWindow
                position={{ lat: addressSearchResult.location.lat, lng: addressSearchResult.location.lng }}
                onCloseClick={() => {
                  setShowAddressResult(false);
                  setAddressSearchResult(null);
                }}
                options={{ maxWidth: 320 }}
              >
                <div className="p-2" data-testid="address-search-info-window">
                  <h3 className="font-bold text-base mb-2 text-gray-800">
                    📍 Address Search Result
                  </h3>
                  <div className="space-y-2 text-sm text-gray-600">
                    <p><strong>Address:</strong> {addressSearchResult.address}</p>
                    
                    {addressSearchResult.servicing_buses.length > 0 && (
                      <div>
                        <strong className="text-green-700">🚌 Buses in Zone:</strong>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {addressSearchResult.servicing_buses.map((bus, idx) => (
                            <span key={idx} className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                              {bus.bus_number}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {addressSearchResult.nearby_buses.length > 0 && (
                      <div>
                        <strong className="text-blue-700">🚌 Nearby Buses:</strong>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {addressSearchResult.nearby_buses.map((bus, idx) => (
                            <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                              {bus}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {addressSearchResult.servicing_buses.length === 0 && addressSearchResult.nearby_buses.length === 0 && (
                      <p className="text-orange-600 italic">No buses currently service this exact area</p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 w-full"
                    onClick={() => {
                      setShowAddressResult(false);
                      setAddressSearchResult(null);
                    }}
                  >
                    Clear Search
                  </Button>
                </div>
              </InfoWindow>
            </>
          )}

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
                        
                        {/* Early Pickup / Late Dropoff Selection */}
                        <div className="mt-3 pt-3 border-t">
                          <div className="text-xs font-semibold mb-2">Pickup/Dropoff:</div>
                          <div className="flex gap-2 items-center">
                            <Select 
                              value={selectedPickupDropoff || selectedCamper.pickup_dropoff || ""} 
                              onValueChange={setSelectedPickupDropoff}
                            >
                              <SelectTrigger className="flex-1 h-8 text-xs">
                                <SelectValue placeholder="Select option" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="Early Pickup">Early Pickup</SelectItem>
                                <SelectItem value="Late Drop Off">Late Drop Off</SelectItem>
                                <SelectItem value="Early Pickup and Late Drop Off">Early Pickup and Late Drop Off</SelectItem>
                                {selectedCamper.pickup_dropoff && (
                                  <SelectItem value="CLEAR" className="text-red-600">Clear Status</SelectItem>
                                )}
                              </SelectContent>
                            </Select>
                            <Button
                              size="sm"
                              className="h-8 text-xs bg-green-600 hover:bg-green-700"
                              onClick={() => handleSavePickupDropoff(selectedCamper._id || `${selectedCamper.last_name}_${selectedCamper.first_name}_${selectedCamper.zip_code}`.replace(' ', '_'))}
                              disabled={!selectedPickupDropoff && !selectedCamper.pickup_dropoff}
                            >
                              Save
                            </Button>
                          </div>
                          {selectedCamper.pickup_dropoff && (
                            <div className="mt-1 text-xs text-green-600">
                              Current: {selectedCamper.pickup_dropoff}
                            </div>
                          )}
                        </div>
                        
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
                                <SelectContent className="max-h-60 overflow-y-auto">
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
                                <SelectContent className="max-h-60 overflow-y-auto">
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
            
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {uniqueBuses.filter(bus => bus.startsWith('Bus')).map((bus) => {
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
                <div className="flex items-center gap-3">
                  <img 
                    src="https://customer-assets.emergentagent.com/job_bustrek/artifacts/14j72p2r_rr%20logo.png" 
                    alt="Rolling River Day Camp" 
                    className="w-10 h-10 rounded-lg shadow-md"
                  />
                  <div>
                    <h2 className="text-xl md:text-2xl font-bold">Camp Bus Routing</h2>
                    <p className="text-sm text-blue-100 mt-0.5">33 Bus Routes</p>
                  </div>
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
              
              {/* Season Selector */}
              <div className="mt-3 flex items-center gap-2">
                <Select
                  value={activeSeason?.id || ""}
                  onValueChange={handleSeasonChange}
                >
                  <SelectTrigger className="flex-1 h-9 bg-blue-500/30 border-blue-400/50 text-white text-sm">
                    <SelectValue placeholder="Select Season">
                      {activeSeason?.name || "Loading..."}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {seasons.map(season => (
                      <SelectItem key={season.id} value={season.id}>
                        {season.name} ({season.camper_count} campers)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-9 px-2 text-white hover:bg-blue-500/30"
                  onClick={() => setShowNewSeasonDialog(true)}
                  title="Create New Season"
                >
                  <Plus className="w-4 h-4" />
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
                    ref={searchInputRef}
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

                {/* Assigned Staff Dialog */}
                <Dialog open={showAssignedStaffDialog} onOpenChange={setShowAssignedStaffDialog}>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle className="text-xl">Add Staff to Bus</DialogTitle>
                      <DialogDescription>
                        Add a staff member who will ride on the bus and take a seat.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      {/* Staff Name */}
                      <div className="space-y-2">
                        <Label htmlFor="assigned_staff_name">Staff Name</Label>
                        <Input
                          id="assigned_staff_name"
                          placeholder="Enter staff name"
                          value={assignedStaffName}
                          onChange={(e) => setAssignedStaffName(e.target.value)}
                          data-testid="assigned-staff-name-input"
                        />
                      </div>

                      {/* Bus Selection */}
                      <div className="space-y-2">
                        <Label htmlFor="assigned_staff_bus">Select Bus</Label>
                        <Select
                          value={assignedStaffBus}
                          onValueChange={setAssignedStaffBus}
                        >
                          <SelectTrigger data-testid="assigned-staff-bus-select">
                            <SelectValue placeholder="-- Select Bus --" />
                          </SelectTrigger>
                          <SelectContent>
                            {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
                              <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Add Button */}
                      <Button
                        className="w-full"
                        onClick={handleSaveAssignedStaff}
                        disabled={!assignedStaffName.trim() || !assignedStaffBus}
                        data-testid="save-assigned-staff-btn"
                      >
                        <UserPlus className="w-4 h-4 mr-2" />
                        Add Staff to Bus
                      </Button>

                      {/* Current Assigned Staff List */}
                      <div className="border-t pt-4 mt-4">
                        <h4 className="font-medium text-sm text-gray-700 mb-2">
                          Current Assigned Staff ({assignedStaffList.length})
                        </h4>
                        <div className="space-y-2 max-h-[200px] overflow-y-auto">
                          {assignedStaffList.length === 0 ? (
                            <p className="text-sm text-gray-500 italic">No staff assigned to buses yet</p>
                          ) : (
                            assignedStaffList.map(staff => (
                              <div 
                                key={staff.id} 
                                className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm"
                              >
                                <div>
                                  <span className="font-medium">{staff.staff_name}</span>
                                  <span className="text-gray-500 ml-2">on {staff.bus_number}</span>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-red-500 hover:text-red-700 hover:bg-red-50 h-6 w-6 p-0"
                                  onClick={() => handleDeleteAssignedStaff(staff.id)}
                                  data-testid={`delete-assigned-staff-${staff.id}`}
                                >
                                  <Trash2 className="w-3 h-3" />
                                </Button>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => {
                        setShowAssignedStaffDialog(false);
                        setAssignedStaffName("");
                        setAssignedStaffBus("");
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

                {/* New Season Dialog */}
                <Dialog open={showNewSeasonDialog} onOpenChange={setShowNewSeasonDialog}>
                  <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2">
                        <Calendar className="w-5 h-5" />
                        Create New Season
                      </DialogTitle>
                      <DialogDescription>
                        Start a new season for bus route management. Optionally copy data from a previous season.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="season_year">Season Year</Label>
                        <Input
                          id="season_year"
                          type="number"
                          value={newSeasonYear}
                          onChange={(e) => setNewSeasonYear(parseInt(e.target.value) || new Date().getFullYear())}
                          min={2020}
                          max={2050}
                        />
                        <p className="text-xs text-gray-500">Season will be named "{newSeasonYear} Bus Route Management"</p>
                      </div>
                      
                      <div className="space-y-2">
                        <Label htmlFor="copy_from">Copy Data From (Optional)</Label>
                        <Select
                          value={copyFromSeason || "none"}
                          onValueChange={(val) => setCopyFromSeason(val === "none" ? "" : val)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Start fresh (no copy)" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Start fresh (no copy)</SelectItem>
                            {seasons.map(season => (
                              <SelectItem key={season.id} value={season.id}>
                                {season.name} ({season.camper_count} campers)
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-gray-500">Copy campers, shadows, bus zones, and staff from a previous season</p>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowNewSeasonDialog(false)}>Cancel</Button>
                      <Button onClick={handleCreateSeason} className="bg-blue-600 hover:bg-blue-700">
                        Create Season
                      </Button>
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

                {/* Add Staff to Bus Button */}
                <Button
                  variant="outline"
                  className="w-full h-12 text-base bg-teal-50 hover:bg-teal-100 border-teal-600 text-teal-700"
                  onClick={() => setShowAssignedStaffDialog(true)}
                  data-testid="add-staff-to-bus-btn"
                >
                  <UserPlus className="w-5 h-5 mr-2" />
                  Add Staff to Bus ({assignedStaffList.length})
                </Button>

                {/* Staff Zone Lookup Button - Opens in new tab */}
                <Button
                  variant="outline"
                  className="w-full h-12 text-base bg-indigo-50 hover:bg-indigo-100 border-indigo-600 text-indigo-700"
                  onClick={() => window.open('/staff-lookup', '_blank')}
                  data-testid="staff-zone-lookup-btn"
                >
                  <Users className="w-5 h-5 mr-2" />
                  Staff Zone Lookup ({staffWithAddresses.filter(s => s.bus_number).length}/{staffWithAddresses.length})
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

                {/* Central Stops Toggle */}
                <Button
                  variant="outline"
                  className={`w-full h-12 text-base ${
                    showCentralStops 
                      ? 'bg-gray-200 hover:bg-gray-300 border-gray-600 text-gray-700' 
                      : 'bg-slate-50 hover:bg-slate-100 border-slate-400 text-slate-600'
                  }`}
                  onClick={() => {
                    setShowCentralStops(!showCentralStops);
                    toast.info(showCentralStops ? "Central stops hidden" : "Central stops shown");
                  }}
                  data-testid="toggle-central-stops-btn"
                >
                  {showCentralStops ? (
                    <>
                      <Eye className="w-5 h-5 mr-2" />
                      Hide Central Stops
                    </>
                  ) : (
                    <>
                      <MapPin className="w-5 h-5 mr-2" />
                      Show Central Stops
                    </>
                  )}
                </Button>
                
                {/* Print Roster Button with Dropdown */}
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full h-12 text-base bg-purple-50 hover:bg-purple-100 border-purple-600 text-purple-700"
                      data-testid="print-roster-btn"
                    >
                      <FileText className="w-5 h-5 mr-2" />
                      Print Roster
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-64 p-2" align="start">
                    <div className="space-y-1">
                      <div className="text-sm font-semibold mb-2 px-2">Select Bus to Print</div>
                      <Button
                        variant="ghost"
                        className="w-full justify-start text-sm h-9"
                        onClick={() => window.open(`${BACKEND_URL}/api/full-roster/print?bus=all`, '_blank')}
                      >
                        <FileText className="w-4 h-4 mr-2" />
                        All Buses
                      </Button>
                      <div className="max-h-60 overflow-y-auto">
                        {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
                          <Button
                            key={bus}
                            variant="ghost"
                            className="w-full justify-start text-sm h-9"
                            onClick={() => window.open(`${BACKEND_URL}/api/full-roster/print?bus=${encodeURIComponent(bus)}`, '_blank')}
                          >
                            <div 
                              className="w-3 h-3 rounded-full mr-2"
                              style={{ backgroundColor: getBusColor(bus) }}
                            />
                            {bus}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
                
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
                          className="h-8 w-8 p-0 flex-shrink-0 text-blue-600 hover:text-blue-800 hover:bg-blue-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditRoute(bus);
                          }}
                          title="Edit Route Order"
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 flex-shrink-0 text-green-600 hover:text-green-800 hover:bg-green-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTrackBus(bus);
                          }}
                          title="Track Bus Location"
                        >
                          <Navigation className="w-4 h-4" />
                        </Button>
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

        {/* GPS Bus Tracking Dialog */}
        <Dialog open={trackingBus !== null} onOpenChange={(open) => !open && closeTracking()}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Navigation className="w-5 h-5 text-green-600" />
                Live Tracking: {trackingBus}
              </DialogTitle>
              <DialogDescription>
                Real-time GPS location from the counselor's phone
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              {trackingLoading ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                  <span className="ml-2">Loading location...</span>
                </div>
              ) : trackingData?.success ? (
                <div className="space-y-4">
                  {/* Status Banner */}
                  <div className={`p-3 rounded-lg flex items-center gap-2 ${
                    trackingData.tracking_active 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    <Radio className={`w-4 h-4 ${trackingData.tracking_active ? 'animate-pulse' : ''}`} />
                    <span className="font-medium">
                      {trackingData.tracking_active 
                        ? 'GPS Active - Tracking in real-time' 
                        : 'GPS Inactive - Last known location'}
                    </span>
                  </div>

                  {/* Map showing bus location - Auto-follows */}
                  <div className="h-64 rounded-lg overflow-hidden border">
                    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
                      <Map
                        zoom={16}
                        center={{ lat: trackingData.latitude, lng: trackingData.longitude }}
                        mapId="bus-tracking-map"
                        gestureHandling="cooperative"
                        disableDefaultUI={true}
                      >
                        <AdvancedMarker
                          position={{ lat: trackingData.latitude, lng: trackingData.longitude }}
                        >
                          <div className="relative">
                            <div className="w-12 h-12 bg-green-500 rounded-full border-4 border-white shadow-lg flex items-center justify-center animate-pulse">
                              <span className="text-white font-bold text-sm">
                                {trackingBus?.replace('Bus #', '')}
                              </span>
                            </div>
                            {trackingData.heading && (
                              <div 
                                className="absolute -top-2 left-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent border-b-green-600"
                                style={{ transform: `translateX(-50%) rotate(${trackingData.heading}deg)`, transformOrigin: 'center bottom' }}
                              />
                            )}
                          </div>
                        </AdvancedMarker>
                      </Map>
                    </APIProvider>
                  </div>

                  {/* Current Stop Info - Shows when bus is near a stop */}
                  {nearestStop ? (
                    <div className="bg-blue-50 border-2 border-blue-300 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <MapPin className="w-5 h-5 text-blue-600" />
                        <span className="font-semibold text-blue-800">At Stop: {nearestStop.address}</span>
                        <span className="text-xs text-blue-500 ml-auto">{Math.round(nearestStop.distance)}m away</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {nearestStop.campers.map((camper, idx) => (
                          <div 
                            key={idx}
                            className="flex items-center gap-1 bg-white border-2 border-blue-400 rounded-full px-3 py-1 shadow-sm"
                            style={{ borderColor: BUS_COLORS[trackingBus] || '#3b82f6' }}
                          >
                            <div 
                              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
                              style={{ backgroundColor: BUS_COLORS[trackingBus] || '#3b82f6' }}
                            >
                              {camper.first_name?.[0]}{camper.last_name?.[0]}
                            </div>
                            <span className="text-sm font-medium text-gray-700">{camper.name}</span>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-blue-600 mt-2">
                        {nearestStop.campers.length} camper{nearestStop.campers.length !== 1 ? 's' : ''} at this stop
                      </p>
                    </div>
                  ) : (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center text-gray-500 text-sm">
                      <MapPin className="w-4 h-4 inline mr-1" />
                      Bus is in transit - not at a stop
                    </div>
                  )}

                  {/* Location Details */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Latitude:</span>
                      <span className="ml-2 font-mono">{trackingData.latitude?.toFixed(6)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Longitude:</span>
                      <span className="ml-2 font-mono">{trackingData.longitude?.toFixed(6)}</span>
                    </div>
                    {trackingData.speed !== null && trackingData.speed !== undefined && (
                      <div>
                        <span className="text-gray-500">Speed:</span>
                        <span className="ml-2">{(trackingData.speed * 2.237).toFixed(1)} mph</span>
                      </div>
                    )}
                    {trackingData.accuracy && (
                      <div>
                        <span className="text-gray-500">Accuracy:</span>
                        <span className="ml-2">±{trackingData.accuracy?.toFixed(0)}m</span>
                      </div>
                    )}
                  </div>

                  {/* Last Update */}
                  <div className="text-center text-sm text-gray-500 border-t pt-3">
                    Last updated: {trackingData.updated_at 
                      ? new Date(trackingData.updated_at).toLocaleTimeString() 
                      : 'Unknown'}
                    <span className="ml-2 text-xs">(Auto-follows every 5s)</span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Navigation className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500 font-medium">No location data available</p>
                  <p className="text-sm text-gray-400 mt-1">
                    The counselor app must be open and GPS enabled on the bus
                  </p>
                  <p className="text-xs text-blue-500 mt-3">
                    Counselor app URL: <code className="bg-gray-100 px-2 py-1 rounded">/counselor</code>
                  </p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={closeTracking}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

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
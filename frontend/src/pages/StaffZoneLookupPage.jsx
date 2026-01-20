import React, { useState, useEffect, useCallback, useRef } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow, useMap } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast, Toaster } from "sonner";
import { Upload, UserPlus, Trash2, Users, MapPin } from "lucide-react";

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

// Component to render a single bus zone polygon
/* global google */
const ZonePolygon = ({ busNumber, points, color }) => {
  const map = useMap();
  const polygonRef = useRef(null);

  useEffect(() => {
    if (!map || !points || points.length < 3) return;

    const polygon = new google.maps.Polygon({
      paths: points.map(p => ({ lat: p.lat, lng: p.lng })),
      strokeColor: color,
      strokeOpacity: 0.8,
      strokeWeight: 2,
      fillColor: color,
      fillOpacity: 0.25,
      map: map,
      clickable: false,
    });

    polygonRef.current = polygon;

    return () => {
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
      }
    };
  }, [map, points, color]);

  return null;
};

const StaffZoneLookupPage = () => {
  const [staffList, setStaffList] = useState([]);
  const [busZones, setBusZones] = useState({});
  const [uniqueBuses, setUniqueBuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStaff, setSelectedStaff] = useState(null);
  
  // Add staff form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newStaffName, setNewStaffName] = useState("");
  const [newStaffAddress, setNewStaffAddress] = useState("");
  const [addingStaff, setAddingStaff] = useState(false);
  
  // CSV upload
  const fileInputRef = useRef(null);
  const [uploadingCSV, setUploadingCSV] = useState(false);

  // Fetch all data on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch staff, zones, and campers in parallel
        const [staffRes, zonesRes, campersRes] = await Promise.all([
          axios.get(`${API}/staff-addresses`),
          axios.get(`${API}/bus-zones`),
          axios.get(`${API}/campers`)
        ]);
        
        setStaffList(staffRes.data.staff || []);
        
        // Convert zones array to object
        const zonesArray = zonesRes.data.zones || [];
        const zonesMap = {};
        zonesArray.forEach(zone => {
          zonesMap[zone.bus_number] = {
            points: zone.points || [],
            color: zone.color || getBusColor(zone.bus_number),
            name: zone.name || `${zone.bus_number} Zone`
          };
        });
        setBusZones(zonesMap);
        
        // Get unique buses from campers
        const busSet = new Set();
        (campersRes.data || []).forEach(c => {
          if (c.am_bus_number && c.am_bus_number.startsWith('Bus')) busSet.add(c.am_bus_number);
          if (c.pm_bus_number && c.pm_bus_number.startsWith('Bus')) busSet.add(c.pm_bus_number);
        });
        const sortedBuses = Array.from(busSet).sort((a, b) => {
          const numA = parseInt(a.replace(/\D/g, '')) || 0;
          const numB = parseInt(b.replace(/\D/g, '')) || 0;
          return numA - numB;
        });
        setUniqueBuses(sortedBuses);
        
      } catch (error) {
        console.error("Error fetching data:", error);
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  // Fetch staff
  const fetchStaff = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/staff-addresses`);
      setStaffList(response.data.staff || []);
    } catch (error) {
      console.error("Error fetching staff:", error);
    }
  }, []);

  // Add new staff member
  const handleAddStaff = async () => {
    if (!newStaffName.trim() || !newStaffAddress.trim()) {
      toast.error("Please enter both name and address");
      return;
    }

    setAddingStaff(true);
    try {
      const response = await axios.post(`${API}/staff-addresses`, {
        name: newStaffName.trim(),
        address: newStaffAddress.trim()
      });
      
      if (response.data.status === "success") {
        toast.success(`Added ${newStaffName}`);
        setNewStaffName("");
        setNewStaffAddress("");
        setShowAddForm(false);
        await fetchStaff();
      }
    } catch (error) {
      console.error("Error adding staff:", error);
      toast.error(error.response?.data?.detail || "Failed to add staff");
    } finally {
      setAddingStaff(false);
    }
  };

  // Assign bus to staff
  const handleAssignBus = async (staffId, busNumber) => {
    try {
      const response = await axios.put(`${API}/staff-addresses/${staffId}`, {
        bus_number: busNumber
      });
      
      if (response.data.status === "success") {
        toast.success(`Assigned to ${busNumber}`);
        await fetchStaff();
      }
    } catch (error) {
      console.error("Error assigning bus:", error);
      toast.error("Failed to assign bus");
    }
  };

  // Delete staff
  const handleDeleteStaff = async (staffId, staffName) => {
    console.log('handleDeleteStaff called:', staffId, staffName);
    
    const confirmed = window.confirm(`Delete ${staffName}?`);
    console.log('User confirmed:', confirmed);
    
    if (!confirmed) return;
    
    try {
      console.log('Sending delete request for:', staffId);
      const response = await axios.delete(`${API}/staff-addresses/${staffId}`);
      console.log('Delete response:', response.data);
      toast.success(`Deleted ${staffName}`);
      await fetchStaff();
    } catch (error) {
      console.error("Error deleting staff:", error);
      console.error("Error details:", error.response?.data);
      toast.error(`Failed to delete: ${error.response?.data?.detail || error.message}`);
    }
  };

  // CSV upload handler
  const handleCSVUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadingCSV(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/staff-addresses/upload-csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      if (response.data.status === "success") {
        const results = response.data.results;
        toast.success(`Imported ${results.success.length} of ${results.total} staff`);
        
        if (results.failed.length > 0) {
          toast.warning(`${results.failed.length} staff could not be imported`);
        }
        
        await fetchStaff();
      }
    } catch (error) {
      console.error("Error uploading CSV:", error);
      toast.error(error.response?.data?.detail || "Failed to upload CSV");
    } finally {
      setUploadingCSV(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Map center - default to Long Island area
  const mapCenter = staffList.length > 0 && staffList[0].lat
    ? { lat: staffList[0].lat, lng: staffList[0].lng }
    : { lat: 40.65, lng: -73.55 };

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading Staff Zone Lookup...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-100">
      <Toaster position="top-right" richColors />
      
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-4 shadow-lg">
        <div className="flex items-center justify-between max-w-screen-2xl mx-auto">
          <div className="flex items-center gap-3">
            <Users className="w-8 h-8" />
            <div>
              <h1 className="text-2xl font-bold">Staff Zone Lookup</h1>
              <p className="text-blue-100 text-sm">{staffList.length} staff members</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="bg-white/20 px-3 py-1 rounded text-sm">
              {staffList.filter(s => s.bus_number).length} assigned / {staffList.length} total
            </span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - Staff List */}
        <div className="w-96 border-r flex flex-col bg-white shadow-lg">
          {/* Actions */}
          <div className="p-3 border-b bg-gray-50 flex gap-2">
            <Button
              size="sm"
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex-1"
              data-testid="add-staff-btn"
            >
              <UserPlus className="w-4 h-4 mr-1" />
              Add Staff
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingCSV}
              data-testid="upload-csv-btn"
            >
              <Upload className="w-4 h-4 mr-1" />
              {uploadingCSV ? "..." : "CSV"}
            </Button>
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv"
              onChange={handleCSVUpload}
              className="hidden"
            />
          </div>

          {/* Add Staff Form */}
          {showAddForm && (
            <div className="p-3 border-b bg-blue-50">
              <div className="space-y-2">
                <div>
                  <Label htmlFor="staff_name" className="text-xs font-medium">Name</Label>
                  <Input
                    id="staff_name"
                    value={newStaffName}
                    onChange={(e) => setNewStaffName(e.target.value)}
                    placeholder="Enter staff name"
                    className="h-9"
                    data-testid="new-staff-name"
                  />
                </div>
                <div>
                  <Label htmlFor="staff_address" className="text-xs font-medium">Address</Label>
                  <Input
                    id="staff_address"
                    value={newStaffAddress}
                    onChange={(e) => setNewStaffAddress(e.target.value)}
                    placeholder="Enter full address"
                    className="h-9"
                    data-testid="new-staff-address"
                  />
                </div>
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    onClick={handleAddStaff}
                    disabled={addingStaff}
                    className="flex-1"
                    data-testid="save-new-staff"
                  >
                    {addingStaff ? "Adding..." : "Add Staff"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowAddForm(false);
                      setNewStaffName("");
                      setNewStaffAddress("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Staff Cards */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {staffList.length === 0 ? (
              <div className="text-center text-gray-500 py-12">
                <Users className="w-16 h-16 mx-auto mb-3 opacity-30" />
                <p className="font-medium">No staff members added yet</p>
                <p className="text-sm mt-1">Add staff manually or upload a CSV file</p>
              </div>
            ) : (
              staffList.map((staff) => (
                <Card
                  key={staff.id}
                  className={`p-3 cursor-pointer transition-all hover:shadow-md border-l-4 ${
                    selectedStaff?.id === staff.id 
                      ? 'ring-2 ring-blue-500 bg-blue-50' 
                      : 'hover:bg-gray-50'
                  }`}
                  style={{ 
                    borderLeftColor: staff.bus_number ? getBusColor(staff.bus_number) : '#9CA3AF' 
                  }}
                  onClick={() => setSelectedStaff(staff)}
                  data-testid={`staff-card-${staff.id}`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-gray-900 truncate">{staff.name}</div>
                      <div className="text-xs text-gray-500 truncate flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3" />
                        {staff.address}
                      </div>
                      
                      {/* Zone/Nearby Info */}
                      {staff.zone_info ? (
                        <div className="mt-1.5">
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                            In Zone: {staff.zone_info.bus_number}
                          </span>
                        </div>
                      ) : staff.nearby_buses?.length > 0 ? (
                        <div className="mt-1.5 text-xs text-gray-600">
                          <span className="font-medium">Nearby:</span> {staff.nearby_buses.slice(0, 3).join(", ")}
                        </div>
                      ) : null}
                    </div>
                    
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-8 w-8 p-0 flex-shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        console.log('Delete clicked for:', staff.id, staff.name);
                        handleDeleteStaff(staff.id, staff.name);
                      }}
                      data-testid={`delete-staff-${staff.id}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                  
                  {/* Bus Assignment */}
                  <div className="mt-3 flex items-center gap-2">
                    <Select
                      value={staff.bus_number || ""}
                      onValueChange={(value) => handleAssignBus(staff.id, value)}
                    >
                      <SelectTrigger 
                        className="h-8 text-sm flex-1"
                        data-testid={`bus-select-${staff.id}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <SelectValue placeholder="Select Bus to Assign" />
                      </SelectTrigger>
                      <SelectContent className="max-h-60 overflow-y-auto">
                        {uniqueBuses.map(bus => (
                          <SelectItem key={bus} value={bus}>
                            <div className="flex items-center gap-2">
                              <div 
                                className="w-3 h-3 rounded-full" 
                                style={{ backgroundColor: getBusColor(bus) }}
                              />
                              {bus}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    {staff.bus_number && (
                      <div 
                        className="w-8 h-8 flex items-center justify-center text-white text-xs font-bold"
                        style={{ 
                          backgroundColor: getBusColor(staff.bus_number),
                          clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)',
                          filter: 'drop-shadow(0 0 1px black) drop-shadow(0 0 1px black)'
                        }}
                        title={staff.bus_number}
                      >
                        <span style={{ marginTop: '6px' }}>
                          {staff.bus_number.replace('Bus #', '')}
                        </span>
                      </div>
                    )}
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>

        {/* Right Panel - Map */}
        <div className="flex-1 relative">
          <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
            <Map
              defaultCenter={mapCenter}
              defaultZoom={11}
              mapId="staff-zone-map-page"
              gestureHandling="greedy"
              disableDefaultUI={false}
              style={{ width: '100%', height: '100%' }}
            >
              {/* Bus Zones - render as polygons */}
              {busZones && typeof busZones === 'object' && Object.entries(busZones).map(([busNumber, zone]) => {
                if (!zone || !zone.points || zone.points.length < 3) return null;
                const busColor = zone.color || getBusColor(busNumber);
                
                return (
                  <ZonePolygon
                    key={busNumber}
                    busNumber={busNumber}
                    points={zone.points}
                    color={busColor}
                  />
                );
              })}

              {/* Staff Markers - Triangles with black outline */}
              {staffList.map((staff) => {
                if (!staff.lat || !staff.lng) return null;
                
                const busColor = staff.bus_number ? getBusColor(staff.bus_number) : '#6B7280';
                const displayText = staff.bus_number 
                  ? staff.bus_number.replace('Bus #', '')
                  : '?';
                
                return (
                  <AdvancedMarker
                    key={staff.id}
                    position={{ lat: staff.lat, lng: staff.lng }}
                    onClick={() => setSelectedStaff(staff)}
                  >
                    {/* Outer triangle (black border) */}
                    <div
                      className="relative cursor-pointer hover:scale-110 transition-transform"
                      style={{ width: '40px', height: '40px' }}
                      data-testid={`staff-marker-${staff.id}`}
                      title={`${staff.name} - ${staff.bus_number || 'Unassigned'}`}
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
                        className="flex items-center justify-center text-white font-bold text-sm"
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

              {/* Selected Staff InfoWindow */}
              {selectedStaff && selectedStaff.lat && (
                <InfoWindow
                  position={{ lat: selectedStaff.lat, lng: selectedStaff.lng }}
                  onCloseClick={() => setSelectedStaff(null)}
                  options={{ maxWidth: 300 }}
                >
                  <div className="p-2" data-testid="staff-info-window">
                    <h3 className="font-bold text-base mb-2">{selectedStaff.name}</h3>
                    <div className="space-y-1.5 text-sm">
                      <p className="text-gray-600">{selectedStaff.address}</p>
                      {selectedStaff.bus_number && (
                        <p>
                          <span className="font-medium">Assigned:</span>{" "}
                          <span 
                            className="px-2 py-0.5 rounded text-white text-xs font-medium"
                            style={{ backgroundColor: getBusColor(selectedStaff.bus_number) }}
                          >
                            {selectedStaff.bus_number}
                          </span>
                        </p>
                      )}
                      {selectedStaff.zone_info && (
                        <p className="text-green-600">
                          <span className="font-medium">In Zone:</span> {selectedStaff.zone_info.bus_number}
                        </p>
                      )}
                      {selectedStaff.nearby_buses?.length > 0 && (
                        <p className="text-gray-600">
                          <span className="font-medium">Nearby:</span> {selectedStaff.nearby_buses.join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </InfoWindow>
              )}
            </Map>
          </APIProvider>
          
          {/* Legend */}
          <div className="absolute bottom-6 left-6 bg-white rounded-lg shadow-lg p-4 text-sm">
            <div className="font-semibold mb-3 text-gray-800">Legend</div>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div 
                  className="w-5 h-5 border-2 border-blue-500 rounded"
                  style={{ backgroundColor: 'rgba(59, 130, 246, 0.25)' }}
                />
                <span className="text-gray-700">Bus Zones</span>
              </div>
              <div className="flex items-center gap-3">
                <div 
                  className="w-5 h-5"
                  style={{ 
                    backgroundColor: '#3B82F6',
                    clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)'
                  }}
                />
                <span className="text-gray-700">Assigned Staff</span>
              </div>
              <div className="flex items-center gap-3">
                <div 
                  className="w-5 h-5"
                  style={{ 
                    backgroundColor: '#6B7280',
                    clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)'
                  }}
                />
                <span className="text-gray-700">Unassigned Staff</span>
              </div>
            </div>
          </div>
          
          {/* Zone Count Badge */}
          <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg px-3 py-2 text-sm">
            <span className="font-medium text-gray-700">
              {Object.keys(busZones).length} Bus Zone{Object.keys(busZones).length !== 1 ? 's' : ''} Displayed
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StaffZoneLookupPage;

import React, { useState, useEffect, useCallback, useRef } from "react";
import { APIProvider, Map, AdvancedMarker, InfoWindow } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { X, Upload, UserPlus, Trash2, MapPin, Users } from "lucide-react";

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

const StaffZoneLookup = ({ isOpen, onClose, busZones, uniqueBuses, onStaffUpdate }) => {
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState(null);
  
  // Add staff form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newStaffName, setNewStaffName] = useState("");
  const [newStaffAddress, setNewStaffAddress] = useState("");
  const [addingStaff, setAddingStaff] = useState(false);
  
  // CSV upload
  const fileInputRef = useRef(null);
  const [uploadingCSV, setUploadingCSV] = useState(false);

  // Fetch staff with addresses
  const fetchStaff = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/staff-addresses`);
      setStaffList(response.data.staff || []);
    } catch (error) {
      console.error("Error fetching staff:", error);
      toast.error("Failed to load staff");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchStaff();
    }
  }, [isOpen, fetchStaff]);

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
        if (onStaffUpdate) onStaffUpdate();
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
        if (onStaffUpdate) onStaffUpdate();
      }
    } catch (error) {
      console.error("Error assigning bus:", error);
      toast.error("Failed to assign bus");
    }
  };

  // Delete staff
  const handleDeleteStaff = async (staffId, staffName) => {
    if (!window.confirm(`Delete ${staffName}?`)) return;
    
    try {
      await axios.delete(`${API}/staff-addresses/${staffId}`);
      toast.success(`Deleted ${staffName}`);
      await fetchStaff();
      if (onStaffUpdate) onStaffUpdate();
    } catch (error) {
      console.error("Error deleting staff:", error);
      toast.error("Failed to delete staff");
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
          console.warn("Failed imports:", results.failed);
          toast.warning(`${results.failed.length} staff could not be imported`);
        }
        
        await fetchStaff();
        if (onStaffUpdate) onStaffUpdate();
      }
    } catch (error) {
      console.error("Error uploading CSV:", error);
      toast.error(error.response?.data?.detail || "Failed to upload CSV");
    } finally {
      setUploadingCSV(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  if (!isOpen) return null;

  // Map center - default to Long Island area
  const mapCenter = staffList.length > 0 && staffList[0].lat
    ? { lat: staffList[0].lat, lng: staffList[0].lng }
    : { lat: 40.65, lng: -73.55 };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-blue-600 to-blue-700">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-white" />
            <h2 className="text-xl font-bold text-white">Staff Zone Lookup</h2>
            <span className="bg-white/20 text-white px-2 py-1 rounded text-sm">
              {staffList.length} staff members
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-white hover:bg-white/20"
            data-testid="close-staff-lookup"
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Main Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Panel - Staff List */}
          <div className="w-96 border-r flex flex-col bg-gray-50">
            {/* Actions */}
            <div className="p-3 border-b bg-white flex gap-2">
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
                {uploadingCSV ? "Uploading..." : "CSV"}
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
                    <Label htmlFor="staff_name" className="text-xs">Name</Label>
                    <Input
                      id="staff_name"
                      value={newStaffName}
                      onChange={(e) => setNewStaffName(e.target.value)}
                      placeholder="Enter staff name"
                      className="h-8 text-sm"
                      data-testid="new-staff-name"
                    />
                  </div>
                  <div>
                    <Label htmlFor="staff_address" className="text-xs">Address</Label>
                    <Input
                      id="staff_address"
                      value={newStaffAddress}
                      onChange={(e) => setNewStaffAddress(e.target.value)}
                      placeholder="Enter full address"
                      className="h-8 text-sm"
                      data-testid="new-staff-address"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={handleAddStaff}
                      disabled={addingStaff}
                      className="flex-1"
                      data-testid="save-new-staff"
                    >
                      {addingStaff ? "Adding..." : "Add"}
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
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {loading ? (
                <div className="text-center text-gray-500 py-8">Loading...</div>
              ) : staffList.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <Users className="w-12 h-12 mx-auto mb-2 opacity-30" />
                  <p>No staff members added yet</p>
                  <p className="text-xs mt-1">Add staff manually or upload a CSV</p>
                </div>
              ) : (
                staffList.map((staff) => (
                  <Card
                    key={staff.id}
                    className={`p-3 cursor-pointer transition-all hover:shadow-md ${
                      selectedStaff?.id === staff.id ? 'ring-2 ring-blue-500' : ''
                    }`}
                    onClick={() => setSelectedStaff(staff)}
                    data-testid={`staff-card-${staff.id}`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-sm truncate">{staff.name}</div>
                        <div className="text-xs text-gray-500 truncate">{staff.address}</div>
                        
                        {/* Zone/Nearby Info */}
                        {staff.zone_info ? (
                          <div className="mt-1 text-xs">
                            <span className="text-green-600 font-medium">
                              In Zone: {staff.zone_info.bus_number}
                            </span>
                          </div>
                        ) : staff.nearby_buses?.length > 0 ? (
                          <div className="mt-1 text-xs text-gray-600">
                            Nearby: {staff.nearby_buses.slice(0, 3).join(", ")}
                          </div>
                        ) : null}
                      </div>
                      
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteStaff(staff.id, staff.name);
                        }}
                        data-testid={`delete-staff-${staff.id}`}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                    
                    {/* Bus Assignment */}
                    <div className="mt-2 flex items-center gap-2">
                      <Select
                        value={staff.bus_number || ""}
                        onValueChange={(value) => handleAssignBus(staff.id, value)}
                      >
                        <SelectTrigger 
                          className="h-7 text-xs flex-1"
                          data-testid={`bus-select-${staff.id}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <SelectValue placeholder="Assign Bus" />
                        </SelectTrigger>
                        <SelectContent>
                          {uniqueBuses.filter(b => b.startsWith('Bus')).map(bus => (
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
                          className="w-6 h-6 flex items-center justify-center text-white text-xs font-bold"
                          style={{ 
                            backgroundColor: getBusColor(staff.bus_number),
                            clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)'
                          }}
                          title={staff.bus_number}
                        >
                          {staff.bus_number.replace('Bus #', '')}
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
                mapId="staff-zone-map"
                gestureHandling="greedy"
                disableDefaultUI={false}
                style={{ width: '100%', height: '100%' }}
              >
                {/* Bus Zones (no campers) - only render if busZones is an array */}
                {Array.isArray(busZones) && busZones.map((zone) => {
                  if (!zone.points || zone.points.length < 3) return null;
                  const busColor = getBusColor(zone.bus_number);
                  
                  // Draw polygon using SVG overlay approach
                  return (
                    <div key={zone.id}>
                      {/* Zone polygon would be rendered here - using Google Maps Polygon API */}
                    </div>
                  );
                })}

                {/* Staff Markers - Triangles */}
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
                      <div
                        className="flex items-center justify-center text-white font-bold text-xs cursor-pointer hover:scale-110 transition-transform"
                        style={{
                          width: '32px',
                          height: '32px',
                          backgroundColor: busColor,
                          clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)',
                          boxShadow: '0 2px 4px rgba(0,0,0,0.3)'
                        }}
                        data-testid={`staff-marker-${staff.id}`}
                        title={`${staff.name} - ${staff.bus_number || 'Unassigned'}`}
                      >
                        <span style={{ marginTop: '8px' }}>{displayText}</span>
                      </div>
                    </AdvancedMarker>
                  );
                })}

                {/* Selected Staff InfoWindow */}
                {selectedStaff && selectedStaff.lat && (
                  <InfoWindow
                    position={{ lat: selectedStaff.lat, lng: selectedStaff.lng }}
                    onCloseClick={() => setSelectedStaff(null)}
                    options={{ maxWidth: 280 }}
                  >
                    <div className="p-2" data-testid="staff-info-window">
                      <h3 className="font-bold text-base mb-2">{selectedStaff.name}</h3>
                      <div className="space-y-1 text-sm">
                        <p><strong>Address:</strong> {selectedStaff.address}</p>
                        {selectedStaff.bus_number && (
                          <p>
                            <strong>Assigned:</strong>{" "}
                            <span 
                              className="px-2 py-0.5 rounded text-white text-xs"
                              style={{ backgroundColor: getBusColor(selectedStaff.bus_number) }}
                            >
                              {selectedStaff.bus_number}
                            </span>
                          </p>
                        )}
                        {selectedStaff.zone_info && (
                          <p className="text-green-600">
                            <strong>In Zone:</strong> {selectedStaff.zone_info.bus_number}
                          </p>
                        )}
                        {selectedStaff.nearby_buses?.length > 0 && (
                          <p className="text-gray-600">
                            <strong>Nearby:</strong> {selectedStaff.nearby_buses.join(", ")}
                          </p>
                        )}
                      </div>
                    </div>
                  </InfoWindow>
                )}
              </Map>
            </APIProvider>
            
            {/* Legend */}
            <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg p-3 text-xs">
              <div className="font-semibold mb-2">Legend</div>
              <div className="flex items-center gap-2 mb-1">
                <div 
                  className="w-4 h-4"
                  style={{ 
                    backgroundColor: '#3B82F6',
                    clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)'
                  }}
                />
                <span>Assigned Staff</span>
              </div>
              <div className="flex items-center gap-2">
                <div 
                  className="w-4 h-4"
                  style={{ 
                    backgroundColor: '#6B7280',
                    clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)'
                  }}
                />
                <span>Unassigned Staff</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StaffZoneLookup;

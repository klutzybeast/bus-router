import React, { useState, useEffect, useCallback } from "react";
import { APIProvider, Map, AdvancedMarker } from "@vis.gl/react-google-maps";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar, RefreshCw, MapPin } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;
const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

export const HistoryDialog = ({ open, busNumber, uniqueBuses, onClose, onChangeBus }) => {
  const [historyDate, setHistoryDate] = useState(new Date().toISOString().split('T')[0]);
  const [historyPeriod, setHistoryPeriod] = useState('');
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [availableDates, setAvailableDates] = useState([]);

  const fetchAvailableDates = useCallback(async (bus) => {
    if (!bus) return;
    try {
      const response = await axios.get(`${API}/bus-tracking/history-dates/${encodeURIComponent(bus)}`);
      setAvailableDates(response.data.dates || []);
    } catch (error) {
      console.error("Error fetching history dates:", error);
      setAvailableDates([]);
    }
  }, []);

  const fetchHistoryData = useCallback(async () => {
    if (!busNumber || !historyDate) return;
    setHistoryLoading(true);
    try {
      const url = `${API}/bus-tracking/history/${encodeURIComponent(busNumber)}?date=${historyDate}${historyPeriod ? `&period=${historyPeriod}` : ''}`;
      const response = await axios.get(url);
      setHistoryData(response.data);
    } catch (error) {
      console.error("Error fetching history:", error);
      setHistoryData({ success: false, message: "Failed to load history" });
    } finally {
      setHistoryLoading(false);
    }
  }, [busNumber, historyDate, historyPeriod]);

  useEffect(() => {
    if (open && busNumber) {
      setHistoryData(null);
      setHistoryDate(new Date().toISOString().split('T')[0]);
      setHistoryPeriod('');
      fetchAvailableDates(busNumber);
    }
  }, [open, busNumber, fetchAvailableDates]);

  useEffect(() => {
    if (open && busNumber && historyDate) {
      fetchHistoryData();
    }
  }, [historyDate, historyPeriod, busNumber, open, fetchHistoryData]);

  const handleBusChange = (val) => {
    if (onChangeBus) {
      onChangeBus(val);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="history-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-600" />
            Tracking History: {busNumber}
          </DialogTitle>
          <DialogDescription>
            View historical route and stop data
          </DialogDescription>
        </DialogHeader>
        
        <div className="py-4 space-y-4">
          {/* Bus, Date and Period Selection */}
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Bus</label>
              <Select value={busNumber || ''} onValueChange={handleBusChange}>
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="Select bus" />
                </SelectTrigger>
                <SelectContent>
                  {uniqueBuses.map(bus => (
                    <SelectItem key={bus} value={bus}>{bus}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
              <Input
                type="date"
                value={historyDate}
                onChange={(e) => setHistoryDate(e.target.value)}
                className="w-40"
                data-testid="history-date-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Period</label>
              <Select value={historyPeriod || "all"} onValueChange={(val) => setHistoryPeriod(val === "all" ? "" : val)}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="All Day" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Day</SelectItem>
                  <SelectItem value="AM">AM Only</SelectItem>
                  <SelectItem value="PM">PM Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {availableDates.length > 0 && (
              <div className="text-xs text-gray-500">
                {availableDates.length} days with data
              </div>
            )}
          </div>

          {historyLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
              <span className="ml-2">Loading history...</span>
            </div>
          ) : historyData?.success ? (
            <div className="space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-blue-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-blue-600">{historyData.point_count}</div>
                  <div className="text-xs text-blue-500">Location Points</div>
                </div>
                <div className="bg-yellow-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-yellow-600">{historyData.stop_count}</div>
                  <div className="text-xs text-yellow-500">Stops Made</div>
                </div>
                <div className="bg-green-50 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {historyData.points?.length > 0 
                      ? `${new Date(historyData.points[0].timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - ${new Date(historyData.points[historyData.points.length-1].timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`
                      : 'N/A'
                    }
                  </div>
                  <div className="text-xs text-green-500">Time Range</div>
                </div>
              </div>

              {/* Map with Route */}
              {historyData.points?.length > 0 && (
                <div className="h-64 rounded-lg overflow-hidden border">
                  <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
                    <Map
                      defaultZoom={13}
                      defaultCenter={{ 
                        lat: historyData.points[Math.floor(historyData.points.length / 2)]?.latitude || 40.7,
                        lng: historyData.points[Math.floor(historyData.points.length / 2)]?.longitude || -73.9
                      }}
                      mapId="history-map"
                    >
                      {/* Route points */}
                      {historyData.points.filter((_, i) => i % 5 === 0).map((point, idx) => {
                        if (idx === 0) return null;
                        return (
                          <AdvancedMarker
                            key={idx}
                            position={{ lat: point.latitude, lng: point.longitude }}
                          >
                            <div className="w-2 h-2 bg-blue-500 rounded-full opacity-60" />
                          </AdvancedMarker>
                        );
                      })}
                      {/* Start marker */}
                      <AdvancedMarker position={{ lat: historyData.points[0].latitude, lng: historyData.points[0].longitude }}>
                        <div className="w-6 h-6 bg-green-500 rounded-full border-2 border-white shadow flex items-center justify-center text-white text-xs font-bold">S</div>
                      </AdvancedMarker>
                      {/* End marker */}
                      <AdvancedMarker position={{ lat: historyData.points[historyData.points.length-1].latitude, lng: historyData.points[historyData.points.length-1].longitude }}>
                        <div className="w-6 h-6 bg-red-500 rounded-full border-2 border-white shadow flex items-center justify-center text-white text-xs font-bold">E</div>
                      </AdvancedMarker>
                      {/* Stop markers */}
                      {historyData.stops?.map((stop, idx) => (
                        <AdvancedMarker key={`stop-${idx}`} position={{ lat: stop.latitude, lng: stop.longitude }}>
                          <div className="w-5 h-5 bg-yellow-500 rounded-full border-2 border-white shadow flex items-center justify-center text-white text-[10px] font-bold">{idx + 1}</div>
                        </AdvancedMarker>
                      ))}
                    </Map>
                  </APIProvider>
                </div>
              )}

              {/* Stops List */}
              {historyData.stops?.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <MapPin className="w-4 h-4" />
                    Stops ({historyData.stops.length})
                  </h3>
                  <div className="max-h-48 overflow-y-auto border rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left">#</th>
                          <th className="px-3 py-2 text-left">Time</th>
                          <th className="px-3 py-2 text-left">Duration</th>
                          <th className="px-3 py-2 text-left">Period</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historyData.stops.map((stop, idx) => (
                          <tr key={idx} className="border-t hover:bg-gray-50">
                            <td className="px-3 py-2 font-medium">{idx + 1}</td>
                            <td className="px-3 py-2">
                              {stop.stop_started_at 
                                ? new Date(stop.stop_started_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
                                : 'N/A'
                              }
                            </td>
                            <td className="px-3 py-2 font-mono">
                              {stop.duration_formatted || `${Math.round(stop.duration_seconds)}s`}
                            </td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 rounded text-xs ${stop.period === 'AM' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                                {stop.period}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {historyData.points?.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No tracking data for this date</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>Select a date to view tracking history</p>
              {availableDates.length > 0 && (
                <p className="text-sm mt-2">Available dates: {availableDates.slice(0, 5).join(', ')}{availableDates.length > 5 ? '...' : ''}</p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default HistoryDialog;

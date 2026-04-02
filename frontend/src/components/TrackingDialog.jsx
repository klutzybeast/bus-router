import React from "react";
import { APIProvider, Map, AdvancedMarker } from "@vis.gl/react-google-maps";
import { Button } from "@/components/ui/button";
import { Navigation, RefreshCw, Radio, MapPin, Calendar } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

export const TrackingDialog = ({
  trackingBus,
  trackingData,
  trackingLoading,
  nearestStop,
  busColors,
  onClose,
  onViewHistory,
}) => {
  const busColor = busColors[trackingBus] || '#3b82f6';

  return (
    <Dialog open={trackingBus !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="tracking-dialog">
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

              {/* Map showing bus location */}
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

              {/* Current Stop Info */}
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
                        style={{ borderColor: busColor }}
                      >
                        <div 
                          className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
                          style={{ backgroundColor: busColor }}
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
              ) : trackingData.is_stopped ? (
                <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-3 text-center">
                  <div className="flex items-center justify-center gap-2 text-yellow-700">
                    <MapPin className="w-5 h-5" />
                    <span className="font-medium">Bus is stopped</span>
                  </div>
                  <p className="text-2xl font-bold text-yellow-800 mt-1">
                    {trackingData.stop_duration >= 60 
                      ? `${Math.floor(trackingData.stop_duration / 60)}m ${Math.floor(trackingData.stop_duration % 60)}s`
                      : `${Math.floor(trackingData.stop_duration)}s`
                    }
                  </p>
                  <p className="text-xs text-yellow-600">at this location</p>
                </div>
              ) : (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-center text-green-700 text-sm">
                  <MapPin className="w-4 h-4 inline mr-1" />
                  Bus is moving
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

        <DialogFooter className="flex gap-2">
          <Button variant="outline" onClick={() => { onClose(); onViewHistory(trackingBus); }}>
            <Calendar className="w-4 h-4 mr-2" />
            View History
          </Button>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TrackingDialog;

/* global google */
import { useEffect, useRef, useCallback } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

/**
 * ZoneCreator - Allows users to create new zones by clicking on the map
 * 
 * Usage:
 * - Click on map to add polygon vertices
 * - Points appear as markers that can be dragged
 * - Minimum 3 points required to form a zone
 * - Preview polygon shown while creating
 */
const ZoneCreator = ({ 
  isActive = false,
  points = [],
  color = '#FF0000',
  onPointsChange,
  onComplete,
}) => {
  const map = useMap();
  const polygonRef = useRef(null);
  const polylineRef = useRef(null);
  const markersRef = useRef([]);
  const clickListenerRef = useRef(null);
  const pointsRef = useRef(points);

  // Keep pointsRef in sync
  useEffect(() => {
    pointsRef.current = points;
  }, [points]);

  // Clear all map objects
  const clearAll = useCallback(() => {
    // Clear markers
    markersRef.current.forEach(marker => {
      google.maps.event.clearInstanceListeners(marker);
      marker.setMap(null);
    });
    markersRef.current = [];

    // Clear polygon
    if (polygonRef.current) {
      google.maps.event.clearInstanceListeners(polygonRef.current);
      polygonRef.current.setMap(null);
      polygonRef.current = null;
    }

    // Clear polyline
    if (polylineRef.current) {
      polylineRef.current.setMap(null);
      polylineRef.current = null;
    }

    // Clear click listener
    if (clickListenerRef.current) {
      google.maps.event.removeListener(clickListenerRef.current);
      clickListenerRef.current = null;
    }
  }, []);

  // Set up map click listener
  useEffect(() => {
    if (!map || !isActive) {
      if (clickListenerRef.current) {
        google.maps.event.removeListener(clickListenerRef.current);
        clickListenerRef.current = null;
      }
      return;
    }

    // Set up click listener using ref to get latest points
    if (!clickListenerRef.current) {
      clickListenerRef.current = map.addListener('click', (e) => {
        if (e.latLng) {
          const newPoint = { lat: e.latLng.lat(), lng: e.latLng.lng() };
          const currentPoints = pointsRef.current;
          onPointsChange([...currentPoints, newPoint]);
        }
      });
    }

    return () => {
      if (clickListenerRef.current) {
        google.maps.event.removeListener(clickListenerRef.current);
        clickListenerRef.current = null;
      }
    };
  }, [map, isActive, onPointsChange]);

  // Update markers and shapes when points change
  useEffect(() => {
    if (!map || !isActive) return;

    // Clear existing markers
    markersRef.current.forEach(m => {
      google.maps.event.clearInstanceListeners(m);
      m.setMap(null);
    });
    markersRef.current = [];

    // Create markers for each point
    points.forEach((point, index) => {
      const marker = new google.maps.Marker({
        position: point,
        map: map,
        draggable: true,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: index === 0 ? 10 : 8,
          fillColor: index === 0 ? '#00FF00' : '#FFFFFF',
          fillOpacity: 1,
          strokeColor: color,
          strokeWeight: 3,
        },
        zIndex: 2000 + index,
        title: index === 0 ? 'Click to complete zone' : `Point ${index + 1} (drag to move)`,
      });

      // Handle drag end
      marker.addListener('dragend', () => {
        const newPoints = pointsRef.current.map((p, i) => {
          if (i === index) {
            return { lat: marker.getPosition().lat(), lng: marker.getPosition().lng() };
          }
          return p;
        });
        onPointsChange(newPoints);
      });

      // Click on first marker to close polygon (if 3+ points)
      if (index === 0 && points.length >= 3) {
        marker.addListener('click', (e) => {
          e.stop(); // Prevent map click
          if (onComplete) {
            onComplete();
          }
        });
      }

      // Right-click to remove point
      marker.addListener('rightclick', (e) => {
        e.stop();
        const newPoints = pointsRef.current.filter((_, i) => i !== index);
        onPointsChange(newPoints);
      });

      markersRef.current.push(marker);
    });

    // Update polygon/polyline preview
    if (points.length >= 3) {
      // Show closed polygon
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
        polylineRef.current = null;
      }

      if (polygonRef.current) {
        polygonRef.current.setPath(points);
      } else {
        polygonRef.current = new google.maps.Polygon({
          paths: points,
          fillColor: color,
          fillOpacity: 0.2,
          strokeColor: color,
          strokeOpacity: 0.8,
          strokeWeight: 2,
          clickable: false,
          zIndex: 1000,
        });
        polygonRef.current.setMap(map);
      }
    } else if (points.length >= 1) {
      // Show polyline for < 3 points
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
        polygonRef.current = null;
      }

      if (polylineRef.current) {
        polylineRef.current.setPath(points);
      } else {
        polylineRef.current = new google.maps.Polyline({
          path: points,
          strokeColor: color,
          strokeOpacity: 0.8,
          strokeWeight: 2,
          zIndex: 1000,
        });
        polylineRef.current.setMap(map);
      }
    } else {
      // No points - clear shapes
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
        polygonRef.current = null;
      }
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
        polylineRef.current = null;
      }
    }
  }, [map, isActive, points, color, onPointsChange, onComplete]);

  // Cleanup on unmount or deactivation
  useEffect(() => {
    if (!isActive) {
      clearAll();
    }
    return () => {
      clearAll();
    };
  }, [isActive, clearAll]);

  return null;
};

export default ZoneCreator;

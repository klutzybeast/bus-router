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

  // Create vertex marker
  const createMarker = useCallback((point, index) => {
    if (!map) return null;

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
      title: index === 0 ? 'Start point (click to close polygon)' : `Point ${index + 1}`,
    });

    // Drag updates
    marker.addListener('drag', () => {
      const newPoints = points.map((p, i) => {
        if (i === index) {
          return { lat: marker.getPosition().lat(), lng: marker.getPosition().lng() };
        }
        return p;
      });
      onPointsChange(newPoints);
    });

    // Click on first marker to close polygon (if 3+ points)
    if (index === 0 && points.length >= 3) {
      marker.addListener('click', () => {
        if (onComplete) {
          onComplete();
        }
      });
    }

    // Right-click to remove point
    marker.addListener('rightclick', () => {
      const newPoints = points.filter((_, i) => i !== index);
      onPointsChange(newPoints);
    });

    return marker;
  }, [map, points, color, onPointsChange, onComplete]);

  // Main effect
  useEffect(() => {
    if (!map) return;

    if (!isActive) {
      clearAll();
      return;
    }

    // Set up click listener for adding points
    if (!clickListenerRef.current) {
      clickListenerRef.current = map.addListener('click', (e) => {
        if (e.latLng) {
          const newPoint = { lat: e.latLng.lat(), lng: e.latLng.lng() };
          onPointsChange([...points, newPoint]);
        }
      });
    }

    // Clear existing markers and recreate
    markersRef.current.forEach(m => {
      google.maps.event.clearInstanceListeners(m);
      m.setMap(null);
    });
    markersRef.current = [];

    // Create markers for each point
    points.forEach((point, index) => {
      const marker = createMarker(point, index);
      if (marker) {
        markersRef.current.push(marker);
      }
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
    }

    return () => {
      // Don't clean up on re-render, only when deactivated
    };
  }, [map, isActive, points, color, createMarker, onPointsChange, clearAll]);

  // Cleanup on unmount or deactivation
  useEffect(() => {
    return () => {
      clearAll();
    };
  }, [clearAll]);

  // Clean up when deactivated
  useEffect(() => {
    if (!isActive) {
      clearAll();
    }
  }, [isActive, clearAll]);

  return null;
};

export default ZoneCreator;

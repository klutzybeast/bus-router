/* global google */
import { useEffect, useRef, useCallback } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

/**
 * ZoneCreator - Allows users to create new zones by clicking on the map
 * 
 * Flow:
 * - Click on map to add vertices (shown as draggable markers)
 * - Lines connect the points as you add them (NOT auto-closing)
 * - Drag points to adjust position while creating
 * - Click "Save Zone" to complete and close the polygon
 * - Right-click on a point to delete it
 */
const ZoneCreator = ({ 
  isActive = false,
  points = [],
  color = '#FF0000',
  onPointsChange,
}) => {
  const map = useMap();
  const polylineRef = useRef(null);
  const markersRef = useRef([]);
  const clickListenerRef = useRef(null);
  const pointsRef = useRef(points);

  // Keep pointsRef in sync with props
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

  // Update markers and polyline when points change
  useEffect(() => {
    if (!map || !isActive) return;

    // Clear existing markers
    markersRef.current.forEach(m => {
      google.maps.event.clearInstanceListeners(m);
      m.setMap(null);
    });
    markersRef.current = [];

    // Create markers for each point - all draggable
    points.forEach((point, index) => {
      const isFirst = index === 0;
      const isLast = index === points.length - 1;
      
      const marker = new google.maps.Marker({
        position: point,
        map: map,
        draggable: true,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: isFirst ? 10 : 8,
          fillColor: isFirst ? '#00FF00' : (isLast ? '#FFD700' : '#FFFFFF'),
          fillOpacity: 1,
          strokeColor: color,
          strokeWeight: 3,
        },
        zIndex: 2000 + index,
        title: isFirst ? 'Start point' : (isLast ? 'Last point (drag to adjust)' : `Point ${index + 1}`),
      });

      // Handle drag end - update points
      marker.addListener('dragend', () => {
        const newPoints = pointsRef.current.map((p, i) => {
          if (i === index) {
            return { lat: marker.getPosition().lat(), lng: marker.getPosition().lng() };
          }
          return p;
        });
        onPointsChange(newPoints);
      });

      // Right-click to remove point
      marker.addListener('rightclick', (e) => {
        e.stop();
        const newPoints = pointsRef.current.filter((_, i) => i !== index);
        onPointsChange(newPoints);
      });

      markersRef.current.push(marker);
    });

    // Update polyline - show OPEN path (not closed)
    if (points.length >= 1) {
      if (polylineRef.current) {
        polylineRef.current.setPath(points);
      } else {
        polylineRef.current = new google.maps.Polyline({
          path: points,
          strokeColor: color,
          strokeOpacity: 0.9,
          strokeWeight: 3,
          zIndex: 1000,
        });
        polylineRef.current.setMap(map);
      }
    } else {
      // No points - clear polyline
      if (polylineRef.current) {
        polylineRef.current.setMap(null);
        polylineRef.current = null;
      }
    }
  }, [map, isActive, points, color, onPointsChange]);

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

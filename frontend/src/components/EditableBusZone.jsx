/* global google */
import { useEffect, useRef, useCallback } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

/**
 * EditableBusZone - Renders a user-defined editable polygon zone
 * 
 * Features:
 * - Display saved zones as polygons
 * - Click to add new points when in edit mode
 * - Drag vertices to adjust zone shape
 * - Visual feedback for edit mode
 */
const EditableBusZone = ({ 
  busNumber, 
  points = [],
  color = '#FF0000',
  isEditing = false,
  isSelected = false,
  showZone = true,
  onPointsChange,
  onZoneClick,
}) => {
  const map = useMap();
  const polygonRef = useRef(null);
  const markersRef = useRef([]);

  // Clean up markers
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach(marker => {
      marker.setMap(null);
    });
    markersRef.current = [];
  }, []);

  // Create draggable vertex markers for edit mode
  const createVertexMarkers = useCallback((path) => {
    clearMarkers();
    
    if (!map || !isEditing || path.length === 0) return;

    path.forEach((point, index) => {
      const marker = new google.maps.Marker({
        position: point,
        map: map,
        draggable: true,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: '#FFFFFF',
          fillOpacity: 1,
          strokeColor: color,
          strokeWeight: 3,
        },
        zIndex: 1000 + index,
      });

      // Handle drag
      marker.addListener('drag', () => {
        const newPath = [...path];
        newPath[index] = {
          lat: marker.getPosition().lat(),
          lng: marker.getPosition().lng()
        };
        if (polygonRef.current) {
          polygonRef.current.setPath(newPath);
        }
      });

      // Handle drag end - update parent
      marker.addListener('dragend', () => {
        const newPath = path.map((p, i) => {
          if (i === index) {
            return {
              lat: marker.getPosition().lat(),
              lng: marker.getPosition().lng()
            };
          }
          return p;
        });
        if (onPointsChange) {
          onPointsChange(newPath);
        }
      });

      // Right-click to delete vertex (minimum 3 points)
      marker.addListener('rightclick', () => {
        if (path.length > 3) {
          const newPath = path.filter((_, i) => i !== index);
          if (onPointsChange) {
            onPointsChange(newPath);
          }
        }
      });

      markersRef.current.push(marker);
    });
  }, [map, isEditing, color, onPointsChange, clearMarkers]);

  // Create or update polygon
  useEffect(() => {
    const cleanup = () => {
      if (polygonRef.current) {
        google.maps.event.clearInstanceListeners(polygonRef.current);
        polygonRef.current.setMap(null);
        polygonRef.current = null;
      }
      clearMarkers();
    };

    if (!map || !showZone || points.length < 3) {
      cleanup();
      return cleanup;
    }

    const path = points.map(p => ({ lat: p.lat, lng: p.lng }));

    if (polygonRef.current) {
      // Update existing polygon
      polygonRef.current.setPath(path);
      polygonRef.current.setOptions({
        fillColor: color,
        fillOpacity: isEditing ? 0.25 : (isSelected ? 0.3 : 0.15),
        strokeColor: color,
        strokeOpacity: isEditing ? 1 : (isSelected ? 0.9 : 0.6),
        strokeWeight: isEditing ? 3 : (isSelected ? 2 : 1.5),
        zIndex: isEditing ? 100 : (isSelected ? 2 : 1),
        editable: false, // We use custom markers instead
      });
    } else {
      // Create new polygon
      const newPolygon = new google.maps.Polygon({
        paths: path,
        fillColor: color,
        fillOpacity: isEditing ? 0.25 : (isSelected ? 0.3 : 0.15),
        strokeColor: color,
        strokeOpacity: isEditing ? 1 : (isSelected ? 0.9 : 0.6),
        strokeWeight: isEditing ? 3 : (isSelected ? 2 : 1.5),
        clickable: true,
        zIndex: isEditing ? 100 : (isSelected ? 2 : 1),
        editable: false,
      });
      
      newPolygon.setMap(map);
      
      // Click handler
      newPolygon.addListener('click', (e) => {
        if (isEditing && e.latLng) {
          // In edit mode, clicking inside polygon adds a new point
          // Find the edge closest to the click and insert point there
          const clickPoint = { lat: e.latLng.lat(), lng: e.latLng.lng() };
          const newPath = insertPointOnClosestEdge(path, clickPoint);
          if (onPointsChange) {
            onPointsChange(newPath);
          }
        } else if (onZoneClick) {
          onZoneClick(busNumber);
        }
      });
      
      polygonRef.current = newPolygon;
    }

    // Create vertex markers in edit mode
    if (isEditing) {
      createVertexMarkers(path);
    } else {
      clearMarkers();
    }

    return cleanup;
  }, [map, points, showZone, color, isEditing, isSelected, busNumber, onZoneClick, onPointsChange, createVertexMarkers, clearMarkers]);

  return null;
};

/**
 * Find the closest edge and insert a point there
 */
function insertPointOnClosestEdge(path, clickPoint) {
  if (path.length < 2) return [...path, clickPoint];

  let minDist = Infinity;
  let insertIndex = path.length;

  for (let i = 0; i < path.length; i++) {
    const p1 = path[i];
    const p2 = path[(i + 1) % path.length];
    const dist = pointToSegmentDistance(clickPoint, p1, p2);
    
    if (dist < minDist) {
      minDist = dist;
      insertIndex = i + 1;
    }
  }

  const newPath = [...path];
  newPath.splice(insertIndex, 0, clickPoint);
  return newPath;
}

/**
 * Calculate distance from point to line segment
 */
function pointToSegmentDistance(p, v, w) {
  const l2 = (v.lat - w.lat) ** 2 + (v.lng - w.lng) ** 2;
  if (l2 === 0) return Math.sqrt((p.lat - v.lat) ** 2 + (p.lng - v.lng) ** 2);
  
  let t = ((p.lat - v.lat) * (w.lat - v.lat) + (p.lng - v.lng) * (w.lng - v.lng)) / l2;
  t = Math.max(0, Math.min(1, t));
  
  const proj = {
    lat: v.lat + t * (w.lat - v.lat),
    lng: v.lng + t * (w.lng - v.lng)
  };
  
  return Math.sqrt((p.lat - proj.lat) ** 2 + (p.lng - proj.lng) ** 2);
}

export default EditableBusZone;

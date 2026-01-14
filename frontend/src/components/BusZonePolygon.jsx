/* global google */
import { useEffect, useRef, useMemo } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

/**
 * Calculate convex hull using Graham scan algorithm
 * Returns points in clockwise order for Google Maps Polygon
 */
function convexHull(points) {
  if (points.length < 3) return points;

  // Find the point with lowest y (and leftmost if tie)
  let start = 0;
  for (let i = 1; i < points.length; i++) {
    if (points[i].lat < points[start].lat || 
        (points[i].lat === points[start].lat && points[i].lng < points[start].lng)) {
      start = i;
    }
  }

  // Swap start point to beginning
  [points[0], points[start]] = [points[start], points[0]];
  const pivot = points[0];

  // Sort points by polar angle with pivot
  const sortedPoints = points.slice(1).sort((a, b) => {
    const angleA = Math.atan2(a.lat - pivot.lat, a.lng - pivot.lng);
    const angleB = Math.atan2(b.lat - pivot.lat, b.lng - pivot.lng);
    if (angleA !== angleB) return angleA - angleB;
    // If same angle, closer point first
    const distA = (a.lat - pivot.lat) ** 2 + (a.lng - pivot.lng) ** 2;
    const distB = (b.lat - pivot.lat) ** 2 + (b.lng - pivot.lng) ** 2;
    return distA - distB;
  });

  // Cross product to determine turn direction
  const cross = (o, a, b) => 
    (a.lng - o.lng) * (b.lat - o.lat) - (a.lat - o.lat) * (b.lng - o.lng);

  const hull = [pivot];
  for (const point of sortedPoints) {
    while (hull.length > 1 && cross(hull[hull.length - 2], hull[hull.length - 1], point) <= 0) {
      hull.pop();
    }
    hull.push(point);
  }

  return hull;
}

/**
 * Expand hull by adding padding around the convex hull
 * This creates a buffer zone around the pins
 */
function expandHull(hull, paddingMeters = 200) {
  if (hull.length < 3) return hull;
  
  // Convert meters to approximate degrees (at equator, 1 degree ≈ 111km)
  const avgLat = hull.reduce((sum, p) => sum + p.lat, 0) / hull.length;
  const latPadding = paddingMeters / 111000;
  const lngPadding = paddingMeters / (111000 * Math.cos(avgLat * Math.PI / 180));
  
  // Calculate centroid
  const centroid = {
    lat: hull.reduce((sum, p) => sum + p.lat, 0) / hull.length,
    lng: hull.reduce((sum, p) => sum + p.lng, 0) / hull.length
  };
  
  // Expand each point away from centroid
  return hull.map(point => {
    const dx = point.lng - centroid.lng;
    const dy = point.lat - centroid.lat;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return point;
    
    const scale = 1 + Math.sqrt(lngPadding * lngPadding + latPadding * latPadding) / dist;
    return {
      lat: centroid.lat + dy * scale,
      lng: centroid.lng + dx * scale
    };
  });
}

/**
 * BusZonePolygon - Renders a polygon zone around pins for a specific bus
 */
const BusZonePolygon = ({ 
  busNumber, 
  campers, 
  color, 
  isSelected,
  onZoneClick,
  showZone = true
}) => {
  const map = useMap();
  const polygonRef = useRef(null);

  // Calculate zone path from campers
  const zonePath = useMemo(() => {
    if (!campers || campers.length === 0) return [];
    
    // Get all unique locations for this bus
    const points = campers
      .filter(c => c.location?.latitude && c.location?.longitude)
      .map(c => ({
        lat: c.location.latitude,
        lng: c.location.longitude
      }));
    
    if (points.length === 0) return [];
    if (points.length === 1) {
      // Single point - create a small circle-like polygon
      const p = points[0];
      const offset = 0.003; // ~300m
      return [
        { lat: p.lat + offset, lng: p.lng },
        { lat: p.lat + offset * 0.7, lng: p.lng + offset * 0.7 },
        { lat: p.lat, lng: p.lng + offset },
        { lat: p.lat - offset * 0.7, lng: p.lng + offset * 0.7 },
        { lat: p.lat - offset, lng: p.lng },
        { lat: p.lat - offset * 0.7, lng: p.lng - offset * 0.7 },
        { lat: p.lat, lng: p.lng - offset },
        { lat: p.lat + offset * 0.7, lng: p.lng - offset * 0.7 },
      ];
    }
    if (points.length === 2) {
      // Two points - create an elongated shape
      const p1 = points[0];
      const p2 = points[1];
      const offset = 0.002;
      const dx = p2.lng - p1.lng;
      const dy = p2.lat - p1.lat;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len === 0) return [];
      const nx = -dy / len * offset;
      const ny = dx / len * offset;
      return [
        { lat: p1.lat + ny + offset, lng: p1.lng + nx },
        { lat: p2.lat + ny + offset, lng: p2.lng + nx },
        { lat: p2.lat - ny - offset, lng: p2.lng - nx },
        { lat: p1.lat - ny - offset, lng: p1.lng - nx },
      ];
    }
    
    // 3+ points - calculate convex hull and expand
    const hull = convexHull([...points]);
    return expandHull(hull, 250); // 250m padding
  }, [campers]);

  // Create, update or remove polygon
  useEffect(() => {
    // Cleanup function to remove polygon
    const cleanup = () => {
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
        polygonRef.current = null;
      }
    };

    // If conditions not met, cleanup and return
    if (!map || !showZone || zonePath.length < 3) {
      cleanup();
      return cleanup;
    }

    // If polygon exists, update it
    if (polygonRef.current) {
      polygonRef.current.setPath(zonePath);
      polygonRef.current.setOptions({
        fillColor: color,
        fillOpacity: isSelected ? 0.35 : 0.15,
        strokeColor: color,
        strokeOpacity: isSelected ? 1 : 0.6,
        strokeWeight: isSelected ? 3 : 2,
        zIndex: isSelected ? 2 : 1,
      });
    } else {
      // Create new polygon
      const newPolygon = new google.maps.Polygon({
        paths: zonePath,
        fillColor: color,
        fillOpacity: isSelected ? 0.35 : 0.15,
        strokeColor: color,
        strokeOpacity: isSelected ? 1 : 0.6,
        strokeWeight: isSelected ? 3 : 2,
        clickable: true,
        zIndex: isSelected ? 2 : 1,
      });
      
      newPolygon.setMap(map);
      
      // Add click handler
      newPolygon.addListener('click', () => {
        if (onZoneClick) {
          onZoneClick(busNumber);
        }
      });
      
      polygonRef.current = newPolygon;
    }

    return cleanup;
  }, [map, zonePath, showZone, color, isSelected, onZoneClick, busNumber]);

  return null; // Polygon is rendered directly on the map, not as React component
};

export default BusZonePolygon;

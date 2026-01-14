/* global google */
import { useEffect, useRef, useMemo } from 'react';
import { useMap } from '@vis.gl/react-google-maps';

/**
 * Calculate convex hull using Graham scan algorithm
 * Returns points forming a tight boundary around the input points
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
  const pointsCopy = [...points];
  [pointsCopy[0], pointsCopy[start]] = [pointsCopy[start], pointsCopy[0]];
  const pivot = pointsCopy[0];

  // Sort points by polar angle with pivot
  const sortedPoints = pointsCopy.slice(1).sort((a, b) => {
    const angleA = Math.atan2(a.lat - pivot.lat, a.lng - pivot.lng);
    const angleB = Math.atan2(b.lat - pivot.lat, b.lng - pivot.lng);
    if (angleA !== angleB) return angleA - angleB;
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
 * Add minimal padding to hull points
 * Uses a fixed small padding that creates a tight boundary
 */
function addMinimalPadding(hull, paddingMeters = 50) {
  if (hull.length < 3) return hull;
  
  // Convert meters to degrees (approximately)
  // At ~40° latitude (NY area), 1 degree lat ≈ 111km, 1 degree lng ≈ 85km
  const avgLat = hull.reduce((sum, p) => sum + p.lat, 0) / hull.length;
  const latPadding = paddingMeters / 111000;
  const lngPadding = paddingMeters / (111000 * Math.cos(avgLat * Math.PI / 180));
  
  // Calculate centroid
  const centroid = {
    lat: hull.reduce((sum, p) => sum + p.lat, 0) / hull.length,
    lng: hull.reduce((sum, p) => sum + p.lng, 0) / hull.length
  };
  
  // Move each point slightly away from centroid
  return hull.map(point => {
    const dx = point.lng - centroid.lng;
    const dy = point.lat - centroid.lat;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    if (dist === 0) {
      // Point is at centroid, expand in all directions
      return { lat: point.lat + latPadding, lng: point.lng + lngPadding };
    }
    
    // Normalize direction and add fixed padding
    const nx = dx / dist;
    const ny = dy / dist;
    
    return {
      lat: point.lat + ny * latPadding,
      lng: point.lng + nx * lngPadding
    };
  });
}

/**
 * Create a small polygon for a single point
 */
function createSinglePointPolygon(point, radiusMeters = 80) {
  const latOffset = radiusMeters / 111000;
  const lngOffset = radiusMeters / (111000 * Math.cos(point.lat * Math.PI / 180));
  
  // Create octagon shape
  const sides = 8;
  const polygon = [];
  for (let i = 0; i < sides; i++) {
    const angle = (i / sides) * 2 * Math.PI;
    polygon.push({
      lat: point.lat + latOffset * Math.sin(angle),
      lng: point.lng + lngOffset * Math.cos(angle)
    });
  }
  return polygon;
}

/**
 * Create a tight capsule shape for two points
 */
function createTwoPointPolygon(p1, p2, widthMeters = 60) {
  const latOffset = widthMeters / 111000;
  const lngOffset = widthMeters / (111000 * Math.cos((p1.lat + p2.lat) / 2 * Math.PI / 180));
  
  const dx = p2.lng - p1.lng;
  const dy = p2.lat - p1.lat;
  const len = Math.sqrt(dx * dx + dy * dy);
  
  if (len === 0) return createSinglePointPolygon(p1, widthMeters);
  
  // Perpendicular direction
  const nx = -dy / len;
  const ny = dx / len;
  
  // Create capsule shape
  return [
    { lat: p1.lat + ny * latOffset, lng: p1.lng + nx * lngOffset },
    { lat: p1.lat - ny * latOffset, lng: p1.lng - nx * lngOffset },
    { lat: p2.lat - ny * latOffset, lng: p2.lng - nx * lngOffset },
    { lat: p2.lat + ny * latOffset, lng: p2.lng + nx * lngOffset },
  ];
}

/**
 * BusZonePolygon - Renders a TIGHT polygon zone around pins for a specific bus
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

  // Calculate zone path from campers - TIGHT FIT
  const zonePath = useMemo(() => {
    if (!campers || campers.length === 0) return [];
    
    // Get all unique locations for this bus (filter out invalid coords)
    const points = campers
      .filter(c => c.location?.latitude && c.location?.longitude && 
                   c.location.latitude !== 0 && c.location.longitude !== 0)
      .map(c => ({
        lat: c.location.latitude,
        lng: c.location.longitude
      }));
    
    // Remove duplicate points (same location)
    const uniquePoints = [];
    const seen = new Set();
    for (const p of points) {
      const key = `${p.lat.toFixed(5)}_${p.lng.toFixed(5)}`;
      if (!seen.has(key)) {
        seen.add(key);
        uniquePoints.push(p);
      }
    }
    
    if (uniquePoints.length === 0) return [];
    
    if (uniquePoints.length === 1) {
      // Single point - small octagon (80m radius)
      return createSinglePointPolygon(uniquePoints[0], 80);
    }
    
    if (uniquePoints.length === 2) {
      // Two points - tight capsule shape (60m width)
      return createTwoPointPolygon(uniquePoints[0], uniquePoints[1], 60);
    }
    
    // 3+ points - calculate tight convex hull with minimal padding (50m)
    const hull = convexHull(uniquePoints);
    return addMinimalPadding(hull, 50);
  }, [campers]);

  // Create, update or remove polygon
  useEffect(() => {
    const cleanup = () => {
      if (polygonRef.current) {
        polygonRef.current.setMap(null);
        polygonRef.current = null;
      }
    };

    if (!map || !showZone || zonePath.length < 3) {
      cleanup();
      return cleanup;
    }

    if (polygonRef.current) {
      // Update existing polygon
      polygonRef.current.setPath(zonePath);
      polygonRef.current.setOptions({
        fillColor: color,
        fillOpacity: isSelected ? 0.3 : 0.12,
        strokeColor: color,
        strokeOpacity: isSelected ? 0.9 : 0.5,
        strokeWeight: isSelected ? 2 : 1.5,
        zIndex: isSelected ? 2 : 1,
      });
    } else {
      // Create new polygon
      const newPolygon = new google.maps.Polygon({
        paths: zonePath,
        fillColor: color,
        fillOpacity: isSelected ? 0.3 : 0.12,
        strokeColor: color,
        strokeOpacity: isSelected ? 0.9 : 0.5,
        strokeWeight: isSelected ? 2 : 1.5,
        clickable: true,
        zIndex: isSelected ? 2 : 1,
      });
      
      newPolygon.setMap(map);
      
      newPolygon.addListener('click', () => {
        if (onZoneClick) {
          onZoneClick(busNumber);
        }
      });
      
      polygonRef.current = newPolygon;
    }

    return cleanup;
  }, [map, zonePath, showZone, color, isSelected, onZoneClick, busNumber]);

  return null;
};

export default BusZonePolygon;

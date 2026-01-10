from typing import List, Dict, Tuple, Optional
import numpy as np
from sklearn.cluster import DBSCAN
from geopy.distance import geodesic
from collections import defaultdict
import logging
from bus_config import get_bus_capacity

logger = logging.getLogger(__name__)

class RouteOptimizer:
    def __init__(self, num_buses: int = 33):
        self.num_buses = num_buses
        self.bus_capacities = {}
    
    def calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calculate distance in miles between two lat/lng points"""
        return geodesic(point1, point2).miles
    
    def cluster_addresses(self, addresses: List[Dict]) -> List[int]:
        """Cluster addresses using DBSCAN for geographic proximity"""
        if not addresses:
            return []
        
        # Extract coordinates
        coords = np.array([[addr['lat'], addr['lng']] for addr in addresses])
        
        # DBSCAN clustering
        # eps=0.02 is approximately 1.4 miles
        # min_samples=2 requires at least 2 campers in proximity
        clustering = DBSCAN(eps=0.02, min_samples=2, metric='haversine').fit(np.radians(coords))
        
        return clustering.labels_
    
    def find_optimal_bus(self, camper_address: Dict, existing_routes: Dict[int, List[Dict]]) -> int:
        """Find the optimal bus for a new camper based on route proximity and capacity"""
        camper_coords = (camper_address['lat'], camper_address['lng'])
        
        best_bus = None
        min_avg_distance = float('inf')
        
        for bus_num, route in existing_routes.items():
            bus_number_str = f"Bus #{bus_num:02d}"
            max_capacity = get_bus_capacity(bus_number_str)
            
            # Check capacity
            if len(route) >= max_capacity:
                continue
            
            # Calculate average distance to all stops on this route
            if route:
                distances = [
                    self.calculate_distance(camper_coords, (stop['lat'], stop['lng']))
                    for stop in route
                ]
                avg_distance = sum(distances) / len(distances)
                
                # Prefer buses with closer average distance
                if avg_distance < min_avg_distance:
                    min_avg_distance = avg_distance
                    best_bus = bus_num
        
        # If no suitable bus found, assign to first available bus
        if best_bus is None:
            for bus_num in range(1, self.num_buses + 1):
                bus_number_str = f"Bus #{bus_num:02d}"
                max_capacity = get_bus_capacity(bus_number_str)
                if len(existing_routes.get(bus_num, [])) < max_capacity:
                    best_bus = bus_num
                    break
        
        return best_bus if best_bus else 1
    
    def optimize_routes(self, campers: List[Dict]) -> Dict[int, List[Dict]]:
        """Optimize bus routes for all campers using clustering and proximity"""
        if not campers:
            return {}
        
        # Prepare address data
        addresses = []
        for camper in campers:
            if camper.get('location', {}).get('latitude') and camper.get('location', {}).get('longitude'):
                addresses.append({
                    'camper_id': camper['_id'],
                    'lat': camper['location']['latitude'],
                    'lng': camper['location']['longitude'],
                    'address': camper['location'].get('address', ''),
                    'first_name': camper.get('first_name', ''),
                    'last_name': camper.get('last_name', '')
                })
        
        if not addresses:
            return {}
        
        # Cluster addresses
        labels = self.cluster_addresses(addresses)
        
        # Group by cluster
        clusters = defaultdict(list)
        for addr, label in zip(addresses, labels):
            clusters[label].append(addr)
        
        # Assign buses to clusters
        bus_routes = {}
        current_bus = 1
        
        for cluster_id, cluster_addresses in sorted(clusters.items()):
            # Skip noise points (label = -1)
            if cluster_id == -1:
                # Assign noise points individually
                for addr in cluster_addresses:
                    if current_bus <= self.num_buses:
                        if current_bus not in bus_routes:
                            bus_routes[current_bus] = []
                        
                        if len(bus_routes[current_bus]) < self.max_capacity_per_bus:
                            bus_routes[current_bus].append(addr)
                        else:
                            current_bus += 1
                            if current_bus <= self.num_buses:
                                bus_routes[current_bus] = [addr]
                continue
            
            # Assign cluster to bus
            if current_bus <= self.num_buses:
                bus_routes[current_bus] = cluster_addresses[:self.max_capacity_per_bus]
                
                # If cluster is larger than capacity, split across multiple buses
                remaining = cluster_addresses[self.max_capacity_per_bus:]
                while remaining and current_bus < self.num_buses:
                    current_bus += 1
                    chunk = remaining[:self.max_capacity_per_bus]
                    bus_routes[current_bus] = chunk
                    remaining = remaining[self.max_capacity_per_bus:]
                
                current_bus += 1
        
        logger.info(f"Optimized routes for {len(campers)} campers across {len(bus_routes)} buses")
        return bus_routes
    
    def calculate_route_efficiency(self, route: List[Dict]) -> float:
        """Calculate efficiency score for a route (lower is better)"""
        if len(route) < 2:
            return 0.0
        
        total_distance = 0
        for i in range(len(route) - 1):
            dist = self.calculate_distance(
                (route[i]['lat'], route[i]['lng']),
                (route[i+1]['lat'], route[i+1]['lng'])
            )
            total_distance += dist
        
        # Average distance per stop
        return total_distance / len(route)
    
    def rebalance_routes(self, bus_routes: Dict[int, List[Dict]]) -> Dict[int, List[Dict]]:
        """Rebalance routes to improve efficiency"""
        improved_routes = {}
        
        for bus_num, route in bus_routes.items():
            if not route:
                continue
            
            # Sort stops by proximity using nearest neighbor
            sorted_route = [route[0]]
            remaining = route[1:]
            
            while remaining:
                last_stop = sorted_route[-1]
                nearest_idx = 0
                min_dist = float('inf')
                
                for idx, stop in enumerate(remaining):
                    dist = self.calculate_distance(
                        (last_stop['lat'], last_stop['lng']),
                        (stop['lat'], stop['lng'])
                    )
                    if dist < min_dist:
                        min_dist = dist
                        nearest_idx = idx
                
                sorted_route.append(remaining.pop(nearest_idx))
            
            improved_routes[bus_num] = sorted_route
        
        return improved_routes
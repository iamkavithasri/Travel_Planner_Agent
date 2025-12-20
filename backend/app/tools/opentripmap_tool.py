import requests
from typing import List, Dict, Tuple, Optional
from app.config import settings
import time

class OpenTripMapTool:
    """Fetch tourist attractions - FULLY GENERIC for any city"""
    
    def __init__(self):
        self.api_key = settings.OPENTRIPMAP_API_KEY
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.overpass_url = "http://overpass-api.de/api/interpreter"
    
    def get_city_coordinates(self, city_name: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Get coordinates for ANY city using Nominatim
        Returns: (lat, lon, country)
        """
        try:
            response = requests.get(
                self.nominatim_url,
                params={
                    "q": city_name,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1  # Get country info
                },
                headers={"User-Agent": "TravelPlannerAgent/1.0"},
                timeout=10
            )
            
            time.sleep(1)  # Rate limit
            
            data = response.json()
            if data:
                result = data[0]
                lat = float(result["lat"])
                lon = float(result["lon"])
                
                # Extract country for cost estimation
                address = result.get("address", {})
                country = address.get("country", "Unknown")
                
                return lat, lon, country
            
            return None, None, None
            
        except Exception as e:
            print(f"Geocoding error for {city_name}: {e}")
            return None, None, None
    
    def get_activities_osm(self, lat: float, lon: float, preferences: List[str], 
                          radius: int = 5000) -> List[Dict]:
        """Get activities using OpenStreetMap - works for ANY location"""
        
        # Map preferences to OSM tags
        tag_mapping = {
            "culture": '["tourism"~"museum|gallery|artwork|theatre"]',
            "food": '["amenity"~"restaurant|cafe|fast_food"]',
            "nature": '["leisure"~"park|garden|beach_resort"]["natural"~"beach|waterfall"]',
            "history": '["historic"~"monument|castle|archaeological_site|memorial"]',
            "shopping": '["shop"~"mall|department_store"]["tourism"="attraction"]["amenity"="marketplace"]',
            "entertainment": '["amenity"~"cinema|nightclub|theatre"]["leisure"~"amusement_arcade"]',
            "sightseeing": '["tourism"~"attraction|viewpoint|artwork"]',
            "adventure": '["leisure"~"sports_centre|water_park"]["tourism"="theme_park"]',
            "religious": '["amenity"~"place_of_worship"]["religion"~"hindu|buddhist|jain|christian|muslim"]',
            "nightlife": '["amenity"~"bar|pub|nightclub"]',
            "temple": '["amenity"="place_of_worship"]["religion"~"hindu|buddhist|jain"]'
        }
        
        # Build query for ALL matching preferences
        queries = []
        for pref in preferences:
            pref_lower = pref.lower()
            if pref_lower in tag_mapping:
                queries.append(f'node{tag_mapping[pref_lower]}(around:{radius},{lat},{lon});')
                queries.append(f'way{tag_mapping[pref_lower]}(around:{radius},{lat},{lon});')
        
        # Default fallback - get popular attractions
        if not queries:
            queries.append(f'node["tourism"](around:{radius},{lat},{lon});')
            queries.append(f'way["tourism"](around:{radius},{lat},{lon});')
        
        overpass_query = f"""
        [out:json][timeout:30];
        (
          {' '.join(queries)}
        );
        out body 150;
        """
        
        try:
            response = requests.post(
                self.overpass_url,
                data={"data": overpass_query},
                timeout=35
            )
            
            data = response.json()
            activities = []
            seen_names = set()  # Avoid duplicates
            
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                name = tags.get("name", tags.get("alt_name", ""))
                
                if not name or name in seen_names:
                    continue
                
                seen_names.add(name)
                
                activity_type = (
                    tags.get("tourism") or 
                    tags.get("amenity") or 
                    tags.get("leisure") or 
                    tags.get("historic") or
                    tags.get("natural") or
                    "attraction"
                )
                
                # Get coordinates
                if "lat" in element:
                    act_lat, act_lon = element["lat"], element["lon"]
                elif "center" in element:
                    act_lat, act_lon = element["center"]["lat"], element["center"]["lon"]
                else:
                    continue
                
                activities.append({
                    "name": name,
                    "type": activity_type,
                    "lat": act_lat,
                    "lon": act_lon,
                    "opening_hours": tags.get("opening_hours", "Unknown"),
                    "website": tags.get("website", ""),
                    "cuisine": tags.get("cuisine", ""),  # For restaurants
                    "fee": tags.get("fee", "")  # yes/no/amount
                })
            
            return activities
            
        except Exception as e:
            print(f"OSM API error: {e}")
            return []
    
    def get_activities(self, city: str, preferences: List[str]) -> Tuple[List[Dict], Optional[str]]:
        """
        Main method - works for ANY city worldwide
        Returns: (activities, country)
        """
        # Step 1: Geocode any city
        lat, lon, country = self.get_city_coordinates(city)
        
        if not lat or not lon:
            print(f"Could not find coordinates for {city}")
            return [], None
        
        print(f"Found {city} at ({lat}, {lon}) in {country}")
        
        # Step 2: Get activities
        activities = self.get_activities_osm(lat, lon, preferences, radius=5000)
        
        # Step 3: If too few results, expand search radius
        if len(activities) < 15:
            print(f"Only {len(activities)} activities found, expanding search...")
            activities = self.get_activities_osm(lat, lon, preferences, radius=10000)
        
        return activities, country
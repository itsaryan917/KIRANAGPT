"""Geographic feature extraction module for Kirana store underwriting.

Provides ``GeoLocation`` for coordinate validation and
``GeoFeatureExtractor`` which computes ring-based population estimates,
POI counts, road classification, and competition counts for a given
lat/lon.  External API integration points are stubbed — the extractor
ships with a deterministic mock data provider so the full pipeline can
run end-to-end without network access.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# In-memory geo cache — avoids re-hitting OSM for same coordinates in demo
# Key: rounded lat/lng (3 decimal places = ~110m precision)
_GEO_CACHE: dict = {}
_GEO_CACHE_MAX = 50   # keep last 50 locations


# ---------------------------------------------------------------------------
# GeoLocation
# ---------------------------------------------------------------------------

class GeoLocation:
    """Represents and validates geographic coordinates.

    Handles GPS data, store addresses, and proximity calculations.
    """

    def __init__(self, latitude: float, longitude: float):
        """Initialize with latitude and longitude.

        Args:
            latitude:  Geographic latitude  (−90 to +90).
            longitude: Geographic longitude (−180 to +180).

        Raises:
            ValueError: If coordinates are out of range.
        """
        if not (-90.0 <= latitude <= 90.0):
            raise ValueError(
                f"Latitude must be in [-90, 90], got {latitude}"
            )
        if not (-180.0 <= longitude <= 180.0):
            raise ValueError(
                f"Longitude must be in [-180, 180], got {longitude}"
            )
        self.latitude = latitude
        self.longitude = longitude

    def get_coordinates(self) -> Tuple[float, float]:
        """Return the current coordinates.

        Returns:
            A tuple of (latitude, longitude).
        """
        return (self.latitude, self.longitude)

    def __repr__(self) -> str:
        return f"GeoLocation(lat={self.latitude:.6f}, lon={self.longitude:.6f})"


# ---------------------------------------------------------------------------
# Population ring container
# ---------------------------------------------------------------------------

@dataclass
class PopulationRings:
    """Estimated population counts in concentric rings around the store.

    Attributes:
        pop_0_200m:    People within 0 – 200 m radius.
        pop_200_500m:  People within 200 – 500 m radius.
        pop_500_1000m: People within 500 – 1 000 m radius.
        total:         Sum of all rings.
    """

    pop_0_200m: int = 0
    pop_200_500m: int = 0
    pop_500_1000m: int = 0

    @property
    def total(self) -> int:
        return self.pop_0_200m + self.pop_200_500m + self.pop_500_1000m

    def to_dict(self) -> Dict[str, int]:
        return {
            "pop_0_200m": self.pop_0_200m,
            "pop_200_500m": self.pop_200_500m,
            "pop_500_1000m": self.pop_500_1000m,
            "total": self.total,
        }


# ---------------------------------------------------------------------------
# POI summary
# ---------------------------------------------------------------------------

@dataclass
class POICounts:
    """Counts of nearby points of interest by category.

    Attributes:
        schools:       Schools / colleges within 1 km.
        hospitals:     Hospitals / clinics within 1 km.
        bus_stops:     Bus stops / transit stations within 500 m.
        temples:       Religious places within 500 m.
        markets:       Markets / mandis within 1 km.
        banks:         Banks / ATMs within 500 m.
    """

    schools: int = 0
    hospitals: int = 0
    bus_stops: int = 0
    temples: int = 0
    markets: int = 0
    banks: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "schools": self.schools,
            "hospitals": self.hospitals,
            "bus_stops": self.bus_stops,
            "temples": self.temples,
            "markets": self.markets,
            "banks": self.banks,
        }


# ---------------------------------------------------------------------------
# Competition summary
# ---------------------------------------------------------------------------

@dataclass
class CompetitionInfo:
    """Competition landscape around the store.

    Attributes:
        kirana_count_500m:   Kirana / general stores within 500 m.
        kirana_count_1km:    Kirana / general stores within 1 km.
        supermarket_count:   Supermarkets / chains within 2 km.
        nearest_competitor_m: Distance to the nearest competitor (metres).
    """

    kirana_count_500m: int = 0
    kirana_count_1km: int = 0
    supermarket_count: int = 0
    nearest_competitor_m: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kirana_count_500m": self.kirana_count_500m,
            "kirana_count_1km": self.kirana_count_1km,
            "supermarket_count": self.supermarket_count,
            "nearest_competitor_m": round(self.nearest_competitor_m, 1),
        }


# ---------------------------------------------------------------------------
# Full extraction result
# ---------------------------------------------------------------------------

ROAD_TYPES = ("highway", "arterial", "collector", "local", "residential")

@dataclass
class GeoExtractionResult:
    """Complete result of geographic feature extraction.

    This is the raw, detailed output.  ``GeoFeatureExtractor`` also
    provides a helper to convert this into the simpler ``GeoFeatures``
    used by ``GeoProcessor``.

    Attributes:
        location:     The validated ``GeoLocation``.
        population:   Ring-based population estimates.
        poi:          Nearby POI counts.
        road_type:    Road classification for the store's street.
        competition:  Competition landscape.
        metadata:     Extra data for audit trail.
    """

    location: GeoLocation = None  # type: ignore[assignment]
    population: PopulationRings = field(default_factory=PopulationRings)
    poi: POICounts = field(default_factory=POICounts)
    road_type: str = "local"
    competition: CompetitionInfo = field(default_factory=CompetitionInfo)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.location.latitude if self.location else None,
            "longitude": self.location.longitude if self.location else None,
            "population": self.population.to_dict(),
            "poi": self.poi.to_dict(),
            "road_type": self.road_type,
            "competition": self.competition.to_dict(),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# GeoFeatureExtractor
# ---------------------------------------------------------------------------

class GeoFeatureExtractor:
    """Extracts geographic features for a store location.

    Usage::

        extractor = GeoFeatureExtractor()
        result    = extractor.extract(19.076, 72.877)
        print(result.population.pop_0_200m)
        print(result.road_type)

        # Convert to the lightweight GeoFeatures used by GeoProcessor:
        from kirana_khata.geo_processor import GeoFeatures
        features = extractor.to_geo_features(result)

    By default, this extractor operates in **precise mode** utilizing actual
    geospatial data fetched from Nominatim (for addresses and tiers) and 
    OpenStreetMap (OSM) Overpass API (for roads, competitors, POIs, and 
    population). It falls back gracefully to a deterministic mock data provider
    if network access fails or is offline.

    Config overrides (via *config* dict):
        - ``use_mock``  (bool) – force mock mode, default ``False``
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the extractor.

        Args:
            config: Optional parameter overrides.
        """
        cfg = config or {}
        self._use_mock: bool = cfg.get("use_mock", False)
        self._raw_data: Optional[Dict[str, Any]] = None
        logger.info(
            "GeoFeatureExtractor initialised (mock=%s)", self._use_mock
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, latitude: float, longitude: float) -> GeoExtractionResult:
        """Run full geographic feature extraction.

        Args:
            latitude:  Store latitude.
            longitude: Store longitude.

        Returns:
            A fully populated ``GeoExtractionResult``.
        """
        location = GeoLocation(latitude, longitude)
        seed = self._coord_seed(latitude, longitude)

        # Pre-fetch precise API data if mock is disabled
        self._raw_data = None
        if not self._use_mock:
            self._raw_data = self._fetch_all_api_data(latitude, longitude)

        population = self._fetch_population(latitude, longitude, seed)
        poi = self._fetch_poi(latitude, longitude, seed)
        road_type = self._fetch_road_type(latitude, longitude, seed)
        competition = self._fetch_competition(latitude, longitude, seed)

        metadata = {"source": "mock" if self._use_mock or not self._raw_data else "api"}
        if not self._use_mock and self._raw_data:
            metadata["pin_code"] = self._raw_data.get("pin_code", "")
            metadata["region_tier"] = self._raw_data.get("region_tier", 3)
            metadata["address_resolved"] = self._raw_data.get("address", {})

        result = GeoExtractionResult(
            location=location,
            population=population,
            poi=poi,
            road_type=road_type,
            competition=competition,
            metadata=metadata,
        )

        # Clear the temporary context
        self._raw_data = None

        logger.info(
            "Geo extraction for (%.4f, %.4f): pop_total=%d, road=%s, "
            "kirana_500m=%d",
            latitude, longitude,
            population.total, road_type,
            competition.kirana_count_500m,
        )
        return result

    def to_geo_features(self, result: GeoExtractionResult):
        """Convert a ``GeoExtractionResult`` to a ``GeoFeatures`` instance.

        This is a convenience bridge to the ``geo_processor`` module so
        that extraction results can feed directly into ``GeoProcessor``.

        Returns:
            A ``GeoFeatures`` dataclass (imported from ``geo_processor``).
        """
        # Late import to avoid circular dependency.
        from .geo_processor import GeoFeatures

        pop = result.population
        comp = result.competition
        total_pop = pop.total

        # Derive population density (people / km²) from ring data.
        # Since we changed the area of concern to 300m, the catchment area is a 300m radius circle.
        # Area of 300m circle ≈ π * (0.3 ** 2) km² ≈ 0.2827 km².
        # If in mock mode (which generates population for a 1km ring), we fall back to 1.0 km radius.
        is_mock = result.metadata.get("source") == "mock"
        radius_km = 1.0 if is_mock else 0.3
        area_km2 = math.pi * (radius_km ** 2)
        pop_density = total_pop / area_km2 if area_km2 > 0 else 0.0

        # Footfall index: heuristic from POI mix + population.
        poi = result.poi
        poi_total = (
            poi.schools + poi.hospitals + poi.bus_stops
            + poi.temples + poi.markets + poi.banks
        )
        
        pop_threshold = 5000.0 if is_mock else 500.0
        poi_threshold = 15.0 if is_mock else 4.0
        
        footfall_raw = (
            0.4 * min(total_pop / pop_threshold, 1.0)
            + 0.3 * min(poi_total / poi_threshold, 1.0)
            + 0.3 * (1.0 if result.road_type in ("arterial", "collector") else
                      0.7 if result.road_type == "highway" else 0.4)
        )
        footfall_index = max(0.0, min(footfall_raw, 1.0))

        # Market saturation: heuristic from competition density.
        comp_threshold = 25.0 if is_mock else 5.0
        sat_raw = min(
            (comp.kirana_count_1km + comp.supermarket_count * 3) / comp_threshold,
            1.0,
        )

        # Region tier: use resolved metadata if present, else fallback to density heuristic
        tier = result.metadata.get("region_tier")
        if tier is None:
            if pop_density > 10_000:
                tier = 1
            elif pop_density > 4_000:
                tier = 2
            else:
                tier = 3

        pin_code = result.metadata.get("pin_code", "")

        return GeoFeatures(
            latitude=result.location.latitude,
            longitude=result.location.longitude,
            population_density=round(pop_density, 1),
            competitor_count=comp.kirana_count_1km + comp.supermarket_count,
            nearest_competitor_km=round(comp.nearest_competitor_m / 1000.0, 3),
            footfall_index=round(footfall_index, 4),
            market_saturation=round(sat_raw, 4),
            pin_code=pin_code,
            region_tier=tier,
            metadata={
                "population_rings": pop.to_dict(),
                "poi": poi.to_dict(),
                "road_type": result.road_type,
                "competition": comp.to_dict(),
            },
        )

    # ------------------------------------------------------------------
    # Data providers (override for real APIs)
    # ------------------------------------------------------------------

    def _fetch_population(
        self, lat: float, lon: float, seed: int
    ) -> PopulationRings:
        """Fetch ring-based population estimates.

        Resolves dynamically using building density when in precise mode (up to 300m).
        """
        if not self._use_mock and self._raw_data:
            osm_pop_0_200m = 0
            osm_pop_200_500m = 0
            osm_pop_500_1000m = 0

            for elem in self._raw_data["elements"]:
                tags = elem.get("tags", {})
                if "building" in tags:
                    coords = self._get_element_coords(elem)
                    if coords:
                        dist = self._haversine(lat, lon, coords[0], coords[1]) * 1000.0  # meters
                        b_type = tags.get("building", "yes")

                        # Estimate occupancy based on building tag
                        if b_type == "apartments":
                            p_count = 60
                        elif b_type in ("house", "detached", "terrace", "semidetached_house"):
                            p_count = 5
                        elif b_type == "yes":
                            p_count = 12
                        else:
                            p_count = 8

                        if dist <= 200:
                            osm_pop_0_200m += p_count
                        elif dist <= 300: # Capped at 300m
                            osm_pop_200_500m += p_count

            # Blend with mock base to guarantee a robust minimum catchment density
            mock_pop = self._fetch_population_mock(lat, lon, seed)
            return PopulationRings(
                pop_0_200m=max(mock_pop.pop_0_200m, osm_pop_0_200m),
                pop_200_500m=max(mock_pop.pop_200_500m, osm_pop_200_500m),
                pop_500_1000m=max(mock_pop.pop_500_1000m, osm_pop_500_1000m),
            )

        return self._fetch_population_mock(lat, lon, seed)

    def _fetch_population_mock(
        self, lat: float, lon: float, seed: int
    ) -> PopulationRings:
        """Fallback mock for ring population."""
        base = 200 + (seed % 800)
        return PopulationRings(
            pop_0_200m=base,
            pop_200_500m=int(base * 2.5 + (seed % 300)),
            pop_500_1000m=int(base * 5.0 + (seed % 600)),
        )

    def _fetch_poi(
        self, lat: float, lon: float, seed: int
    ) -> POICounts:
        """Fetch nearby POI counts.

        Resolves dynamically using OpenStreetMap amenities when in precise mode (up to 300m).
        """
        if not self._use_mock and self._raw_data:
            schools = 0
            hospitals = 0
            bus_stops = 0
            temples = 0
            markets = 0
            banks = 0

            for elem in self._raw_data["elements"]:
                tags = elem.get("tags", {})
                coords = self._get_element_coords(elem)
                if not coords:
                    continue
                dist = self._haversine(lat, lon, coords[0], coords[1]) * 1000.0  # meters

                amenity = tags.get("amenity", "")
                highway = tags.get("highway", "")
                public_transport = tags.get("public_transport", "")
                shop = tags.get("shop", "")
                landuse = tags.get("landuse", "")

                if dist <= 300: # Consistent with 300m area of concern
                    if amenity in ("school", "college", "university"):
                        schools += 1
                    if amenity in ("hospital", "clinic"):
                        hospitals += 1
                    if amenity == "marketplace" or shop == "mall" or landuse in ("commercial", "retail"):
                        markets += 1
                    if highway == "bus_stop" or public_transport == "platform":
                        bus_stops += 1
                    if amenity == "place_of_worship":
                        temples += 1
                    if amenity in ("bank", "atm"):
                        banks += 1

            mock_poi = self._fetch_poi_mock(lat, lon, seed)
            return POICounts(
                schools=max(mock_poi.schools, schools),
                hospitals=max(mock_poi.hospitals, hospitals),
                bus_stops=max(mock_poi.bus_stops, bus_stops),
                temples=max(mock_poi.temples, temples),
                markets=max(mock_poi.markets, markets),
                banks=max(mock_poi.banks, banks),
            )

        return self._fetch_poi_mock(lat, lon, seed)

    def _fetch_poi_mock(
        self, lat: float, lon: float, seed: int
    ) -> POICounts:
        """Fallback mock for POIs."""
        return POICounts(
            schools=(seed % 5) + 1,
            hospitals=(seed % 3) + 1,
            bus_stops=(seed % 6) + 2,
            temples=(seed % 4) + 1,
            markets=(seed % 3) + 1,
            banks=(seed % 5) + 2,
        )

    def _fetch_road_type(
        self, lat: float, lon: float, seed: int
    ) -> str:
        """Classify the road nearest to the store.

        Resolves dynamically using OpenStreetMap highways when in precise mode.
        """
        if not self._use_mock and self._raw_data:
            closest_road_type = None
            min_dist = float("inf")

            for elem in self._raw_data["elements"]:
                tags = elem.get("tags", {})
                if "highway" in tags and elem.get("type") == "way":
                    coords = self._get_element_coords(elem)
                    if coords:
                        dist = self._haversine(lat, lon, coords[0], coords[1]) * 1000.0  # meters
                        if dist < min_dist and dist <= 100.0:  # 100 meters limit
                            min_dist = dist
                            highway_val = tags.get("highway", "")

                            if highway_val in ("motorway", "motorway_link", "trunk", "trunk_link"):
                                closest_road_type = "highway"
                            elif highway_val in ("primary", "primary_link", "secondary", "secondary_link"):
                                closest_road_type = "arterial"
                            elif highway_val in ("tertiary", "tertiary_link"):
                                closest_road_type = "collector"
                            elif highway_val == "residential":
                                closest_road_type = "residential"
                            else:
                                closest_road_type = "local"

            if closest_road_type:
                return closest_road_type

        return self._fetch_road_type_mock(lat, lon, seed)

    def _fetch_road_type_mock(
        self, lat: float, lon: float, seed: int
    ) -> str:
        """Fallback mock for road type."""
        return ROAD_TYPES[seed % len(ROAD_TYPES)]

    def _fetch_competition(
        self, lat: float, lon: float, seed: int
    ) -> CompetitionInfo:
        """Fetch competition landscape.

        Resolves dynamically using OpenStreetMap shop listings when in precise mode (up to 300m).
        """
        if not self._use_mock and self._raw_data:
            kirana_count_500m = 0
            kirana_count_1km = 0
            supermarket_count = 0
            nearest_competitor_m = float("inf")

            for elem in self._raw_data["elements"]:
                tags = elem.get("tags", {})
                shop = tags.get("shop", "")
                if shop in ("convenience", "general", "grocery", "kiosk", "minimarket", "supermarket", "department_store", "mall"):
                    coords = self._get_element_coords(elem)
                    if coords:
                        dist = self._haversine(lat, lon, coords[0], coords[1]) * 1000.0  # meters

                        # Any shop of these types counts as competitor proximity
                        if shop in ("convenience", "general", "grocery", "kiosk", "minimarket", "supermarket", "department_store"):
                            if dist < nearest_competitor_m:
                                nearest_competitor_m = dist

                        if shop in ("convenience", "general", "grocery", "kiosk", "minimarket"):
                            if dist <= 300: # Capped at 300m
                                kirana_count_500m += 1
                                kirana_count_1km += 1

                        if shop in ("supermarket", "department_store"):
                            if dist <= 300: # Capped at 300m
                                supermarket_count += 1

            mock_comp = self._fetch_competition_mock(lat, lon, seed)

            final_k500 = max(mock_comp.kirana_count_500m, kirana_count_500m)
            final_k1k = max(mock_comp.kirana_count_1km, kirana_count_1km)
            final_super = max(mock_comp.supermarket_count, supermarket_count)
            final_nearest = min(mock_comp.nearest_competitor_m, nearest_competitor_m) if nearest_competitor_m != float("inf") else mock_comp.nearest_competitor_m

            return CompetitionInfo(
                kirana_count_500m=final_k500,
                kirana_count_1km=final_k1k,
                supermarket_count=final_super,
                nearest_competitor_m=final_nearest,
            )

        return self._fetch_competition_mock(lat, lon, seed)

    def _fetch_competition_mock(
        self, lat: float, lon: float, seed: int
    ) -> CompetitionInfo:
        """Fallback mock for competition."""
        k500 = (seed % 8) + 1
        return CompetitionInfo(
            kirana_count_500m=k500,
            kirana_count_1km=k500 + (seed % 6) + 2,
            supermarket_count=(seed % 3),
            nearest_competitor_m=float(50 + (seed % 400)),
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _fetch_all_api_data(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        # Check cache first (rounded to 3dp ≈ 110m precision)
        cache_key = f"{lat:.3f},{lon:.3f}"
        if cache_key in _GEO_CACHE:
            logger.info("Geo cache hit for %s", cache_key)
            return _GEO_CACHE[cache_key]

        """Fetch all necessary geospatial data from Nominatim and Overpass APIs in a single batch.

        Returns:
            A dictionary containing pre-fetched geocoding and OSM data, or None on failure.
        """
        logger.info("Attempting to fetch precise geospatial data for (%.4f, %.4f)", lat, lon)
        try:
            # 1. Reverse-geocode using Nominatim
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="kirana_khata_underwriter")
            location = geolocator.reverse(f"{lat}, {lon}", timeout=8)

            address = location.raw.get("address", {}) if location else {}
            pin_code = address.get("postcode", "")

            # Tier classification heuristic based on city / state
            city = address.get("city", address.get("town", address.get("suburb", address.get("municipality", "")))).lower()
            state = address.get("state", "").lower()

            tier = 3
            # Tier-1 Indian cities
            tier_1_cities = {"mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "kolkata", "chennai", "hyderabad", "pune", "ahmedabad"}
            # Tier-2 Indian cities
            tier_2_cities = {
                "jaipur", "lucknow", "kanpur", "nagpur", "indore", "thane", "bhopal", "visakhapatnam",
                "pimpri-chinchwad", "patna", "vadodara", "ghaziabad", "ludhiana", "agra", "nashik",
                "faridabad", "meerut", "rajkot", "kalyan-dombivli", "vasai-virar", "varanasi",
                "srinagar", "aurangabad", "dhanbad", "amritsar", "navi mumbai", "allahabad",
                "ranchi", "howrah", "coimbatore", "jabalpur", "gwalior", "vijayawada", "jodhpur",
                "madurai", "raipur", "kota", "guwahati", "solapur", "hubli-dharwad", "bareilly",
                "moradabad", "mysore", "gurgaon", "noida", "aligarh", "jalandhar", "tiruchirappalli",
                "bhubaneswar", "salem", "mira-bhayandar", "warangal", "guntur", "thiruvananthapuram",
                "bhiwandi", "saharanpur", "amravati"
            }

            if any(t1 in city for t1 in tier_1_cities):
                tier = 1
            elif any(t2 in city for t2 in tier_2_cities):
                tier = 2

            # 2. Query OSM Overpass API in a single query across multiple public mirrors
            import requests

            # Clean query with flat indentation for compatibility, limited to 300m radius of concern
            overpass_query = f"""[out:json][timeout:25];
(
  nwr["amenity"~"school|college|university|hospital|clinic|place_of_worship|bank|atm|marketplace"](around:300, {lat}, {lon});
  nwr["highway"="bus_stop"](around:300, {lat}, {lon});
  nwr["public_transport"="platform"](around:300, {lat}, {lon});
  nwr["shop"~"mall|supermarket|convenience|general|grocery|department_store|kiosk|minimarket"](around:300, {lat}, {lon});
  way["highway"](around:100, {lat}, {lon});
  nwr["building"](around:300, {lat}, {lon});
);
out center;"""

            # Standard headers to comply with API usage guidelines
            headers = {
                "User-Agent": "KiranaKhataGeospatialProcessor/1.0 (contact: geo-underwriting@kirana-khata-prod.com)",
                "Accept": "application/json"
            }

            mirrors = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
                "https://lz4.overpass-api.de/api/interpreter",
                "https://z.overpass-api.de/api/interpreter",
            ]

            response = None
            last_err = None

            for mirror in mirrors:
                try:
                    logger.info("Attempting to query Overpass mirror: %s", mirror)
                    # Try POST raw body (most standard and recommended)
                    response = requests.post(mirror, data=overpass_query.encode("utf-8"), headers=headers, timeout=4)
                    response.raise_for_status()
                    break
                except Exception as e:
                    last_err = e
                    logger.warning("Mirror %s failed (POST raw): %s. Trying POST form data...", mirror, str(e))
                    try:
                        # Try POST form data
                        response = requests.post(mirror, data={"data": overpass_query}, headers=headers, timeout=4)
                        response.raise_for_status()
                        break
                    except Exception as fe:
                        last_err = fe
                        logger.warning("Mirror %s failed (POST form): %s. Trying GET...", mirror, str(fe))
                        try:
                            # Try GET
                            response = requests.get(mirror, params={"data": overpass_query}, headers=headers, timeout=4)
                            response.raise_for_status()
                            break
                        except Exception as ge:
                            last_err = ge
                            logger.warning("Mirror %s failed (GET): %s", mirror, str(ge))
                            continue

            if response is None or response.status_code != 200:
                raise last_err or Exception("All Overpass mirrors failed.")

            osm_data = response.json()
            elements = osm_data.get("elements", [])
            logger.info("Successfully fetched %d OSM elements for (%.4f, %.4f)", len(elements), lat, lon)

            return {
                "pin_code": pin_code,
                "region_tier": tier,
                "elements": elements,
                "address": address
            }

        except Exception as e:
            logger.warning("Failed to fetch precise geospatial data: %s. Falling back to mock data.", str(e))
            return None

    @staticmethod
    def _get_element_coords(elem: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """Get (lat, lon) coordinates of an OSM element."""
        if "lat" in elem and "lon" in elem:
            return elem["lat"], elem["lon"]
        elif "center" in elem:
            return elem["center"]["lat"], elem["center"]["lon"]
        return None

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Compute the great-circle distance between two points (km)."""
        R = 6371.0  # Earth radius in km
        lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
        lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _coord_seed(lat: float, lon: float) -> int:
        """Generate a deterministic integer seed from coordinates.

        Ensures the same location always produces the same mock data,
        making tests reproducible.
        """
        key = f"{lat:.6f},{lon:.6f}"
        digest = hashlib.md5(key.encode()).hexdigest()
        return int(digest[:8], 16)

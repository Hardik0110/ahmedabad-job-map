import httpx
import time
import random
import math

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "AhmedabadJobsMap/1.0 (contact@example.com)"}

# Ahmedabad IT corridor center (SG Highway / Prahlad Nagar belt)
AHMEDABAD_LAT = 23.0280
AHMEDABAD_LNG = 72.5100

# Known area centers in Ahmedabad (lat, lng)
AREA_CENTERS = {
    "prahlad nagar":   (23.0117, 72.5072),
    "prahladnagar":    (23.0117, 72.5072),
    "satellite":       (23.0170, 72.5230),
    "bodakdev":        (23.0378, 72.5032),
    "sg highway":      (23.0300, 72.5100),
    "navrangpura":     (23.0395, 72.5600),
    "vastrapur":       (23.0365, 72.5270),
    "thaltej":         (23.0510, 72.4990),
    "makarba":         (23.0050, 72.4980),
    "gandhinagar":     (23.2156, 72.6369),
    "gift city":       (23.1572, 72.6812),
    "anandnagar":      (23.0380, 72.5450),
    "shantigram":      (23.0700, 72.5350),
    "maninagar":       (22.9900, 72.6050),
    "gurukul":         (23.0420, 72.5380),
    "bopal":           (22.9830, 72.4680),
    "ambli":           (23.0290, 72.4800),
    "science city":    (23.0720, 72.5130),
    "memnagar":        (23.0490, 72.5350),
    "ellis bridge":    (23.0320, 72.5600),
    "ashram road":     (23.0350, 72.5680),
    "c.g. road":       (23.0310, 72.5520),
    "cg road":         (23.0310, 72.5520),
    "drive in":        (23.0450, 72.5300),
    "drive-in":        (23.0450, 72.5300),
    "gota":            (23.1020, 72.5410),
    "chandkheda":      (23.1150, 72.5800),
    "motera":          (23.1020, 72.5960),
    "iscon":           (23.0210, 72.5070),
    "hebatpur":        (23.0580, 72.4980),
    "sindhu bhavan":   (23.0350, 72.4900),
    "south bopal":     (22.9750, 72.4700),
    "ghuma":           (22.9750, 72.4830),
    "vejalpur":        (22.9960, 72.5500),
    "jodhpur":         (23.0290, 72.5180),
    "sabarmati":       (23.0730, 72.5850),
    "bapunagar":       (23.0280, 72.6250),
    "naroda":          (23.0760, 72.6550),
    "odhav":           (23.0250, 72.6650),
    "vastral":         (22.9880, 72.6480),
    "nikol":           (23.0460, 72.6500),
    "new cg road":     (23.0280, 72.5900),
    "sarkhej":         (22.9830, 72.5050),
    "ahmedabad":       (23.0300, 72.5050),  # IT corridor (west of river)
}

# Sabarmati River centerline points (lat, lng) from north to south
# Traced carefully along the actual river path
RIVER_POINTS = [
    (23.120, 72.582),
    (23.110, 72.580),
    (23.100, 72.579),
    (23.090, 72.577),
    (23.080, 72.575),
    (23.070, 72.573),
    (23.060, 72.571),
    (23.050, 72.569),
    (23.040, 72.567),
    (23.035, 72.566),
    (23.030, 72.564),
    (23.025, 72.562),
    (23.020, 72.560),
    (23.015, 72.558),
    (23.010, 72.556),
    (23.005, 72.554),
    (23.000, 72.553),
    (22.995, 72.551),
    (22.990, 72.550),
    (22.985, 72.548),
    (22.975, 72.546),
]

# ~1.2km exclusion zone around the river
RIVER_EXCLUSION = 0.012


def _distance_to_river(lat: float, lng: float) -> float:
    """Return minimum distance (in degrees) from point to river centerline."""
    min_dist = float("inf")
    for rlat, rlng in RIVER_POINTS:
        d = math.sqrt((lat - rlat) ** 2 + (lng - rlng) ** 2)
        if d < min_dist:
            min_dist = d
    return min_dist


def _push_away_from_river(lat: float, lng: float) -> tuple[float, float]:
    """If point is within exclusion zone, push it to the nearest side of the river."""
    # Find closest river point
    closest_rlat, closest_rlng = RIVER_POINTS[0]
    min_dist = float("inf")
    for rlat, rlng in RIVER_POINTS:
        d = math.sqrt((lat - rlat) ** 2 + (lng - rlng) ** 2)
        if d < min_dist:
            min_dist = d
            closest_rlat, closest_rlng = rlat, rlng

    if min_dist >= RIVER_EXCLUSION:
        return lat, lng

    # Push perpendicular to the river (river runs roughly north-south)
    # If west of river -> push further west, if east -> push further east
    if lng < closest_rlng:
        lng = closest_rlng - RIVER_EXCLUSION - 0.005
    else:
        lng = closest_rlng + RIVER_EXCLUSION + 0.005

    return lat, lng


def _normalize_location(text: str) -> str:
    """Normalize location text for matching."""
    t = text.lower().strip()
    if "," in t or "\n" in t:
        t = t.split(",")[0].split("\n")[0].strip()
    return t


def _name_hash(name: str) -> int:
    """Simple deterministic hash from company name."""
    h = 0
    for ch in name:
        h = ord(ch) + ((h << 5) - h)
    return abs(h)


def geocode(location_text: str, company_name: str = "") -> tuple[float, float]:
    """
    Place a company pin near its area center with seeded random scatter.
    Uses the company name as seed so the position is deterministic.

    For specific areas (Prahlad Nagar, Satellite, etc.) -> scatter within ~1km.
    For generic "Ahmedabad" -> scatter across a wider ~4km zone covering
    the western IT corridor (SG Highway to Satellite to Prahlad Nagar).
    """
    normalized = _normalize_location(location_text)

    # Find the area center
    center = AREA_CENTERS.get(normalized)

    if not center:
        for key, coords in AREA_CENTERS.items():
            if key in normalized or normalized in key:
                center = coords
                break

    if not center:
        center = AREA_CENTERS["ahmedabad"]

    # Use company name as random seed for deterministic but natural scatter
    rng = random.Random(_name_hash(company_name or location_text))

    # Wider spread for generic "Ahmedabad", tighter for specific areas
    is_generic = normalized in ("ahmedabad", "")
    spread = 0.030 if is_generic else 0.008  # ~3.3km vs ~0.9km

    if is_generic:
        # Split companies across both sides of the river
        # Use hash to decide west vs east side
        side = rng.choice(["west", "east"])
        if side == "west":
            cx, cy = 23.030, 72.510  # west IT corridor
        else:
            cx, cy = 23.035, 72.600  # east side (Navrangpura/CG Road/Memnagar)
        angle = rng.uniform(0, 2 * math.pi)
        r = 0.018 * math.sqrt(rng.uniform(0, 1))
        lat = cx + r * math.cos(angle)
        lng = cy + r * math.sin(angle)
    else:
        angle = rng.uniform(0, 2 * math.pi)
        r = spread * math.sqrt(rng.uniform(0, 1))
        lat = center[0] + r * math.cos(angle)
        lng = center[1] + r * math.sin(angle)

    # Push away from river if inside exclusion zone
    lat, lng = _push_away_from_river(lat, lng)

    return lat, lng

import os
import json
import urllib.request
import urllib.parse
import subprocess

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k] = v

load_env()

def geocode_address(address: str) -> str:
    """Turn an address into geographic coordinates using the Geocoding API.

    Args:
        address: Unstructured address string (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Formatted address and coordinates (latitude, longitude).
    """
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    encoded = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded}&key={key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        if data.get("status") == "OK" and data.get("results"):
            res = data["results"][0]
            formatted_addr = res.get("formatted_address", address)
            loc = res["geometry"]["location"]
            return f"Address: {formatted_addr} | Location: ({loc['lat']}, {loc['lng']})"
    except Exception:
        pass

    # Fallback to Open-Meteo Geocoding REST API
    try:
        fallback_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1"
        req = urllib.request.Request(fallback_url, headers={"User-Agent": "RunLifestyle/1.0"})
        with urllib.request.urlopen(req) as resp:
            fdata = json.loads(resp.read().decode())
        results = fdata.get("results")
        if results:
            r = results[0]
            c_str = f", {r.get('country')}" if r.get('country') else ""
            return f"Address: {r.get('name')}{c_str} | Location: ({r.get('latitude')}, {r.get('longitude')})"
    except Exception as ex:
        return f"Geocoding failed for {address}: {ex}"

    return f"No geocoding results found for {address}."


def find_nearby_places(latitude: float, longitude: float, place_type: str = "park", radius_meters: float = 1000.0) -> str:
    """Find nearby places of a given type around coordinates using Places API (New) REST endpoint.

    Args:
        latitude: Center latitude.
        longitude: Center longitude.
        place_type: Type of place to search for (e.g., 'park', 'gym', 'sports_complex').
        radius_meters: Search radius in meters.

    Returns:
        Formatted list of nearby places with name, formatted address, and location.
    """
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": float(latitude), "longitude": float(longitude)},
                "radius": float(radius_meters),
            }
        },
    }

    pdata = {}
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            pdata = json.loads(resp.read().decode())
    except Exception:
        # Fallback using Bearer token
        try:
            token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
            fb_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "X-Goog-User-Project": "qwiklabs-gcp-02-61a3e08edf96",
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
            }
            req_fb = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=fb_headers, method="POST")
            with urllib.request.urlopen(req_fb) as resp_fb:
                pdata = json.loads(resp_fb.read().decode())
        except Exception as ex:
            return f"Places API request failed: {ex}"

    places = pdata.get("places", [])
    if not places:
        return f"No nearby {place_type} found within {radius_meters}m."

    lines = []
    for p in places:
        name = p.get("displayName", {}).get("text", "Unknown")
        addr = p.get("formattedAddress", "N/A")
        loc = p.get("location", {})
        lines.append(f"- Name: {name} | Address: {addr} | Location: ({loc.get('latitude')}, {loc.get('longitude')})")

    return "\n".join(lines)


if __name__ == "__main__":
    print("GEOCODE TEST:")
    print(geocode_address("San Francisco, CA"))
    print("\nNEARBY PLACES TEST:")
    print(find_nearby_places(37.7749, -122.4194, "park", 1000))

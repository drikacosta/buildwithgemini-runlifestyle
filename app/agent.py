# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import subprocess
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types
from google.oauth2 import credentials

from .a2ui_utils import a2ui_callback

# IMPORTANT: Hardcode GCP project ID and bucket name as strings.
# Do NOT read from GOOGLE_CLOUD_PROJECT or google.auth.default() because
# on Agent Platform those return the project number instead of project ID.
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-61a3e08edf96"
BUCKET_NAME = "runlifestyle-images-qwiklabs-gcp-02-61a3e08edf96"


def _get_firestore_client() -> firestore.Client:
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = credentials.Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_running_routes(location: str = "", terrain: str = "") -> str:
    """Search for running routes in the Firestore collection by location or terrain.

    Args:
        location: City or area to filter routes by (e.g., 'San Francisco', 'New York').
        terrain: Terrain type to filter routes by (e.g., 'Paved', 'Trail').

    Returns:
        A formatted list of matching running routes with distance, terrain, and description.
    """
    db = _get_firestore_client()
    routes_ref = db.collection("running_routes")
    docs = routes_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        loc_match = not location or location.lower() in data.get("location", "").lower()
        terr_match = not terrain or terrain.lower() in data.get("terrain", "").lower()
        if loc_match and terr_match:
            results.append(data)

    if not results:
        return f"No running routes found matching location='{location}', terrain='{terrain}'."

    summary_lines = []
    for r in results:
        summary_lines.append(
            f"- [{r.get('id')}] {r.get('name')} in {r.get('location')}: {r.get('distance_miles')} miles ({r.get('terrain')}, {r.get('difficulty')}). Rating: {r.get('rating')}/5. {r.get('description')}"
        )
    return "\n".join(summary_lines)


def add_running_route(
    name: str,
    location: str,
    distance_miles: float,
    terrain: str,
    description: str,
    difficulty: str = "Moderate",
    rating: float = 4.5,
) -> str:
    """Add a new running route to the Firestore database.

    Args:
        name: The name of the running route.
        location: The city or area where the route is located.
        distance_miles: Route distance in miles.
        terrain: Terrain type (e.g., 'Paved / Flat', 'Trail', 'Road').
        description: A brief summary or highlight of the route.
        difficulty: Difficulty rating (e.g., 'Easy', 'Moderate', 'Challenging').
        rating: User rating out of 5.0.

    Returns:
        Confirmation message containing the new route ID.
    """
    db = _get_firestore_client()
    route_id = f"route-{uuid.uuid4().hex[:6]}"
    route_doc = {
        "id": route_id,
        "name": name,
        "location": location,
        "distance_miles": float(distance_miles),
        "terrain": terrain,
        "description": description,
        "difficulty": difficulty,
        "rating": float(rating),
    }

    db.collection("running_routes").document(route_id).set(route_doc)
    return f"Successfully added new running route '{name}' (ID: {route_id}) to {location}!"


def calculate_pace_and_calories(
    distance_miles: float,
    duration_minutes: float,
    runner_weight_lbs: float = 150.0,
) -> str:
    """Calculate average running pace (minutes per mile) and estimated calorie burn.

    Args:
        distance_miles: Total distance in miles.
        duration_minutes: Total duration in minutes.
        runner_weight_lbs: Runner's weight in pounds (default: 150.0 lbs).

    Returns:
        Formatted summary with average pace (min/mile) and estimated calories burned.
    """
    if distance_miles <= 0 or duration_minutes <= 0:
        return "Distance and duration must be greater than zero."

    pace_total_seconds = int((duration_minutes / distance_miles) * 60)
    pace_minutes = pace_total_seconds // 60
    pace_seconds = pace_total_seconds % 60

    estimated_calories = int(0.75 * runner_weight_lbs * distance_miles)

    return (
        f"Average Pace: {pace_minutes}:{pace_seconds:02d} min/mile | "
        f"Estimated Calories Burned: ~{estimated_calories} kcal (for a {runner_weight_lbs} lbs runner)."
    )


def get_live_running_weather(city: str) -> str:
    """Fetch real-time weather and outdoor running advice for a city using Open-Meteo API.

    Args:
        city: City name to check (e.g., 'San Francisco', 'New York', 'Tokyo').

    Returns:
        Real-time weather conditions (temperature, wind speed) and running advice.
    """
    try:
        encoded_city = urllib.parse.quote(city)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1"
        req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "RunLifestyle/1.0"})
        with urllib.request.urlopen(req_geo) as resp_geo:
            geo_data = json.loads(resp_geo.read().decode())

        results = geo_data.get("results")
        if not results:
            return f"City '{city}' not found."

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        matched_name = results[0].get("name", city)
        country = results[0].get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "RunLifestyle/1.0"})
        with urllib.request.urlopen(req_w) as resp_w:
            w_data = json.loads(resp_w.read().decode())

        current = w_data.get("current_weather", {})
        temp_c = current.get("temperature", 20.0)
        temp_f = round((temp_c * 9 / 5) + 32, 1)
        wind_kmh = current.get("windspeed", 0.0)

        if temp_c > 30:
            advice = "Hot conditions! Stay hydrated, wear light clothing, and consider running early."
        elif temp_c < 5:
            advice = "Cold conditions! Wear thermal layers and warm up thoroughly before starting."
        elif wind_kmh > 35:
            advice = "Windy conditions! Be mindful of strong headwinds on open paths."
        else:
            advice = "Great conditions for an outdoor run!"

        return (
            f"Live Weather for {matched_name}, {country}: {temp_c}°C ({temp_f}°F), "
            f"Wind Speed: {wind_kmh} km/h. {advice}"
        )
    except Exception as e:
        return f"Unable to fetch live weather for '{city}': {e}"


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

    # Fallback to Open-Meteo Geocoding REST API if key restricted/unavailable
    try:
        fallback_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count=1"
        req = urllib.request.Request(fallback_url, headers={"User-Agent": "RunLifestyle/1.0"})
        with urllib.request.urlopen(req) as resp:
            fdata = json.loads(resp.read().decode())
        results = fdata.get("results")
        if results:
            r = results[0]
            c_str = f", {r.get('country')}" if r.get("country") else ""
            return f"Address: {r.get('name')}{c_str} | Location: ({r.get('latitude')}, {r.get('longitude')})"
    except Exception as ex:
        return f"Geocoding failed for '{address}': {ex}"

    return f"No geocoding results found for '{address}'."


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "park",
    radius_meters: float = 1000.0,
) -> str:
    """Find nearby places of a given type around coordinates using Places API (New) REST endpoint.

    Args:
        latitude: Center latitude.
        longitude: Center longitude.
        place_type: Type of place to search for (e.g., 'park', 'gym', 'sports_complex').
        radius_meters: Search radius in meters (default 1000m).

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
        # Fallback with Bearer token if API key is restricted
        try:
            token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
            fb_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "X-Goog-User-Project": FIRESTORE_PROJECT_ID,
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


def _get_storage_client() -> storage.Client:
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = credentials.Credentials(token)
        return storage.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        return storage.Client(project=FIRESTORE_PROJECT_ID)


def generate_route_image(prompt: str, tool_context: ToolContext) -> str:
    """Generate an image for a running route or item in the RunLifestyle domain using gemini-3.1-flash-lite-image model in the global region.

    Saves the image as an artifact in the Playground's Artifacts panel via tool_context.save_artifact
    and uploads the image bytes directly to public Cloud Storage, returning its public HTTPS URL.

    Args:
        prompt: Description of the running route, fitness gear, or route highlight image to generate.
        tool_context: ADK ToolContext used to save the artifact.

    Returns:
        Public Cloud Storage HTTPS URL (https://storage.googleapis.com/<bucket>/<object>).
    """
    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global",
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=f"Generate a vibrant high quality illustration or photo for running lifestyle: {prompt}",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    image_bytes = None
    mime_type = "image/png"

    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return f"Failed to generate image bytes for prompt: '{prompt}'"

    ext = "png" if "png" in mime_type else "jpg"
    filename = f"route_{uuid.uuid4().hex[:8]}.{ext}"

    # 1. Save artifact with tool_context.save_artifact for Playground Artifacts panel
    try:
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)
    except Exception as e:
        print(f"Warning: tool_context.save_artifact failed: {e}")

    # 2. Upload image bytes directly to public Cloud Storage bucket (no local file)
    try:
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
        return public_url
    except Exception as ex:
        return f"Error uploading image bytes to Cloud Storage bucket '{BUCKET_NAME}': {ex}"


def generate_route_video(prompt: str, tool_context: ToolContext) -> str:
    """Generate a short video clip for a running route or item in the RunLifestyle domain using gemini-omni-flash-preview model in the global region.

    Saves the video as an artifact in the Playground's Artifacts panel via tool_context.save_artifact
    and uploads the video bytes directly to public Cloud Storage, returning its public HTTPS URL.

    Args:
        prompt: Description of the running scene, route highlight, or athletic action to generate as a video.
        tool_context: ADK ToolContext used to save the artifact.

    Returns:
        Public Cloud Storage HTTPS URL (https://storage.googleapis.com/<bucket>/<object>).
    """
    client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT_ID,
        location="global",
    )

    try:
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"A high quality short video clip for running lifestyle: {prompt}",
        )

        video_bytes = None
        if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
            data = interaction.output_video.data
            video_bytes = base64.b64decode(data) if isinstance(data, str) else data

        if not video_bytes and hasattr(interaction, "steps") and interaction.steps:
            for step in interaction.steps:
                if getattr(step, "content", None):
                    for part in step.content:
                        if getattr(part, "mime_type", "").startswith("video/") or getattr(part, "type", "") == "video":
                            d = getattr(part, "data", None)
                            if d:
                                video_bytes = base64.b64decode(d) if isinstance(d, str) else d
                                break

        if not video_bytes:
            return f"Failed to generate video bytes for prompt: '{prompt}'"

        mime_type = "video/mp4"
        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact with tool_context.save_artifact for Playground Artifacts panel
        try:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=filename, artifact=artifact_part)
        except Exception as e:
            print(f"Warning: tool_context.save_artifact failed: {e}")

        # 2. Upload video bytes directly to public Cloud Storage bucket (no local file)
        try:
            storage_client = _get_storage_client()
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(filename)
            blob.upload_from_string(video_bytes, content_type=mime_type)
            public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
            return public_url
        except Exception as ex:
            return f"Error uploading video bytes to Cloud Storage bucket '{BUCKET_NAME}': {ex}"

    except Exception as e:
        return f"Error generating video with gemini-omni-flash-preview: {e}"


def _get_code_executor() -> AgentEngineSandboxCodeExecutor | None:
    meta_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        sandbox_resource = meta.get("sandbox_resource_name")
        engine_resource = meta.get("remote_agent_runtime_id")
        if sandbox_resource:
            return AgentEngineSandboxCodeExecutor(sandbox_resource_name=sandbox_resource)
        elif engine_resource:
            return AgentEngineSandboxCodeExecutor(agent_engine_resource_name=engine_resource)
    except Exception as e:
        print(f"Warning: Failed to initialize AgentEngineSandboxCodeExecutor: {e}")
    return None


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        if getattr(callback_context, "memory_service", None) is not None:
            await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Warning: add_session_to_memory skipped or failed: {e}")
    return None


MEMORY_BANK_ID = "6917547719338754048"


def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

_a2ui_instruction = _schema_manager.generate_system_prompt(
    role_description=(
        "You are the RunLifestyle assistant, a stateful running and fitness coach. "
        "You remember the user's stated preferences, goals, facts, and ALLERGIES / medical conditions from previous conversations "
        "and use them to personalize your responses. "
        "Pay special attention to any allergies, dietary restrictions, sensitivities (e.g., pollen, heat, asthma, foods, medications), "
        "or health conditions mentioned by the user, and ensure they are remembered and accounted for in all running, route, and fitness recommendations. "
        "You can search for running routes, record new running routes in Firestore, "
        "calculate running pace and calorie burn, check real-time live weather, "
        "geocode addresses into coordinates, find nearby places (like parks or gyms), "
        "and generate promotional images or short video clips for running routes or fitness items. "
        "You can also run Python code safely in a sandbox when requested."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property (\'h1\', \'h2\', \'body\') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or \'kind\'/\'data\'/\'metadata\' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=_get_code_executor(),
    instruction=_a2ui_instruction,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        search_running_routes,
        add_running_route,
        calculate_pace_and_calories,
        get_live_running_weather,
        geocode_address,
        find_nearby_places,
        generate_route_image,
        generate_route_video,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

#!/usr/bin/env python3
"""Seed script for runlifestyle Firestore database."""

import subprocess
from google.cloud import firestore
from google.oauth2 import credentials

# IMPORTANT: Hardcoded GCP project ID (string ID, not project number)
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-61a3e08edf96"

def get_firestore_client():
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        creds = credentials.Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT_ID, credentials=creds)
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT_ID)

def seed_firestore():
    print(f"Connecting to Firestore with project_id={FIRESTORE_PROJECT_ID}...")
    db = get_firestore_client()
    collection_ref = db.collection("running_routes")

    routes = [
        {
            "id": "route-001",
            "name": "Embarcadero Waterfront Run",
            "location": "San Francisco",
            "distance_miles": 5.0,
            "terrain": "Paved / Flat",
            "difficulty": "Easy",
            "description": "Scenic flat run along the bay with views of the Bay Bridge and Ferry Building.",
            "rating": 4.8,
        },
        {
            "id": "route-002",
            "name": "Golden Gate Park Loop",
            "location": "San Francisco",
            "distance_miles": 6.2,
            "terrain": "Road & Trail",
            "difficulty": "Moderate",
            "description": "Lush green loop passing Stow Lake, Bison Paddock, and ending at Ocean Beach.",
            "rating": 4.9,
        },
        {
            "id": "route-003",
            "name": "Central Park Reservoir & Hills",
            "location": "New York",
            "distance_miles": 4.0,
            "terrain": "Paved & Dirt Track",
            "difficulty": "Moderate",
            "description": "Classic NYC run around the Jackie O. Reservoir with rolling hills along Cat Hill.",
            "rating": 4.7,
        },
        {
            "id": "route-004",
            "name": "Hudson River Park Trail",
            "location": "New York",
            "distance_miles": 7.5,
            "terrain": "Paved Pier Path",
            "difficulty": "Easy",
            "description": "Continuous waterfront greenway running along Manhattan west side.",
            "rating": 4.6,
        },
    ]

    for route in routes:
        doc_ref = collection_ref.document(route["id"])
        doc_ref.set(route)
        print(f"Seeded route: {route['id']} - {route['name']}")

    print("Firestore seeding complete!")

if __name__ == "__main__":
    seed_firestore()

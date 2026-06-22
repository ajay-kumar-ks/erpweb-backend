"""
Example: Testing the Business Suite Backend API

Run these requests after starting the server:
    uvicorn app.main:app --reload
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")

# Headers for authenticated requests
def get_auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health():
    """Check server health"""
    print("\n=== Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_login():
    """Login and get access token"""
    print("\n=== Login ===")
    login_data = {
        "username": "admin",
        "password": "secret"
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    return data.get("access_token")


def test_dashboard(token: str):
    """Access protected dashboard endpoint"""
    print("\n=== Dashboard (Protected) ===")
    headers = get_auth_headers(token)
    response = requests.get(f"{BASE_URL}/auth/dashboard", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")


def test_module_health():
    """Check all module endpoints"""
    print("\n=== Module Health ===")
    modules = ["hr", "accounts", "crm", "tasks"]
    for module in modules:
        response = requests.get(f"{BASE_URL}/{module}/")
        print(f"{module.upper()}: {response.json()}")


if __name__ == "__main__":
    try:
        test_health()
        token = test_login()
        if token:
            test_dashboard(token)
        test_module_health()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server. Make sure it's running on {BASE_URL}")

#!/usr/bin/env python3
"""
Test script for CRM Leads Phase 2 functionality
Tests pipeline, phase, and lead CRUD operations
"""

import os
import requests
import json
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8001/api")

def test_pipelines():
    """Test pipeline endpoints"""
    print("\n=== Testing Pipelines ===")
    
    # Create a pipeline
    pipeline_data = {
        "name": "Sales Pipeline",
        "description": "Primary sales pipeline",
        "owner": "sales@example.com"
    }
    response = requests.post(f"{BASE_URL}/crm/pipelines/", json=pipeline_data)
    print(f"Create Pipeline: {response.status_code}")
    if response.status_code == 201:
        pipeline = response.json()
        pipeline_id = pipeline["id"]
        print(f"  Pipeline ID: {pipeline_id}")
        print(f"  Name: {pipeline['name']}")
        
        # List pipelines
        response = requests.get(f"{BASE_URL}/crm/pipelines/")
        print(f"List Pipelines: {response.status_code} - {len(response.json())} pipelines")
        
        return pipeline_id
    else:
        print(f"  Error: {response.text}")
        return None

def test_phases(pipeline_id):
    """Test phase endpoints"""
    print("\n=== Testing Phases ===")
    
    phases_data = [
        {"name": "New", "color": "#3b82f6", "position": 0, "is_terminal": False},
        {"name": "Contacted", "color": "#8b5cf6", "position": 1, "is_terminal": False},
        {"name": "Qualified", "color": "#ec4899", "position": 2, "is_terminal": False},
        {"name": "Proposal", "color": "#f59e0b", "position": 3, "is_terminal": False},
        {"name": "Won", "color": "#10b981", "position": 4, "is_terminal": True},
    ]
    
    phase_ids = []
    for phase_data in phases_data:
        response = requests.post(f"{BASE_URL}/crm/pipelines/{pipeline_id}/phases", json=phase_data)
        print(f"Create Phase '{phase_data['name']}': {response.status_code}")
        if response.status_code == 201:
            phase = response.json()
            phase_ids.append(phase["id"])
        else:
            print(f"  Error: {response.text}")
    
    # List phases
    response = requests.get(f"{BASE_URL}/crm/pipelines/{pipeline_id}/phases")
    print(f"List Phases: {response.status_code} - {len(response.json())} phases")
    
    return phase_ids

def test_contacts():
    """Get or create a contact for testing"""
    print("\n=== Testing Contacts ===")
    
    # List contacts
    response = requests.get(f"{BASE_URL}/crm/contacts/")
    print(f"List Contacts: {response.status_code}")
    
    contacts = response.json()
    if contacts:
        contact_id = contacts[0]["id"]
        print(f"  Using existing contact: {contacts[0]['name']} ({contact_id})")
        return contact_id
    
    # Create a contact if none exist
    contact_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "company": "Tech Corp"
    }
    response = requests.post(f"{BASE_URL}/crm/contacts/", json=contact_data)
    print(f"Create Contact: {response.status_code}")
    if response.status_code == 201:
        contact = response.json()
        print(f"  Contact ID: {contact['id']}")
        return contact["id"]
    else:
        print(f"  Error: {response.text}")
        return None

def test_leads(pipeline_id, phase_ids, contact_id):
    """Test lead endpoints"""
    print("\n=== Testing Leads ===")
    
    if not phase_ids:
        print("  No phases available, skipping leads test")
        return None
    
    # Create a lead
    lead_data = {
        "title": "Enterprise Deal - Q3",
        "contact_id": contact_id,
        "pipeline_id": pipeline_id,
        "phase_id": phase_ids[0],
        "value": 50000,
        "expected_close_date": (datetime.now() + timedelta(days=30)).isoformat(),
        "assignee": "sales@example.com",
        "source": "Referral",
        "notes": "High-value opportunity"
    }
    response = requests.post(f"{BASE_URL}/crm/leads/", json=lead_data)
    print(f"Create Lead: {response.status_code}")
    if response.status_code == 201:
        lead = response.json()
        lead_id = lead["id"]
        print(f"  Lead ID: {lead_id}")
        print(f"  Title: {lead['title']}")
        print(f"  Value: ${lead['value']}")
        
        # Get lead details
        response = requests.get(f"{BASE_URL}/crm/leads/{lead_id}")
        print(f"Get Lead: {response.status_code}")
        
        # Update lead
        update_data = {"phase_id": phase_ids[1]}
        response = requests.put(f"{BASE_URL}/crm/leads/{lead_id}", json=update_data)
        print(f"Update Lead: {response.status_code}")
        
        # Move lead to different phase
        response = requests.put(f"{BASE_URL}/crm/leads/{lead_id}/move?phase_id={phase_ids[1]}")
        print(f"Move Lead: {response.status_code}")
        
        # List leads
        response = requests.get(f"{BASE_URL}/crm/leads/")
        print(f"List Leads: {response.status_code} - {len(response.json())} leads")
        
        return lead_id
    else:
        print(f"  Error: {response.text}")
        return None

def test_lead_convert(lead_id):
    """Test lead conversion"""
    print("\n=== Testing Lead Conversion ===")
    
    response = requests.post(f"{BASE_URL}/crm/leads/{lead_id}/convert")
    print(f"Convert Lead: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"  Lead converted: {result['success']}")
    else:
        print(f"  Error: {response.text}")

def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("CRM Leads Phase 2 - Test Suite")
    print("=" * 50)
    
    try:
        # Test pipelines
        pipeline_id = test_pipelines()
        if not pipeline_id:
            print("\nFailed to create pipeline. Aborting tests.")
            return
        
        # Test phases
        phase_ids = test_phases(pipeline_id)
        
        # Test contacts
        contact_id = test_contacts()
        
        # Test leads
        lead_id = test_leads(pipeline_id, phase_ids, contact_id)
        
        # Test lead conversion
        if lead_id:
            test_lead_convert(lead_id)
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        print("=" * 50)
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Could not connect to backend at {BASE_URL}")
        print(f"Make sure the backend server is running on {BASE_URL}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    run_all_tests()

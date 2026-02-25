#!/usr/bin/env python3
"""Create and attach knowledge base to Gigi agent via Retell API."""

import os
import sys
import json
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
if not RETELL_API_KEY:
    print("ERROR: RETELL_API_KEY environment variable is required")
    print("Run: export RETELL_API_KEY='your_key_here'")
    sys.exit(1)

RETELL_API_BASE = "https://api.retellai.com"
AGENT_ID = "agent_d5c3f32bdf48fa4f7f24af7d36"


def main():
    print("=" * 60)
    print("CREATING KNOWLEDGE BASE FOR GIGI")
    print("=" * 60)

    # Read the knowledge base content
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(script_dir, "knowledge_base.md")
    with open(kb_path, "r") as f:
        kb_content = f.read()
    
    print(f"Knowledge base size: {len(kb_content)} characters")
    
    # First, let's check what endpoints are available for knowledge bases
    # Try to list existing knowledge bases
    print("\nListing existing knowledge bases...")
    list_response = requests.get(
        f"{RETELL_API_BASE}/list-knowledge-bases",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
        },
        timeout=30
    )
    print(f"List response status: {list_response.status_code}")
    if list_response.status_code == 200:
        kbs = list_response.json()
        print(f"Existing knowledge bases: {json.dumps(kbs, indent=2)[:500]}")
    else:
        print(f"Error: {list_response.text[:500]}")
    
    # Try creating a knowledge base with text content
    print("\n" + "-" * 60)
    print("Creating new knowledge base...")
    
    create_payload = {
        "knowledge_base_name": "Gigi Knowledge Base",
        "texts": [
            {
                "title": "Colorado Care Assist - Complete Knowledge Base",
                "text": kb_content
            }
        ]
    }
    
    create_response = requests.post(
        f"{RETELL_API_BASE}/create-knowledge-base",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=create_payload,
        timeout=120
    )
    
    print(f"Create response status: {create_response.status_code}")
    
    if create_response.status_code in (200, 201):
        kb_data = create_response.json()
        kb_id = kb_data.get("knowledge_base_id")
        print(f"SUCCESS! Created knowledge base: {kb_id}")
        print(f"Response: {json.dumps(kb_data, indent=2)[:500]}")
        
        # Now attach to the agent
        print("\n" + "-" * 60)
        print(f"Attaching knowledge base to agent {AGENT_ID}...")
        
        attach_response = requests.patch(
            f"{RETELL_API_BASE}/update-agent/{AGENT_ID}",
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "knowledge_base_ids": [kb_id]
            },
            timeout=30
        )
        
        print(f"Attach response status: {attach_response.status_code}")
        if attach_response.status_code == 200:
            print("SUCCESS! Knowledge base attached to agent.")
            print("\n" + "=" * 60)
            print("KNOWLEDGE BASE SETUP COMPLETE")
            print("=" * 60)
            print(f"Knowledge Base ID: {kb_id}")
            print(f"Agent ID: {AGENT_ID}")
            return True
        else:
            print(f"Error attaching: {attach_response.text[:500]}")
            return False
    else:
        print(f"Error creating knowledge base:")
        print(create_response.text[:1000])
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

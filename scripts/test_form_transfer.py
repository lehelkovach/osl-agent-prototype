#!/usr/bin/env python3
"""
Test script for form filler data transfer between different forms.

This script tests whether the agent can:
1. Store user identity data
2. Fill out one form and learn the pattern
3. Transfer that knowledge to fill similar forms with different field names
"""
import os
import sys
import asyncio
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.personal_assistant.networkx_memory import NetworkXMemoryTools
from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.models import Node, Provenance
from datetime import datetime, timezone


def create_test_memory():
    """Create memory with test user data."""
    memory = NetworkXMemoryTools()
    prov = Provenance(
        source="test",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="form-transfer-test"
    )
    
    # Store user identity
    identity = Node(
        kind="Identity",
        labels=["Identity", "user"],
        props={
            "first_name": "John",
            "last_name": "Smith",
            "full_name": "John Smith",
            "name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "+1-555-123-4567",
            "company": "Acme Corporation",
            "organization": "Acme Corporation",
            "job_title": "Software Engineer",
            "country": "US",
        }
    )
    memory.upsert(identity, prov)
    print(f"✅ Stored Identity: {identity.uuid}")
    
    # Store some form data from a previous form fill
    form_data = Node(
        kind="FormData",
        labels=["FormData", "contact"],
        props={
            "url": "https://example.com/contact",
            "full_name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "+1-555-123-4567",
            "company": "Acme Corporation",
            "message": "Test message content",
        }
    )
    memory.upsert(form_data, prov)
    print(f"✅ Stored FormData: {form_data.uuid}")
    
    return memory, prov


def test_form_retrieval(memory, prov):
    """Test form data retrieval for different forms."""
    retriever = FormDataRetriever(memory)
    
    print("\n" + "="*60)
    print("Testing Form Data Transfer")
    print("="*60)
    
    # First, let's check what's in memory
    print("\n🔍 Memory contents:")
    all_results = memory.search("Identity FormData", top_k=10)
    for r in all_results:
        node = r if isinstance(r, dict) else r.__dict__
        print(f"  - {node.get('kind')}: {list(node.get('props', {}).keys())}")
    
    # Test 1: Contact Form (exact field names)
    print("\n📝 Test 1: Contact Form")
    print("-" * 40)
    contact_fields = ["full_name", "email", "phone", "company", "message"]
    
    # Search for identity/form data
    result = retriever.build_autofill(
        required_fields=contact_fields,
        query="Identity FormData email phone",
        url=None  # No domain filtering
    )
    
    print("Fields requested:", contact_fields)
    print("Autofill result:", json.dumps(result, indent=2))
    
    # Test 2: Registration Form (different field names)
    print("\n📝 Test 2: Registration Form (different field names)")
    print("-" * 40)
    reg_fields = ["first_name", "last_name", "email", "phone", "organization", "job_title", "country"]
    
    result = retriever.build_autofill(
        required_fields=reg_fields,
        query="Identity FormData email name",
        url=None
    )
    
    print("Fields requested:", reg_fields)
    print("Autofill result:", json.dumps(result, indent=2))
    
    # Test 3: Feedback Form (yet another variation)
    print("\n📝 Test 3: Feedback Form (name variations)")
    print("-" * 40)
    feedback_fields = ["name", "email", "phone", "company"]
    
    result = retriever.build_autofill(
        required_fields=feedback_fields,
        query="Identity FormData name email",
        url=None
    )
    
    print("Fields requested:", feedback_fields)
    print("Autofill result:", json.dumps(result, indent=2))
    
    # Test 4: Check field normalization
    print("\n📝 Test 4: Field Normalization Check")
    print("-" * 40)
    
    normalizations = [
        ("full_name", "name"),
        ("email_address", "email"),
        ("telephone", "phone"),
        ("organisation", "organization"),
        ("company_name", "company"),
        ("firstname", "first_name"),
        ("lastname", "last_name"),
    ]
    
    for original, expected in normalizations:
        normalized = retriever.normalize_field_name(original)
        status = "✅" if normalized == expected else "❌"
        print(f"  {status} '{original}' -> '{normalized}' (expected: '{expected}')")


def test_with_playwright(memory, prov):
    """Test form filling with actual Playwright browser."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n⚠️ Playwright not available, skipping browser test")
        return
    
    print("\n" + "="*60)
    print("Testing with Playwright Browser")
    print("="*60)
    
    retriever = FormDataRetriever(memory)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Test each form
        forms = [
            ("Contact Form", "test_contact_form.html", {
                "full_name": "#fullName",
                "email": "#emailAddress",
                "phone": "#phoneNumber",
                "company": "#company",
            }),
            ("Registration Form", "test_registration_form.html", {
                "first_name": "#firstName",
                "last_name": "#lastName",
                "email": "#email",
                "phone": "#phone",
                "organization": "#organization",
            }),
            ("Feedback Form", "test_feedback_form.html", {
                "name": "#customerName",
                "email": "#customerEmail",
                "phone": "#customerPhone",
                "company": "#companyName",
            }),
        ]
        
        for form_name, filename, selectors in forms:
            print(f"\n📝 Testing {form_name}")
            print("-" * 40)
            
            # Navigate to form
            form_path = Path(__file__).parent.parent / "tests" / "fixtures" / filename
            page.goto(f"file://{form_path}")
            
            # Get autofill data - build_autofill returns field_map directly
            fields = list(selectors.keys())
            autofill = retriever.build_autofill(
                required_fields=fields,
                query="Identity FormData email name phone",
                url=None
            )
            print(f"  Autofill data: {autofill}")
            
            # Fill the form
            filled = []
            for field, selector in selectors.items():
                if field in autofill and autofill[field]:
                    try:
                        page.fill(selector, str(autofill[field]))
                        filled.append(field)
                    except Exception as e:
                        print(f"  ❌ Failed to fill {field}: {e}")
            
            print(f"  ✅ Filled fields: {filled}")
            
            # Take screenshot
            screenshot_path = f"/tmp/{filename.replace('.html', '_filled.png')}"
            page.screenshot(path=screenshot_path)
            print(f"  📸 Screenshot: {screenshot_path}")
        
        browser.close()
    
    print("\n✅ Playwright tests complete!")


def main():
    print("="*60)
    print("Form Filler Transfer Test")
    print("="*60)
    
    # Create memory with test data
    memory, prov = create_test_memory()
    
    # Test data retrieval and transfer
    test_form_retrieval(memory, prov)
    
    # Test with Playwright if available (pass same memory)
    test_with_playwright(memory, prov)
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
verify-production.py — Verify The Listening Tree is running correctly on Vercel

This script tests the deployed application on production Vercel URL.

Usage:
    python verify-production.py
    OR with custom URL:
    python verify-production.py --url https://your-custom-url.vercel.app
"""

import httpx
import sys
import time
import json
from pathlib import Path

def load_project_url():
    """Try to find the project URL from Vercel config or .env"""
    vercel_config = Path(".vercel/project.json")
    if vercel_config.exists():
        import json
        with open(vercel_config) as f:
            config = json.load(f)
            project_name = config.get("projectName", "the-listening-tree")
            # The actual URL needs to be retrieved from Vercel
            # For now, return a placeholder that user can customize
            return None
    return None

def test_endpoint(url: str, path: str, expected_status: int = 200) -> tuple[bool, str]:
    """Test an endpoint and return success/failure and message"""
    full_url = f"{url.rstrip('/')}{path}"
    try:
        print(f"  🔍 Testing {path}...", end=" ", flush=True)
        r = httpx.get(full_url, timeout=10)
        
        if r.status_code == expected_status:
            try:
                data = r.json()
                print(f"✅ {r.status_code}")
                print(f"     Response: {json.dumps(data, indent=6)}")
                return True, json.dumps(data)
            except:
                print(f"✅ {r.status_code}")
                print(f"     Response: {r.text[:100]}")
                return True, r.text
        else:
            print(f"❌ Expected {expected_status}, got {r.status_code}")
            print(f"     Response: {r.text[:200]}")
            return False, r.text
    except httpx.TimeoutException:
        print(f"⏱️  Timeout (10s)")
        return False, "Timeout"
    except httpx.ConnectError as e:
        print(f"❌ Connection error")
        return False, str(e)
    except Exception as e:
        print(f"❌ Error: {str(e)[:60]}")
        return False, str(e)

def main():
    print("\n" + "="*70)
    print("🚀 The Listening Tree — Production Verification")
    print("="*70 + "\n")
    
    # Get URL from argument or environment
    url = None
    if len(sys.argv) > 2 and sys.argv[1] == "--url":
        url = sys.argv[2]
    
    if not url:
        print("❌ No URL provided")
        print("\nUsage:")
        print("  python verify-production.py --url https://your-url.vercel.app")
        print("\nExample:")
        print("  python verify-production.py --url https://the-listening-tree-xxx.vercel.app")
        sys.exit(1)
    
    print(f"Testing: {url}\n")
    
    # Test endpoints
    tests = [
        ("/", 303),  # Redirect
        ("/health", 200),
        ("/health/db", 200),
    ]
    
    passed = 0
    failed = 0
    
    for path, expected_status in tests:
        success, response = test_endpoint(url, path, expected_status)
        passed += success
        failed += not success
        print()
    
    # Summary
    print("="*70)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! Application is running correctly.")
        print("\n🎉 Deployment successful!")
        return 0
    else:
        print("❌ Some tests failed. Check the deployment logs:")
        print(f"   vercel logs https://the-listening-tree-xxx.vercel.app")
        return 1

if __name__ == "__main__":
    sys.exit(main())

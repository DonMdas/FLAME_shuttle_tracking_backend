"""
Test script for user authentication system
Run this after starting the server to verify everything works
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_signup():
    print_section("TEST 1: User Signup")
    
    payload = {
        "email": "don.das@flame.edu.in",
        "password": "TestPassword123",
        "role": "student"
    }
    
    response = requests.post(f"{BASE_URL}/auth/signup", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Signup successful!")
        print("📧 Check logs/console for OTP")
        return True
    else:
        print("❌ Signup failed!")
        return False

def test_invalid_email():
    print_section("TEST 2: Invalid Email Domain")
    
    payload = {
        "email": "test2@gmail.com",
        "password": "TestPassword123",
        "role": "student"
    }
    
    response = requests.post(f"{BASE_URL}/auth/signup", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 422:
        print("✅ Correctly rejected invalid email domain!")
        return True
    else:
        print("❌ Should have rejected invalid email!")
        return False

def test_verify_otp():
    print_section("TEST 3: OTP Verification")
    
    otp = input("\nEnter the OTP from logs/email: ")
    
    payload = {
        "email": "don.das@flame.edu.in",
        "otp": otp
    }
    
    response = requests.post(f"{BASE_URL}/auth/verify-otp", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ OTP verification successful!")
        return True
    else:
        print("❌ OTP verification failed!")
        return False

def test_login():
    print_section("TEST 4: User Login")
    
    payload = {
        "email": "don.das@flame.edu.in",
        "password": "TestPassword123"
    }
    
    session = requests.Session()
    response = session.post(f"{BASE_URL}/auth/login", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful!")
        print(f"User: {data['user']['email']}")
        print(f"Role: {data['user']['role']}")
        print(f"Token Type: {data['token_type']}")
        csrf_token = data.get('csrf_token')
        print(f"CSRF Token: {csrf_token[:20]}...")
        return session, csrf_token
    else:
        print("❌ Login failed!")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return None, None

def test_authenticated_schedules(session, csrf_token):
    print_section("TEST 5: Get Schedules (Authenticated)")
    
    headers = {"X-CSRF-Token": csrf_token}
    response = session.get(f"{BASE_URL}/client/schedules", headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        schedules = response.json()
        print(f"✅ Retrieved {len(schedules)} schedules")
        print("Note: Role-based filtering applied automatically from JWT token")
        return True
    else:
        print("❌ Failed to get schedules!")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return False

def test_unauthenticated_schedules():
    print_section("TEST 6: Get Schedules (Unauthenticated)")
    
    response = requests.get(f"{BASE_URL}/client/schedules")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        schedules = response.json()
        print(f"✅ Retrieved {len(schedules)} schedules (regular type)")
        print("Note: Backward compatibility works - returns regular schedules")
        return True
    else:
        print("❌ Failed to get schedules!")
        return False

def test_logout(session):
    print_section("TEST 7: Logout")
    
    response = session.post(f"{BASE_URL}/auth/logout")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Logout successful!")
        return True
    else:
        print("❌ Logout failed!")
        return False

def main():
    print("\n" + "🚀" * 30)
    print("USER AUTHENTICATION SYSTEM - TEST SUITE")
    print("🚀" * 30)
    
    # Test 1: Signup
    if not test_signup():
        print("\n⚠️  Signup failed. User might already exist.")
        print("   Continue to test other features? (y/n)")
        if input().lower() != 'y':
            return
    
    # Test 2: Invalid email
    test_invalid_email()
    
    # Test 3: Verify OTP
    print("\n⚠️  OTP sent! Check:")
    print("   - Console output (if SMTP not configured)")
    print("   - Email inbox (if SMTP configured)")
    print("   - Backend logs/shuttle_tracker_*.log")
    
    if not test_verify_otp():
        print("\n❌ Cannot continue without verified account")
        return
    
    # Test 4: Login
    session, csrf_token = test_login()
    if not session:
        print("\n❌ Cannot continue without login")
        return
    
    # Test 5: Authenticated schedules
    test_authenticated_schedules(session, csrf_token)
    
    # Test 6: Unauthenticated schedules (backward compatibility)
    test_unauthenticated_schedules()
    
    # Test 7: Logout
    test_logout(session)
    
    print_section("TEST SUMMARY")
    print("✅ All basic tests completed!")
    print("\n📋 Next steps:")
    print("   1. Test admin user management endpoints (/api/admin/users)")
    print("   2. Test Google OAuth login")
    print("   3. Test role-based access (create staff user)")
    print("   4. Check API documentation at /docs")
    print("\n💡 For detailed documentation, see:")
    print("   - copilot_files/USER_AUTHENTICATION.md")
    print("   - copilot_files/AUTH_QUICK_START.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user")
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server!")
        print("   Make sure the server is running:")
        print("   $ uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

#!/usr/bin/env python3
"""
Test Anthropic API connection to diagnose LLM integration issues.
"""

import os
import sys
import traceback

def test_anthropic_api():
    """Test direct connection to Anthropic API"""
    print("🧪 Testing Anthropic API Connection")
    print("=" * 50)
    
    # Check environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    print(f"1. API Key Status: {'✅ Found' if api_key else '❌ Not found'}")
    if api_key:
        print(f"   Key format: {api_key[:15]}...{api_key[-4:] if len(api_key) > 15 else api_key}")
    
    # Test import
    try:
        import anthropic
        print("2. Anthropic SDK Import: ✅ Success")
    except ImportError as e:
        print(f"2. Anthropic SDK Import: ❌ Failed - {e}")
        return False
    
    # Test client initialization
    try:
        client = anthropic.Anthropic(api_key=api_key)
        print("3. Client Initialization: ✅ Success")
    except Exception as e:
        print(f"3. Client Initialization: ❌ Failed - {e}")
        return False
    
    # Test simple API call
    try:
        print("4. Testing API Call...")
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            temperature=0.1,
            messages=[{"role": "user", "content": "Hello! Please respond with 'API connection working'"}]
        )
        
        if response and response.content:
            response_text = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
            print(f"4. API Call: ✅ Success")
            print(f"   Response: {response_text}")
            return True
        else:
            print(f"4. API Call: ❌ Empty response")
            return False
            
    except Exception as e:
        print(f"4. API Call: ❌ Failed")
        print(f"   Error: {str(e)}")
        print(f"   Error Type: {type(e).__name__}")
        traceback.print_exc()
        return False

def test_railway_environment():
    """Test if running in Railway and check environment"""
    print("\n🚂 Railway Environment Check")
    print("=" * 30)
    
    # Check for Railway-specific environment variables
    railway_env = os.getenv("RAILWAY_ENVIRONMENT")
    railway_project = os.getenv("RAILWAY_PROJECT_NAME")
    
    print(f"Railway Environment: {railway_env or 'Not detected'}")
    print(f"Railway Project: {railway_project or 'Not detected'}")
    
    # Check all Anthropic-related env vars
    anthropic_vars = [key for key in os.environ.keys() if 'ANTHROPIC' in key.upper()]
    print(f"Anthropic Env Vars: {anthropic_vars}")
    
    return bool(railway_env)

def main():
    print("🔍 LLM Integration Diagnostic Script")
    print("=" * 40)
    
    # Test environment
    is_railway = test_railway_environment()
    
    # Test Anthropic connection
    api_works = test_anthropic_api()
    
    print("\n📊 Summary")
    print("=" * 20)
    
    if api_works:
        print("🎉 Anthropic API is working correctly!")
        print("   The issue might be in the LLM command processor logic.")
        print("   Check Railway logs for specific error messages.")
    else:
        print("❌ Anthropic API connection failed!")
        print("   This explains why LLM responses show fallback messages.")
        
        if is_railway:
            print("\n🔧 Railway Troubleshooting:")
            print("   1. Check Railway environment variables")
            print("   2. Verify ANTHROPIC_API_KEY is set correctly")
            print("   3. Restart Railway deployment")
        else:
            print("\n🔧 Local Troubleshooting:")
            print("   1. Set ANTHROPIC_API_KEY environment variable")
            print("   2. Install anthropic package: pip install anthropic")

if __name__ == "__main__":
    main()
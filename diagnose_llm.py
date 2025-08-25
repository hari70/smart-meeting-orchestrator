#!/usr/bin/env python3
"""
LLM Integration Diagnostic Script
Checks why the LLM is not working and provides solutions
"""

import os
import sys
import logging
from datetime import datetime

def check_environment():
    """Check environment variables"""
    print("🔧 Environment Variables Check:")
    print("=" * 40)
    
    # Check required SMS variables
    surge_key = os.getenv("SURGE_SMS_API_KEY")
    surge_account = os.getenv("SURGE_ACCOUNT_ID")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    print(f"SURGE_SMS_API_KEY: {'✅ SET' if surge_key else '❌ NOT SET'}")
    print(f"SURGE_ACCOUNT_ID: {'✅ SET' if surge_account else '❌ NOT SET'}")
    print(f"ANTHROPIC_API_KEY: {'✅ SET' if anthropic_key else '❌ NOT SET (PROBLEM!)'}")
    
    if anthropic_key:
        print(f"ANTHROPIC_API_KEY preview: {anthropic_key[:10]}..." if len(anthropic_key) > 10 else "Key too short!")
    
    return bool(anthropic_key)

def check_anthropic_import():
    """Check if anthropic module can be imported"""
    print("\n📦 Anthropic Module Check:")
    print("=" * 40)
    
    try:
        import anthropic
        print("✅ Anthropic module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Cannot import anthropic module: {e}")
        print("💡 Solution: pip install anthropic")
        return False

def test_llm_processor():
    """Test LLM processor initialization"""
    print("\n🧠 LLM Processor Test:")
    print("=" * 40)
    
    try:
        from llm_integration.enhanced_command_processor import LLMCommandProcessor
        
        # Create processor instance
        processor = LLMCommandProcessor(None, None, None, None)
        
        print(f"LLM Enabled: {'✅ YES' if processor.llm_enabled else '❌ NO'}")
        
        if processor.llm_enabled:
            print("✅ LLM processor successfully initialized")
            print("✅ Claude client ready")
        else:
            print("❌ LLM processor in fallback mode")
            print("💡 This is why you're seeing 'LLM unavailable' messages")
        
        return processor.llm_enabled
        
    except Exception as e:
        print(f"❌ Error testing LLM processor: {e}")
        return False

def test_basic_claude_call():
    """Test a basic Claude API call"""
    print("\n🔌 Claude API Test:")
    print("=" * 40)
    
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("❌ No ANTHROPIC_API_KEY found - skipping API test")
        return False
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        
        print("🚀 Testing Claude API call...")
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'API test successful' in exactly 3 words"}]
        )
        
        result = response.content[0].text
        print(f"✅ Claude API response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Claude API test failed: {e}")
        print("💡 Check if your ANTHROPIC_API_KEY is valid")
        return False

def provide_solutions():
    """Provide solutions based on diagnostic results"""
    print("\n🛠️ SOLUTIONS:")
    print("=" * 40)
    
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not anthropic_key:
        print("❌ PROBLEM: ANTHROPIC_API_KEY not set")
        print("\n💡 SOLUTION FOR RAILWAY DEPLOYMENT:")
        print("1. Go to your Railway dashboard")
        print("2. Navigate to your project")
        print("3. Go to Variables tab")
        print("4. Add environment variable:")
        print("   Name: ANTHROPIC_API_KEY")
        print("   Value: your_anthropic_api_key_here")
        print("5. Redeploy your application")
        print("\n💡 SOLUTION FOR LOCAL DEVELOPMENT:")
        print("export ANTHROPIC_API_KEY=your_anthropic_api_key_here")
        
    else:
        print("✅ ANTHROPIC_API_KEY is set")
        print("💡 If LLM still not working, check:")
        print("1. API key validity")
        print("2. Network connectivity")
        print("3. Railway deployment logs")

def main():
    """Run complete diagnostic"""
    print("🔍 Smart Meeting Orchestrator - LLM Diagnostic")
    print("=" * 50)
    print(f"Diagnostic run at: {datetime.now()}")
    
    # Run all checks
    env_ok = check_environment()
    import_ok = check_anthropic_import()
    processor_ok = test_llm_processor()
    
    # Only test API if environment is set up
    api_ok = False
    if env_ok and import_ok:
        api_ok = test_basic_claude_call()
    
    # Provide solutions
    provide_solutions()
    
    # Summary
    print("\n📊 DIAGNOSTIC SUMMARY:")
    print("=" * 50)
    print(f"Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"Anthropic Import: {'✅' if import_ok else '❌'}")
    print(f"LLM Processor: {'✅' if processor_ok else '❌'}")
    print(f"Claude API: {'✅' if api_ok else '❌' if env_ok else '⏭️ Skipped'}")
    
    if all([env_ok, import_ok, processor_ok, api_ok]):
        print("\n🎉 ALL SYSTEMS GO! LLM should be working")
    else:
        print("\n⚠️ ISSUES FOUND - Follow solutions above")
        
        if not env_ok:
            print("🎯 PRIMARY ISSUE: Missing ANTHROPIC_API_KEY environment variable")

if __name__ == "__main__":
    main()
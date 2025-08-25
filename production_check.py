#!/usr/bin/env python3
"""
Production Readiness Verification Script
Checks if the Smart Meeting Orchestrator is ready for Railway deployment
"""

import os
import sys
import importlib.util
from pathlib import Path

def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a required file exists"""
    if Path(file_path).exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description} MISSING: {file_path}")
        return False

def check_environment_vars() -> bool:
    """Check required environment variables"""
    print("\n🔧 Environment Variables:")
    
    required_vars = {
        "SURGE_SMS_API_KEY": "SMS API Key",
        "SURGE_ACCOUNT_ID": "SMS Account ID"
    }
    
    optional_vars = {
        "ANTHROPIC_API_KEY": "LLM Integration (optional)",
        "ADMIN_API_KEY": "Admin API Security (optional)"
    }
    
    all_good = True
    
    for var, desc in required_vars.items():
        if os.getenv(var):
            print(f"✅ {desc}: SET")
        else:
            print(f"❌ {desc}: NOT SET (REQUIRED)")
            all_good = False
    
    for var, desc in optional_vars.items():
        if os.getenv(var):
            print(f"✅ {desc}: SET")
        else:
            print(f"⚠️ {desc}: NOT SET (optional)")
    
    return all_good

def check_imports() -> bool:
    """Check if all required modules can be imported"""
    print("\n📦 Dependencies:")
    
    required_modules = [
        ("fastapi", "FastAPI Framework"),
        ("uvicorn", "ASGI Server"),
        ("sqlalchemy", "Database ORM"),
        ("requests", "HTTP Client"),
        ("pydantic", "Data Validation")
    ]
    
    optional_modules = [
        ("anthropic", "LLM Integration (optional)"),
        ("pytest", "Testing Framework (dev)")
    ]
    
    all_good = True
    
    for module, desc in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {desc}: Available")
        except ImportError:
            print(f"❌ {desc}: NOT AVAILABLE (REQUIRED)")
            all_good = False
    
    for module, desc in optional_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {desc}: Available")
        except ImportError:
            print(f"⚠️ {desc}: Not available (optional)")
    
    return all_good

def check_application_structure() -> bool:
    """Check if application structure is correct"""
    print("\n📁 Application Structure:")
    
    required_files = [
        ("main.py", "FastAPI Application Entry Point"),
        ("requirements.txt", "Python Dependencies"),
        ("railway.toml", "Railway Deployment Config"),
        ("app/config.py", "Application Configuration"),
        ("app/services.py", "Service Initialization"),
        ("database/models.py", "Database Models"),
        ("sms_coordinator/surge_client.py", "SMS Integration"),
        ("llm_integration/enhanced_command_processor.py", "LLM Processing")
    ]
    
    all_good = True
    for file_path, description in required_files:
        if not check_file_exists(file_path, description):
            all_good = False
    
    return all_good

def test_basic_imports() -> bool:
    """Test basic application imports"""
    print("\n🧪 Application Import Test:")
    
    try:
        from app.config import get_settings
        settings = get_settings()
        print("✅ Configuration loading: OK")
        
        from database.models import Team, TeamMember, Meeting
        print("✅ Database models: OK")
        
        from sms_coordinator.surge_client import SurgeSMSClient
        print("✅ SMS client: OK")
        
        from llm_integration.enhanced_command_processor import LLMCommandProcessor
        print("✅ LLM processor: OK")
        
        # Test FastAPI app creation
        from main import app
        print("✅ FastAPI application: OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def main():
    """Run all production readiness checks"""
    print("🚀 Smart Meeting Orchestrator - Production Readiness Check")
    print("=" * 60)
    
    checks = [
        ("Application Structure", check_application_structure),
        ("Dependencies", check_imports),
        ("Environment Variables", check_environment_vars),
        ("Application Imports", test_basic_imports)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 Checking {check_name}...")
        result = check_func()
        results.append((check_name, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 PRODUCTION READINESS SUMMARY:")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 PRODUCTION READY! ✅")
        print("Your Smart Meeting Orchestrator is ready for Railway deployment!")
        print("\nNext steps:")
        print("1. git add . && git commit -m 'Production ready'")
        print("2. Deploy to Railway")
        print("3. Configure environment variables in Railway dashboard")
        print("4. Set up Surge SMS webhook to your Railway URL")
    else:
        print("⚠️ PRODUCTION NOT READY ❌")
        print("Please fix the failed checks above before deploying.")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Railway Deployment Troubleshooting and Fix Script
"""

import os
import subprocess
import json

def check_git_status():
    """Check git status and prepare for deployment"""
    print("📂 Checking Git Status")
    print("=" * 30)
    
    try:
        # Check if we have uncommitted changes
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, cwd='.')
        
        if result.stdout.strip():
            print("⚠️  Uncommitted changes found:")
            print(result.stdout)
            print("\n💡 Need to commit changes before Railway can deploy")
            return False
        else:
            print("✅ Git working directory is clean")
            return True
            
    except Exception as e:
        print(f"❌ Error checking git status: {e}")
        return False

def check_railway_config():
    """Verify Railway configuration"""
    print("\n🚂 Railway Configuration Check")
    print("=" * 40)
    
    # Check if railway.toml exists and is valid
    if os.path.exists('railway.toml'):
        print("✅ railway.toml found")
        with open('railway.toml', 'r') as f:
            content = f.read()
            print("📄 Contents:")
            print(content)
            
        # Check for correct start command
        if 'uvicorn main:app' in content:
            print("✅ Start command looks correct")
        else:
            print("❌ Start command may be incorrect")
            
    else:
        print("❌ railway.toml not found")
        return False
    
    # Check if main.py exists
    if os.path.exists('main.py'):
        print("✅ main.py found")
    else:
        print("❌ main.py not found - this is the entrypoint!")
        return False
    
    return True

def check_requirements():
    """Check if requirements.txt has all needed dependencies"""
    print("\n📦 Dependencies Check")
    print("=" * 30)
    
    if os.path.exists('requirements.txt'):
        print("✅ requirements.txt found")
        with open('requirements.txt', 'r') as f:
            deps = f.read()
            
        required_deps = ['fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2-binary']
        missing_deps = []
        
        for dep in required_deps:
            if dep not in deps:
                missing_deps.append(dep)
        
        if missing_deps:
            print(f"❌ Missing dependencies: {missing_deps}")
            return False
        else:
            print("✅ All required dependencies present")
            return True
    else:
        print("❌ requirements.txt not found")
        return False

def suggest_fixes():
    """Provide step-by-step fix instructions"""
    print("\n🛠️  RAILWAY DEPLOYMENT FIXES")
    print("=" * 50)
    
    print("""
🔧 IMMEDIATE ACTIONS TO FIX RAILWAY:

1. **Commit and Push Changes:**
   ```bash
   git add .
   git commit -m "Fix Railway deployment configuration"
   git push origin main
   ```

2. **Check Railway Dashboard:**
   - Go to: https://railway.app/dashboard
   - Find your Smart Meeting Orchestrator project
   - Go to Deployments tab
   - Check if latest deployment failed
   - Look at build logs for errors

3. **Verify Environment Variables in Railway:**
   - Go to Variables tab in Railway
   - Ensure these are set:
     ✓ ANTHROPIC_API_KEY=sk-ant-api03-...
     ✓ SURGE_SMS_API_KEY=...
     ✓ SURGE_ACCOUNT_ID=...
     ✓ DATABASE_URL (auto-set by Railway)

4. **Force Redeploy:**
   - In Railway dashboard, click "Deploy Latest Commit"
   - Or add a dummy change and push again

5. **Check Logs:**
   - In Railway, go to Logs tab
   - Look for startup errors
   - Should see: "Smart Meeting Orchestrator started"

🔍 DEBUGGING STEPS:

If still not working after above:

A. **Check Start Command:**
   Railway should use: `uvicorn main:app --host 0.0.0.0 --port $PORT`

B. **Verify File Structure:**
   ✓ main.py (entrypoint)
   ✓ app/ directory with routers
   ✓ requirements.txt
   ✓ railway.toml

C. **Test Locally First:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   curl http://localhost:8000/health
   ```

D. **Railway Build Issues:**
   - Check if Nixpacks detected Python correctly
   - Verify no conflicting configuration files
   - Ensure no syntax errors in Python files

🚨 COMMON RAILWAY ISSUES:

❌ **App shows Railway default page**
   → Railway isn't running your app
   → Check deployment logs for Python/dependency errors
   → Verify start command in railway.toml

❌ **404 on all endpoints**
   → App running but routes not working
   → Check FastAPI router inclusion in main.py
   → Verify no import errors in modules

❌ **500 Internal Server Error**
   → App starts but crashes on requests
   → Check database connection (DATABASE_URL)
   → Verify all environment variables set
""")

def run_local_test():
    """Test the app locally to ensure it works"""
    print("\n🧪 Local Test (Optional)")
    print("=" * 30)
    
    print("To test locally before deploying:")
    print("1. Run: uvicorn main:app --host 0.0.0.0 --port 8000")
    print("2. Test: curl http://localhost:8000/health")
    print("3. Should return: {\"status\": \"healthy\"}")

def main():
    """Run complete Railway deployment fix"""
    print("🚂 Railway Deployment Troubleshooting")
    print("=" * 45)
    
    # Run checks
    git_ok = check_git_status()
    config_ok = check_railway_config()
    deps_ok = check_requirements()
    
    # Summary
    print(f"\n📊 STATUS SUMMARY")
    print("=" * 30)
    print(f"Git Status: {'✅' if git_ok else '❌'}")
    print(f"Railway Config: {'✅' if config_ok else '❌'}")
    print(f"Dependencies: {'✅' if deps_ok else '❌'}")
    
    # Provide next steps
    suggest_fixes()
    run_local_test()
    
    if git_ok and config_ok and deps_ok:
        print("\n🎉 Configuration looks good!")
        print("💡 Main issue is likely Railway not picking up latest deployment")
        print("📤 Try: git commit + git push to trigger redeploy")
    else:
        print("\n⚠️  Issues found - fix them first, then redeploy")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Add missing team members to the Family team
"""

import requests
import json

def add_team_member():
    """Add Rick to the Family team"""
    
    print("🔧 Adding Missing Team Member")
    print("=" * 30)
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    # First, let's check who's currently in the team
    print("1. Checking current team members...")
    try:
        response = requests.get(f"{railway_url}/debug/sms-flow-status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            current_members = status.get('members', [])
            print(f"   Current team members: {len(current_members)}")
            for member in current_members:
                print(f"   - {member.get('name', 'Unknown')} ({member.get('phone', 'No phone')})")
        else:
            print(f"   ⚠️ Could not check current members: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Error checking members: {e}")
    
    print()
    print("2. Adding Rick to the team...")
    
    # Prepare Rick's details
    rick_data = {
        "name": "Rick",
        "phone": "+15551234567",  # Placeholder - you should replace with real phone
        "email": "rick@example.com",  # Placeholder - you should replace with real email
        "is_admin": False
    }
    
    print(f"   Name: {rick_data['name']}")
    print(f"   Phone: {rick_data['phone']}")
    print(f"   Email: {rick_data['email']}")
    print()
    
    # Note: We don't have a direct API endpoint to add team members
    # This would need to be done via database or admin endpoint
    
    print("📝 Manual Steps Required:")
    print("=" * 25)
    print("Since there's no public API to add team members, you need to:")
    print()
    print("Option 1: Add via Database (if you have access)")
    print("   - Connect to Railway PostgreSQL database")
    print("   - Add record to team_members table")
    print()
    print("Option 2: Create Admin Endpoint")
    print("   - Add POST /admin/team-members endpoint")
    print("   - Include proper API key authentication")
    print()
    print("Option 3: For Testing (Temporary Fix)")
    print("   - Modify the team member lookup logic")
    print("   - Add fallback for unknown names")
    print()
    
    # For now, let's suggest the data format needed
    print("Database Record Format:")
    print("-" * 20)
    print("INSERT INTO team_members (id, team_id, name, phone, email, is_admin, created_at)")
    print("VALUES (")
    print("  gen_random_uuid(),")
    print("  (SELECT id FROM teams WHERE name = 'Family'),")
    print(f"  '{rick_data['name']}',")
    print(f"  '{rick_data['phone']}',")
    print(f"  '{rick_data['email']}',")
    print(f"  {rick_data['is_admin']},")
    print("  NOW()")
    print(");")
    print()
    
    print("🔧 Alternative: Update existing member")
    print("If 'Rick' is actually a nickname for an existing member:")
    print("   - Update their name in the database")
    print("   - Or add nickname handling in the code")

def check_email_addresses():
    """Check which team members are missing email addresses"""
    
    print("\n🔍 Email Address Audit")
    print("=" * 22)
    
    railway_url = "https://helpful-solace-production.up.railway.app"
    
    try:
        response = requests.get(f"{railway_url}/debug/sms-flow-status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            members = status.get('members', [])
            members_with_email = status.get('members_with_email', 0)
            
            print(f"Team members: {len(members)}")
            print(f"Members with email: {members_with_email}")
            print(f"Members missing email: {len(members) - members_with_email}")
            print()
            
            print("Email Status by Member:")
            for member in members:
                name = member.get('name', 'Unknown')
                has_email = member.get('has_email', False)
                status_icon = "✅" if has_email else "❌"
                print(f"   {status_icon} {name}")
                
            if members_with_email < len(members):
                print()
                print("💡 To fix calendar invitations:")
                print("   1. Add email addresses for team members")
                print("   2. Update database records with real emails")
                print("   3. Test calendar invitation functionality")
                
        else:
            print(f"❌ Could not check email status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking emails: {e}")

if __name__ == "__main__":
    add_team_member()
    check_email_addresses()
#!/usr/bin/env python3
"""Test script to verify Anthropic API key works"""
import os
import sys

def test_anthropic():
    try:
        import anthropic
        print(f"✅ Anthropic library available: {anthropic.__version__}")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ ANTHROPIC_API_KEY environment variable not set")
            return False

        print(f"✅ API key found (length: {len(api_key)})")
        print(f"🔍 API key starts with: {api_key[:20]}...")

        # Test the client initialization
        client = anthropic.Anthropic(api_key=api_key)
        print("✅ Anthropic client initialized successfully")

        # Try a simple test message
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                temperature=0.0,
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Say 'Hello World'"}]
            )
            print(f"✅ API call successful: {response.content[0].text[:50]}...")
            return True
        except Exception as e:
            print(f"❌ API call failed: {e}")
            return False

    except ImportError as e:
        print(f"❌ Anthropic library not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing Anthropic API key...")
    success = test_anthropic()
    sys.exit(0 if success else 1)

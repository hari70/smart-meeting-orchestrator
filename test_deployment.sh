#!/bin/bash

# Smart Meeting Orchestrator - Deployment Test Script
# Replace YOUR_RAILWAY_URL with your actual Railway app URL

RAILWAY_URL="https://your-app-name.up.railway.app"

echo "🧪 Testing Smart Meeting Orchestrator Deployment"
echo "================================================="
echo "Railway URL: $RAILWAY_URL"
echo ""

echo "1. 🏥 Testing Health Check..."
health_response=$(curl -s "$RAILWAY_URL/health")
echo "Response: $health_response"

if [[ $health_response == *"healthy"* ]]; then
    echo "✅ Health check passed!"
else
    echo "❌ Health check failed!"
    exit 1
fi

echo ""
echo "2. 📱 Testing Root Endpoint..."
root_response=$(curl -s "$RAILWAY_URL/")
echo "Response: $root_response"

if [[ $root_response == *"Smart Meeting Orchestrator"* ]]; then
    echo "✅ Root endpoint working!"
else
    echo "❌ Root endpoint failed!"
    exit 1
fi

echo ""
echo "3. 📚 Testing API Documentation..."
docs_response=$(curl -s -o /dev/null -w "%{http_code}" "$RAILWAY_URL/docs")
echo "HTTP Status: $docs_response"

if [[ $docs_response == "200" ]]; then
    echo "✅ API docs accessible!"
    echo "🌐 View docs at: $RAILWAY_URL/docs"
else
    echo "❌ API docs failed!"
fi

echo ""
echo "4. 🔧 Testing SMS Webhook Endpoint..."
webhook_response=$(curl -s -X POST "$RAILWAY_URL/webhook/sms" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message.received",
    "data": {
      "body": "test deployment",
      "conversation": {
        "contact": {
          "first_name": "Test",
          "last_name": "User",
          "phone_number": "+1234567890"
        }
      }
    }
  }')

echo "Response: $webhook_response"

if [[ $webhook_response == *"processed"* ]]; then
    echo "✅ SMS webhook working!"
else
    echo "⚠️ SMS webhook needs team member setup first"
fi

echo ""
echo "================================================="
echo "🎉 Deployment test complete!"
echo ""
echo "Next steps:"
echo "1. Set environment variables in Railway dashboard"
echo "2. Update Surge webhook URL to: $RAILWAY_URL/webhook/sms"
echo "3. Send test SMS to verify end-to-end functionality"
echo ""
echo "📖 Full documentation: DEPLOYMENT_GUIDE.md"
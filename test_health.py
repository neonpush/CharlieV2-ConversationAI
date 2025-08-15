"""
Quick test script to verify our health endpoints work.

This creates a minimal .env file and tests the app.
"""

import os
import sys

# Create a minimal .env file for testing with PostgreSQL
# PostgreSQL URL format: postgresql://username@localhost/database_name
# On Mac, the default user is your system username, no password needed
import os
username = os.getenv('USER', 'postgres')

test_env = f"""
DATABASE_URL=postgresql://{username}@localhost/lead_management
WEBHOOK_SECRET=test-secret
TWILIO_ACCOUNT_SID=test-sid
TWILIO_AUTH_TOKEN=test-token
TWILIO_FROM_NUMBER=+1234567890
PUBLIC_BASE_URL=http://localhost:8000
ELEVENLABS_API_KEY=test-key
DEBUG=true
PORT=8000
"""

# Write the test .env file
with open('.env', 'w') as f:
    f.write(test_env)

print("Created test .env file")
print("Starting the app...")
print("\nYou can test the endpoints at:")
print("  http://localhost:8000/health/healthz")
print("  http://localhost:8000/health/readyz")
print("  http://localhost:8000/docs (API documentation)")
print("\nPress Ctrl+C to stop the server")

# Now run the app
os.system("python run.py")
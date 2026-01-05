import os
from dotenv import load_dotenv
from google import genai
import sys

def debug_auth():
    print("--- Debugging API Key Configuration ---")
    
    # 1. Load .env explicitly
    load_dotenv(override=True)
    
    # 2. Check Environment Variable
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ ERROR: 'GEMINI_API_KEY' not found in environment variables.")
        return
    
    print(f"✅ Found 'GEMINI_API_KEY'")
    print(f"   Length: {len(api_key)}")
    print(f"   Preview: {api_key[:4]}...{api_key[-4:]}")
    
    if api_key.startswith('"') or api_key.endswith('"'):
         print("⚠️ WARNING: Key appears to be wrapped in quotes. This might be part of the key string if not parsed correctly.")

    if '\n' in api_key or '\r' in api_key:
         print("⚠️ WARNING: Key contains newline characters!")

    # 3. Test google-genai Client
    print("\n--- Testing Gemini API Connection ---")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello, just testing connection."
        )
        print("✅ API Call Successful!")
        print(f"   Response: {response.text}")
    except Exception as e:
        print("❌ API Call Failed!")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {e}")

if __name__ == "__main__":
    debug_auth()

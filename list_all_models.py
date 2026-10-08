import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

print("Listing all available models...")
for model in client.models.list():
    print(f"- {model.name} (Actions: {model.supported_actions})")

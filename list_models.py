import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)

print("Listing available models...")
for model in client.models.list():
    if "embed" in model.name.lower():
        print(f"Name: {model.name}, Supported Methods: {model.supported_actions}")

from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GROQ_API_KEY")
print(f"Key loaded: {key[:10] if key else 'NOT FOUND'}")

client = Groq(api_key=key)

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {
            "role": "user",
            "content": "talk about life"
        }
    ]
)

print(response.choices[0].message.content)
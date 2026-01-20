from openai import OpenAI
import os

api_key = "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"
base_url = "https://integrate.api.nvidia.com/v1"

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

print(f"Connecting to {base_url}...")

try:
    completion = client.chat.completions.create(
        model="minimaxai/minimax-m2",
        messages=[{"role": "user", "content": "Hello, translate 'Hello World' to Chinese."}],
        temperature=0.2,
        top_p=0.7,
        max_tokens=1024,
    )

    print("Success!")
    print("Response:", completion.choices[0].message.content)

except Exception as e:
    print(f"Error: {e}")

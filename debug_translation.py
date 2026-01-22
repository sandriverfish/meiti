import os
from openai import OpenAI

nvidia_key = "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"
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=nvidia_key
)

texts = [
    "Today, I'm excited to announce the AMD Ryzen AI Halo,",
    "a new reference platform for local AI deployment.",
    "Now, I would say this is pretty beautiful."
]

delimiter = " ||| "
combined_text = delimiter.join(texts)

prompt = (
    f"Translate the following text segments to Simplified Chinese for subtitles. "
    f"Keep the segments separated by '{delimiter}'. "
    "Translate the full meaning of each segment directly. "
    "Do NOT summarize. Do NOT shorten. Do NOT omit details. "
    "Return only the translated string joined by the delimiter.\n\n"
    f"Text: {combined_text}"
)

completion = client.chat.completions.create(
    model="minimaxai/minimax-m2",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)
content = completion.choices[0].message.content.strip()
print(f"--- Response ---\n{content}\n--- End ---")

segments = content.split(delimiter.strip())
print(f"Segments count: {len(segments)}")
for i, s in enumerate(segments):
    print(f"{i}: {s.strip()}")

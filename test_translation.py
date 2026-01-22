import os
import json
from openai import OpenAI

# Mocking the class structure or just testing the logic directly
class TranslationTester:
    def __init__(self, key):
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", api_key=key
        )
        self.model_name = "minimaxai/minimax-m2"
        self.target_lang = "zh"

    def _translate_batch(self, texts):
        print(f"[*] Translating {len(texts)} segments in batch...")
        
        system_prompt = (
            "You are a professional subtitle translator. Translate the following English subtitles to Chinese (Simplified).\n"
            "Rules:\n"
            "1. Output must be a VALID JSON list of objects.\n"
            "2. Each object must have: 'original' (str), 'translated' (str), and 'speaker' (str).\n"
            "3. 'speaker' should be 'A' for the main/first speaker, 'B' for a second speaker (if detected), etc. "
            "If unsure or monologue, default to 'A'.\n"
            "4. Keep the translation concise and natural. Do not summarize.\n"
            "5. Maintain the same number of items as the input.\n"
            "6. Input will be a JSON list of strings.\n"
        )

        chunk_size = 50
        all_results = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            user_content = json.dumps(chunk, ensure_ascii=False)

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                )
                
                content = response.choices[0].message.content.strip()
                print(f"[DEBUG] Raw response len: {len(content)}")
                
                # Robust extraction: Find the first '[' and last ']'
                start_idx = content.find('[')
                end_idx = content.rfind(']')
                
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx : end_idx + 1]
                    print(f"[DEBUG] Extracted JSON start: {json_str[:50]}...")
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        all_results.extend(parsed)
                    else:
                         print("[-] Parsed JSON is not a list")
                else:
                    print("[-] Could not find JSON list brackets [] in response")

            except Exception as e:
                print(f"[-] Error: {e}")
                import traceback
                traceback.print_exc()
        
        return all_results

if __name__ == "__main__":
    TEST_KEY = "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"
    
    tester = TranslationTester(TEST_KEY)
    
    sample_texts = [
        "So good to see you.",
        "Great to see you too.",
        "Last time I saw you I was in San Francisco.",
        "Gemini 3 is out.",
        "We've heard that OpenAI called a code red internally."
    ]
    
    results = tester._translate_batch(sample_texts)
    print(json.dumps(results, indent=2, ensure_ascii=False))

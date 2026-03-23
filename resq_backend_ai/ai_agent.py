import cv2
import json
import google.generativeai as genai
from config import GEMINI_API_KEY
from PIL import Image

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class AIAnalyzer:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def analyze_scene(self, image_array):
        """Send scene to Gemini for deep contextual analysis."""
        if not GEMINI_API_KEY:
            return {"error": "API Key not set."}

        # Convert CV2 BGR to RGB, then to PIL Image for Gemini
        rgb_img = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        prompt = """
        You are an advanced search and rescue AI analyzing a drone camera feed. 
        A victim has been detecting in this frame. Look at them and their surroundings.
        Return a strict JSON response with no markdown formatting containing these keys:
        - "situation_summary": A brief 1-sentence description of what is happening.
        - "hazards": A list of strings analyzing the surrounding environment (e.g., ["rubble", "unstable structure", "water", "fire"]). If none, return [].
        - "victim_status": Best guess of victim status based on visual cues (e.g., "trapped under debris", "conscious", "unconscious", "bleeding").
        - "urgency_level": Must be exactly "CRITICAL", "HIGH", "MEDIUM", or "LOW".
        """

        try:
            response = self.model.generate_content([prompt, pil_img])
            res_text = response.text.strip()
            # Strip markdown block if model adds it
            if res_text.startswith('```json'):
                res_text = res_text[7:]
            elif res_text.startswith('```'):
                res_text = res_text[3:]
            if res_text.endswith('```'):
                res_text = res_text[:-3]
            
            return json.loads(res_text.strip())

        except Exception as e:
            print(f"[AI Analyzer Error]: {e}")
            return {"error": str(e)}

# Quick test script
if __name__ == "__main__":
    import numpy as np
    # Create a dummy image (black square) just to test the API connection
    dummy_img = np.zeros((500, 500, 3), dtype=np.uint8)
    analyzer = AIAnalyzer()
    print("Testing connection to Google Gemini...")
    res = analyzer.analyze_scene(dummy_img)
    print("Response:", res)
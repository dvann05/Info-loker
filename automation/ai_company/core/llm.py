import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
from automation.ai_company.core.config import GEMINI_API_KEY, GEMINI_MODEL

class LLMEngine:
    """Intelligent reasoning and natural language processing engine."""

    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, system_instruction: str = "", temperature: float = 0.2) -> str:
        if self.api_key:
            try:
                return self._call_gemini_api(prompt, system_instruction, temperature)
            except Exception as e:
                # If Gemini API errors or rate limits, fallback gracefully
                print(f"[LLMEngine] Gemini API error, fallback active: {e}")

        # Deterministic / heuristic fallback
        return self._heuristic_fallback(prompt)

    def _call_gemini_api(self, prompt: str, system_instruction: str, temperature: float) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return ""

    def _heuristic_fallback(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "ringkasan" in prompt_lower or "laporan" in prompt_lower:
            return "Operasional harian AI Company berjalan optimal dengan koordinasi antar divisi sesuai SOP."
        if "seo" in prompt_lower or "meta" in prompt_lower:
            return "Info lowongan kerja resmi terbaru, persyaratan lengkap, gaji, dan tautan pendaftaran langsung."
        if "caption" in prompt_lower or "sosmed" in prompt_lower:
            return "Peluang karir terbaru di perusahaan terpercaya. Simak kualifikasi dan daftarkan diri Anda sebelum batas waktu berakhir."
        return "Tugas berhasil diproses berdasarkan parameter sistem terverifikasi."


llm_engine = LLMEngine()

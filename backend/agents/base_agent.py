from abc import ABC, abstractmethod
from typing import Dict, Any
import os
import asyncio
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

# ─── Groq client (lazy init) ────────────────────────────────────────────────
_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import AsyncGroq
            _groq_client = AsyncGroq(
                api_key=os.environ["GROQ_API_KEY"],
                timeout=15.0  # 🔥 Timeout global
            )
            print("✅ Groq client initialisé")
        except ImportError:
            raise RuntimeError("Groq non installé : pip install groq")
    return _groq_client

# ─── Mapping modèles (MODÈLES ACTIFS GROQ) ───────────────────────────────────
GROQ_MODEL_MAP = {
    "mistral:7b":    "llama-3.1-8b-instant",      # Rapide
    "qwen:7b":       "llama-3.1-8b-instant",
    "mistral:latest":"llama-3.1-8b-instant",
    "qwen:latest":   "llama-3.1-8b-instant",
}

# ─── Cache LRU pour les réponses fréquentes ──────────────────────────────────
_cache = {}
CACHE_MAX_SIZE = 100

# ─── Système prompt bancaire ────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un conseiller bancaire expert d'Attijariwafa Bank (AWB).

RÈGLES :
1. Réponds dans la langue du client (français, anglais ou arabe)
2. Sois précis, professionnel et concis (max 3 phrases)
3. N'utilise JAMAIS '[votre nom]', '[nom]' ou '[prénom]'. Utilise 'je'
4. Ne demande jamais de mot de passe ou code PIN

Réponse courte et utile."""

class BaseAgent(ABC):
    def __init__(self, agent_id: str, model: str):
        self.agent_id = agent_id
        self.model = model
        self.hitl_threshold = None

    @abstractmethod
    async def process(self, message: str, context: Dict = None) -> Dict:
        pass

    def _matches(self, text: str, keywords: list) -> bool:
        text_lower = text.lower()
        for kw in keywords:
            if kw in text_lower:
                return True
            for word in text_lower.split():
                if len(kw) > 4 and (kw[:4] in word or word[:4] in kw):
                    return True
        return False

    def detect_language(self, text: str) -> str:
        if any('\u0600' <= c <= '\u06FF' for c in text):
            return "arabe"
        english_keywords = ["hello", "hi", "how", "what", "please", "thank", "card", "account", "money", "block", "credit"]
        if any(kw in text.lower() for kw in english_keywords):
            return "anglais"
        return "francais"

    async def call_llm(self, prompt: str, system: str = None, rag_context: str = None,
                       max_tokens: int = 150, temperature: float = 0.3) -> str:
        """
        Appel Groq API optimisé pour la vitesse.
        """
        cache_key = f"{self.agent_id}_{hash(prompt)}_{hash(system or '')}"
        if cache_key in _cache:
            print(f"🟢 Cache hit {self.agent_id}")
            return _cache[cache_key]

        groq = _get_groq()
        groq_model = GROQ_MODEL_MAP.get(self.model, "llama-3.1-8b-instant")

        lang = self.detect_language(prompt)
        lang_instruction = f" Réponds en {lang}."

        sys_msg = system or SYSTEM_PROMPT
        sys_msg += lang_instruction

        user_content = prompt
        if rag_context:
            user_content = f"[Contexte]\n{rag_context[:500]}\n\n[Question]\n{prompt}"

        try:
            print(f"🟢 Groq {self.agent_id}...")

            completion = await asyncio.wait_for(
                groq.chat.completions.create(
                    model=groq_model,
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=12.0
            )

            response = completion.choices[0].message.content
            print(f"🟢 Réponse reçue ({len(response)} caractères)")

            if len(_cache) < CACHE_MAX_SIZE:
                _cache[cache_key] = response

            return response

        except asyncio.TimeoutError:
            print(f"🔴 Timeout {self.agent_id}")
            return self._fallback_simulation(prompt)
        except Exception as e:
            print(f"🔴 ERREUR {self.agent_id}: {e}")
            return self._fallback_simulation(prompt)

    def _fallback_simulation(self, prompt: str) -> str:
        p = prompt.lower()

        if self._matches(p, ["solde", "balance", "compte"]):
            return "Votre solde est disponible sur l'application mobile AWB."
        elif self._matches(p, ["carte", "opposition", "perdue", "volée"]):
            return "Opposition immédiate : 0800 00 11 00. Votre carte sera bloquée sous 5 minutes."
        elif self._matches(p, ["credit", "crédit", "pret"]):
            return "Pour un crédit, un conseiller vous contactera sous 24h."
        elif self._matches(p, ["fraude", "piratage", "arnaque"]):
            return "Urgence fraude : 0801 00 22 22 (24h/24). Gel préventif activé."
        else:
            return "Je suis votre conseiller bancaire AWB. Comment puis-je vous aider ?"
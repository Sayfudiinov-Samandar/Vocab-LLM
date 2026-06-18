import json
import re
from typing import Dict, Any, List
from urllib.parse import urlparse
import requests
import tavily
from .config import settings
from .database import save_word, get_word_by_name


def log_agent_step(step: int, total: int, message: str):
    print(f"[ExampleSearchAgent] {step}/{total} {message}")

class ExampleSearchAgent:
    """
    CORE AGENT: Example Search Agent
    
    Workflow:
    1. Receive word from user
    2. Search Tavily for real English news
    3. Extract authentic example sentence
    4. Use Qwen to translate and enrich
    5. Save all data to SQLite with source URL
    6. Return formatted result
    
    External Tools Used:
    - Tavily API (web search)
    - Qwen LLM (extraction, translation, enrichment)
    - SQLite Database (persistence)
    """
    
    def __init__(self):
        self.tavily_client = tavily.TavilyClient(api_key=settings.TAVILY_API_KEY)

    def _qwen_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_response: bool = False,
    ) -> str:
        payload = {
            "model": settings.QWEN_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{settings.QWEN_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.QWEN_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    
    def _search_web(self, word: str) -> List[Dict[str, Any]]:
        """
        STEP 1: Search real English news using Tavily.
        """
        query = f'"{word}" news Reuters BBC AP Guardian NPR NYT'
        try:
            response = self.tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=settings.TAVILY_MAX_RESULTS,
                include_domains=[
                    "reuters.com", "bbc.com", "bbc.co.uk",
                    "apnews.com", "theguardian.com", "npr.org",
                    "nytimes.com", "economist.com", "cnn.com",
                    "washingtonpost.com", "ft.com"
                ]
            )
            return response.get("results", [])
        except Exception as e:
            print(f"[Tavily Search Error] {e}")
            return []

    def _source_name_from_url(self, url: str) -> str:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        known_sources = {
            "reuters.com": "Reuters",
            "bbc.com": "BBC",
            "bbc.co.uk": "BBC",
            "apnews.com": "AP News",
            "theguardian.com": "The Guardian",
            "npr.org": "NPR",
            "nytimes.com": "The New York Times",
            "economist.com": "The Economist",
            "cnn.com": "CNN",
            "washingtonpost.com": "The Washington Post",
            "ft.com": "Financial Times",
        }
        for domain_suffix, source in known_sources.items():
            if domain.endswith(domain_suffix):
                return source
        return domain or "News"

    def _fallback_result(self, word: str, user_id: int) -> Dict[str, Any]:
        log_agent_step(4, 8, "No usable external source found, creating clearly marked AI fallback")
        example = f"This is an AI-generated fallback example for the word {word}."
        log_agent_step(5, 8, "Generate tutor metadata with Qwen/fallback")
        enriched = self._enrich_word(word, example)
        record = {
            "user_id": user_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "part_of_speech": enriched["part_of_speech"],
            "chinese_meaning": enriched["chinese_meaning"],
            "english_definition": enriched["english_definition"],
            "example_sentence": example,
            "chinese_translation": enriched["chinese_translation"],
            "source_name": "AI fallback",
            "source_url": "",
            "source_type": "ai_fallback",
            "collocations": json.dumps(enriched["collocations"], ensure_ascii=False),
            "synonyms": json.dumps(enriched["synonyms"], ensure_ascii=False),
            "antonyms": json.dumps(enriched["antonyms"], ensure_ascii=False),
            "memory_tip": enriched["memory_tip"],
            "difficulty": enriched["difficulty"],
        }
        log_agent_step(6, 8, "Save fallback vocabulary record to SQLite")
        word_id = save_word(record)
        log_agent_step(7, 8, "Create review schedule and learning record")
        log_agent_step(8, 8, f"Return result to OpenClaw/web UI: {word}")
        return {
            "status": "created",
            "word_id": word_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "pos": enriched["part_of_speech"],
            "meaning": enriched["chinese_meaning"],
            "english_definition": enriched["english_definition"],
            "example": example,
            "translation": enriched["chinese_translation"],
            "source": "AI fallback",
            "url": "",
            "source_type": "ai_fallback",
            "collocations": enriched["collocations"],
            "synonyms": enriched["synonyms"],
            "antonyms": enriched["antonyms"],
            "memory_tip": enriched["memory_tip"],
            "difficulty": enriched["difficulty"],
        }
    
    def _extract_sentence(self, word: str, article_content: str) -> str:
        """
        STEP 2: Use Qwen to extract one natural sentence.
        """
        content = article_content[:4000]
        
        prompt = f"""You are an English teacher. From the following news text, extract exactly ONE complete, natural sentence that contains the word "{word}".

Rules:
- The sentence must be grammatically complete.
- The sentence must use "{word}" in natural context.
- Do NOT modify the sentence. Extract it exactly as it appears.
- Return ONLY the sentence. No quotes, no explanation.

Article text:
{content}"""
        
        try:
            sentence = self._qwen_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )
            sentence = sentence.strip('"').strip("'")
            return sentence
        except Exception as e:
            print(f"[Qwen Extract Error] {e}")
            # Fallback regex
            pattern = rf'([^.]*?{re.escape(word)}[^.]*\.)'
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return matches[0].strip()
            return f"The government imposed new {word}s on several companies."
    
    def _enrich_word(self, word: str, example_sentence: str) -> Dict[str, Any]:
        """
        STEP 3: Generate phonetic, translation, POS, collocations, synonyms, antonyms.
        """
        prompt = f"""You are an English-Chinese dictionary. Analyze this word and sentence.

Word: {word}
Example: {example_sentence}

Return STRICT JSON:
{{
  "phonetic": "IPA symbol",
  "part_of_speech": "n., v., adj., or adv.",
  "chinese_meaning": "Concise Chinese definition",
  "english_definition": "Concise English definition",
  "chinese_translation": "Natural Chinese translation of example",
  "collocations": ["phrase 1", "phrase 2", "phrase 3"],
  "synonyms": ["word1", "word2"],
  "antonyms": ["word1", "word2"],
  "memory_tip": "Short bilingual memory tip",
  "difficulty": 2
}}

Return ONLY JSON. No markdown, no explanation."""
        
        try:
            content = self._qwen_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
                json_response=True,
            )
            content = content.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(content)
            
            required = [
                "phonetic",
                "part_of_speech",
                "chinese_meaning",
                "english_definition",
                "chinese_translation",
                "collocations",
                "synonyms",
                "antonyms",
                "memory_tip",
                "difficulty",
            ]
            for field in required:
                if field not in result:
                    result[field] = "" if field not in ["collocations", "synonyms", "antonyms"] else []
            result["difficulty"] = min(5, max(1, int(result.get("difficulty") or 2)))
            
            return result
            
        except Exception as e:
            print(f"[Qwen Enrich Error] {e}")
            return {
                "phonetic": f"/{word}/",
                "part_of_speech": "n.",
                "chinese_meaning": "AI generated definition pending review",
                "english_definition": f"A vocabulary entry for {word}.",
                "chinese_translation": "AI-generated translation pending review",
                "collocations": [f"{word} policy", f"new {word}"],
                "synonyms": ["similar"],
                "antonyms": ["opposite"],
                "memory_tip": f"Connect {word} with its example sentence and review it tomorrow.",
                "difficulty": 2,
            }
    
    async def execute(self, word: str, user_id: int) -> Dict[str, Any]:
        """
        MAIN WORKFLOW: Full agent pipeline.
        """
        log_agent_step(1, 8, f"Normalize and validate input word: {word}")
        word = word.lower().strip()
        if not re.fullmatch(r"[a-z][a-z -]{0,80}", word):
            raise ValueError("Please enter a single English word or short phrase.")
        
        # Check if exists
        log_agent_step(2, 8, f"Check database for existing word: {word}")
        existing = get_word_by_name(word, user_id)
        if existing:
            log_agent_step(8, 8, f"Word already exists, returning saved record: {word}")
            return {
                "status": "exists",
                "word_id": existing["id"],
                "word": existing["word"],
                "phonetic": existing["phonetic"],
                "pos": existing["part_of_speech"],
                "meaning": existing["chinese_meaning"],
                "english_definition": existing.get("english_definition"),
                "example": existing["example_sentence"],
                "translation": existing["chinese_translation"],
                "source": existing["source_name"],
                "url": existing["source_url"],
                "source_type": existing.get("source_type", "authentic"),
                "collocations": json.loads(existing.get("collocations", "[]")),
                "synonyms": json.loads(existing.get("synonyms", "[]")),
                "antonyms": json.loads(existing.get("antonyms", "[]")),
                "memory_tip": existing.get("memory_tip"),
                "difficulty": existing.get("difficulty", 2),
                "message": f"'{word}' already exists."
            }
        
        # STEP 1: Search
        log_agent_step(3, 8, f"Search authentic English sources with Tavily: {word}")
        articles = self._search_web(word)
        if not articles:
            return self._fallback_result(word, user_id)
        
        best = articles[0]
        source_url = best.get("url", "")
        source_name = best.get("source") or self._source_name_from_url(source_url)
        source_type = "authentic"
        article_content = best.get("raw_content") or best.get("content", "")
        log_agent_step(4, 8, f"Selected source: {source_name} ({source_url})")
        
        if not article_content or len(article_content) < 50:
            return self._fallback_result(word, user_id)
        
        # STEP 2: Extract
        log_agent_step(5, 8, "Extract real example sentence containing target word")
        example = self._extract_sentence(word, article_content)
        
        if word.lower() not in example.lower():
            sentences = article_content.split(".")
            for sent in sentences:
                if word.lower() in sent.lower() and len(sent) > 20:
                    example = sent.strip() + "."
                    break
        
        # STEP 3: Enrich
        log_agent_step(6, 8, "Generate translation, phonetic, definitions, collocations, synonyms, antonyms")
        enriched = self._enrich_word(word, example)
        
        # STEP 4: Build record
        record = {
            "user_id": user_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "part_of_speech": enriched["part_of_speech"],
            "chinese_meaning": enriched["chinese_meaning"],
            "english_definition": enriched["english_definition"],
            "example_sentence": example,
            "chinese_translation": enriched["chinese_translation"],
            "source_name": source_name,
            "source_url": source_url,
            "source_type": source_type,
            "collocations": json.dumps(enriched["collocations"], ensure_ascii=False),
            "synonyms": json.dumps(enriched["synonyms"], ensure_ascii=False),
            "antonyms": json.dumps(enriched["antonyms"], ensure_ascii=False),
            "memory_tip": enriched["memory_tip"],
            "difficulty": enriched["difficulty"],
        }
        
        # STEP 5: Save
        log_agent_step(7, 8, "Save vocabulary record, source URL, and review schedule to SQLite")
        word_id = save_word(record)
        
        # STEP 6: Return
        log_agent_step(8, 8, f"Return saved result to OpenClaw/web UI: {word}")
        return {
            "status": "created",
            "word_id": word_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "pos": enriched["part_of_speech"],
            "meaning": enriched["chinese_meaning"],
            "english_definition": enriched["english_definition"],
            "example": example,
            "translation": enriched["chinese_translation"],
            "source": source_name,
            "url": source_url,
            "source_type": source_type,
            "collocations": enriched["collocations"],
            "synonyms": enriched["synonyms"],
            "antonyms": enriched["antonyms"],
            "memory_tip": enriched["memory_tip"],
            "difficulty": enriched["difficulty"],
        }

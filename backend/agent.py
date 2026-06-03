import json
import re
from typing import Dict, Any, List
import tavily
from openai import OpenAI
from .config import settings
from .database import save_word, get_word_by_name

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
        self.qwen_client = OpenAI(
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL
        )
    
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
            response = self.qwen_client.chat.completions.create(
                model=settings.QWEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200
            )
            sentence = response.choices[0].message.content.strip()
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
  "chinese_translation": "Natural Chinese translation of example",
  "collocations": ["phrase 1", "phrase 2", "phrase 3"],
  "synonyms": ["word1", "word2"],
  "antonyms": ["word1", "word2"]
}}

Return ONLY JSON. No markdown, no explanation."""
        
        try:
            response = self.qwen_client.chat.completions.create(
                model=settings.QWEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content.strip()
            content = content.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(content)
            
            required = ["phonetic", "part_of_speech", "chinese_meaning", 
                       "chinese_translation", "collocations", "synonyms", "antonyms"]
            for field in required:
                if field not in result:
                    result[field] = "" if field not in ["collocations", "synonyms", "antonyms"] else []
            
            return result
            
        except Exception as e:
            print(f"[Qwen Enrich Error] {e}")
            return {
                "phonetic": f"/{word}/",
                "part_of_speech": "n.",
                "chinese_meaning": "待补充",
                "chinese_translation": "待补充",
                "collocations": [f"{word} policy", f"new {word}"],
                "synonyms": ["similar"],
                "antonyms": ["opposite"]
            }
    
    async def execute(self, word: str, user_id: int) -> Dict[str, Any]:
        """
        MAIN WORKFLOW: Full agent pipeline.
        """
        word = word.lower().strip()
        
        # Check if exists
        existing = get_word_by_name(word, user_id)
        if existing:
            return {
                "status": "exists",
                "word_id": existing["id"],
                "word": existing["word"],
                "phonetic": existing["phonetic"],
                "pos": existing["part_of_speech"],
                "meaning": existing["chinese_meaning"],
                "example": existing["example_sentence"],
                "translation": existing["chinese_translation"],
                "source": existing["source_name"],
                "url": existing["source_url"],
                "collocations": json.loads(existing.get("collocations", "[]")),
                "message": f"'{word}' already exists."
            }
        
        # STEP 1: Search
        articles = self._search_web(word)
        if not articles:
            raise ValueError(f"No sources found for '{word}'.")
        
        best = articles[0]
        source_url = best.get("url", "")
        source_name = best.get("source", "News")
        article_content = best.get("content", "")
        
        if not article_content or len(article_content) < 50:
            raise ValueError(f"Article too short for '{word}'.")
        
        # STEP 2: Extract
        example = self._extract_sentence(word, article_content)
        
        if word.lower() not in example.lower():
            sentences = article_content.split(".")
            for sent in sentences:
                if word.lower() in sent.lower() and len(sent) > 20:
                    example = sent.strip() + "."
                    break
        
        # STEP 3: Enrich
        enriched = self._enrich_word(word, example)
        
        # STEP 4: Build record
        record = {
            "user_id": user_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "part_of_speech": enriched["part_of_speech"],
            "chinese_meaning": enriched["chinese_meaning"],
            "example_sentence": example,
            "chinese_translation": enriched["chinese_translation"],
            "source_name": source_name,
            "source_url": source_url,
            "collocations": json.dumps(enriched["collocations"], ensure_ascii=False),
            "synonyms": json.dumps(enriched["synonyms"], ensure_ascii=False),
            "antonyms": json.dumps(enriched["antonyms"], ensure_ascii=False)
        }
        
        # STEP 5: Save
        word_id = save_word(record)
        
        # STEP 6: Return
        return {
            "status": "created",
            "word_id": word_id,
            "word": word,
            "phonetic": enriched["phonetic"],
            "pos": enriched["part_of_speech"],
            "meaning": enriched["chinese_meaning"],
            "example": example,
            "translation": enriched["chinese_translation"],
            "source": source_name,
            "url": source_url,
            "collocations": enriched["collocations"],
            "synonyms": enriched["synonyms"],
            "antonyms": enriched["antonyms"]
        }
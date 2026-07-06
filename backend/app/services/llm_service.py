import json
import logging
import re
import time
from typing import Any, Dict, Tuple
import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are an AI feedback analysis engine. Analyze the following user feedback item.

[Metadata]
Source Type: {source_type}
Platform: {platform}
Rating/Score: {rating_or_score}

[Keyword Indicators (Heuristics)]
{keyword_indicators}

Note: The keyword indicators above are assistive heuristics only. You must perform full contextual semantic analysis of the Raw Feedback Text to make the final determination.

[Feedback Text]
\"\"\"{text}\"\"\"

[Classification Rules for primary_theme]
- Music Discovery: Finding new music, exploring new songs, finding hidden gems, discovering fresh music.
- Recommendations: Algorithmic suggestions, personalized recommendations, automated mix feeds, AI DJ, AI recommendation features.
- Playlists: Creating, editing, or listening to playlists, including Daily Mix, Discover Weekly, Release Radar, Blend, Liked Songs, or user-curated playlists.
- Shuffle Experience: Playing music in shuffle mode, smart shuffle mode, randomizing music, or complaints about shuffle behavior.
- Radio: Artist radio, song radio, stations, autoplay radio, or queueing stations.
- Search & Browse: Searching for tracks, artists, albums, browsing genres/categories, home page recommendations navigation.
- Library Management: Saving songs, managing liked songs, library organization, queue management, adding/removing library items.
- Social Discovery: Friend activity feed, sharing playlists, Blend (collaborative playlists), following friends/artists.
- Podcast vs Music: Podcast recommendations appearing in music feeds, complaints about podcast overlap with music, podcast-specific features.
- Premium vs Free Experience: Premium subscription details, ads in free tier, offline playback restrictions on free tier, billing, or subscription value.
- Unidentified: Use this fallback category only when the review does not fit any other category confidently.

[Classification Rules for secondary_tags (Include as applicable)]
- Artist Discovery: Discovering new, similar, unknown, or emerging artists.
- Genre Exploration: Exploring different musical genres, variety, diverse music styles, expanding tastes.
- Mood-Based Listening: Listening based on mood (happy, sad, chill, relax, energetic, emotional).
- Activity-Based Listening: Listening while doing activities (workout, gym, running, study, work, commute, driving, sleep).
- Personalization: Feedback on how well recommendations fit the user's specific taste, listening habits, or tailored personalization.
- Recommendation Accuracy: Mismatch of recommendations, irrelevant songs, wrong songs suggested, mismatch of taste profile.
- Content Variety: General variety or diversity of music, complaints about same/repetitive artists or songs in recommendations, mix variety.
- Listening Habits: Daily listening behavior, favorite songs, replay frequency, repeat listening patterns.
- New Releases: Listening to newly released music, tracks, albums, or Release Radar.
- Feature Requests: User wishes, suggestions, ideas, missing options, feature suggestions.
- Recommendation Trust: General trust or lack thereof in recommendations, stopped using recommendations, feature doesn't work as expected, got worse.
- Discovery Features: Release Radar, Discover Weekly, AI DJ, Smart Shuffle, Daily Mix.
- Repetitive Listening: Loop, repeat listening, same playlist, keeps playing same songs/artists over and over.

[Classification Rules for sentiment]
- positive: Explicit praise, satisfaction, delight, or positive feedback.
- negative: Explicit frustration, disappointment, anger, complaint, or negative issues.
- neutral: Factual or low-emotion review that is balanced or emotionally flat.
- unclear: Vague, contradictory, nonsense, too short, or sentiment cannot be confidently determined.
- Mixed-Sentiment Rule: If a review has mixed sentiment (contains both praise/satisfaction and criticism/issues), set "has_mixed_sentiment" to true, and assign the dominant sentiment (positive or negative) to "sentiment". Do NOT collapse mixed reviews into neutral or unclear. Standardize the praise and criticism aspects into standard aspect categories in the "sentiment_profile".

[Classification Rules for sentiment_profile (Aspect Label Normalization)]
For the positive and negative aspects in the review, you must ONLY use values from this fixed list of standardized categories:
- music_discovery (finding new songs/artists, fresh recommendations)
- recommendation_accuracy (algorithmic precision, suitability of suggestions)
- playlist_experience (playlist curation, daily mix, release radar, blend)
- shuffle_experience (randomized play, smart shuffle)
- search_browse (find bar, browse menu, filters)
- library_management (liked songs, queueing, saving, organization)
- premium_ads (subscription price, premium features, ads in free tier)
- app_performance (speed, bugs, crashes, lag, offline playback)
- audio_quality (sound quality, volume level)
- other (any aspect that doesn't fit the above categories)

Provide your analysis in raw JSON format matching this schema:
{{
  "primary_theme": "one of: Music Discovery, Recommendations, Playlists, Shuffle Experience, Radio, Search & Browse, Library Management, Social Discovery, Podcast vs Music, Premium vs Free Experience, Unidentified",
  "secondary_tags": ["list of matching secondary tags from: Artist Discovery, Genre Exploration, Mood-Based Listening, Activity-Based Listening, Personalization, Recommendation Accuracy, Content Variety, Listening Habits, New Releases, Feature Requests, Recommendation Trust, Discovery Features, Repetitive Listening"],
  "sentiment": "one of: positive, negative, neutral, unclear",
  "has_mixed_sentiment": true,
  "sentiment_profile": {{
    "positive_aspects": ["list of standardized aspect categories containing only: music_discovery, recommendation_accuracy, playlist_experience, shuffle_experience, search_browse, library_management, premium_ads, app_performance, audio_quality, other"],
    "negative_aspects": ["list of standardized aspect categories containing only: music_discovery, recommendation_accuracy, playlist_experience, shuffle_experience, search_browse, library_management, premium_ads, app_performance, audio_quality, other"]
  }},
  "topics": ["list", "of", "specific", "topics"],
  "unmet_needs": ["unmet", "feature", "requests", "or", "pain_points"],
  "user_segment": "one of: premium_subscriber, free_tier, artist, podcast_listener, unknown",
  "listening_intent": "one of: music_discovery, background_listening, commute, workout, unknown",
  "loop_cause": "brief explanation of what triggered the user to write this",
  "listening_job": "user's high-level listening goal/job, e.g., finding new music for a party, background focus, workout energy",
  "desired_outcome": "what the user wants to achieve, e.g., discovery of new artists, seamless casting, no repetitive tracks",
  "blocked_goal": "what blocks the user from their goal, e.g., recommendation repeats same songs, search fails to find track",
  "root_cause": "product/technical cause, e.g., recommendation algorithm repeats tracks, UI redesign hid playlists",
  "user_segment_signals": ["list", "of", "signals", "e.g.", "premium_subscriber", "heavy_user", "carplay_user"],
  "recommendation_pain_type": "one of: repetitive_recommendations, stale_recommendations, wrong_taste_alignment, missing_customization, none",
  "evidence_quote": "primary exact quote from raw text backing up the core complaint/need",
  "confidence": 0.95,
  "evidence": [
    {{
      "quote": "exact direct quote from the text supporting a topic or category",
      "topic": "corresponding topic from topics list"
    }}
  ]
}}

Enforce valid JSON. Return ONLY the JSON object and nothing else."""


class RateLimitException(Exception):
    def __init__(self, message: str, retry_after: float, provider: str):
        super().__init__(message)
        self.retry_after = retry_after
        self.provider = provider


class LLMException(Exception):
    pass


class InvalidAPIKeyException(LLMException):
    pass


class QuotaExhaustedException(LLMException):
    pass


class ModelNotFoundException(LLMException):
    pass


def get_sentiment_emotion_indicators(text: str) -> dict:
    text_lower = text.lower()
    
    positive_keywords = [
        "love", "like", "amazing", "awesome", "excellent", "fantastic", "great",
        "perfect", "best", "wonderful", "brilliant", "impressive", "helpful",
        "easy", "smooth", "fast", "accurate", "personalized", "refreshing",
        "enjoy", "enjoying", "favorite", "happy", "satisfied", "recommend",
        "worth it", "works well", "finally", "thank you", "improved", "pleasant",
        "reliable", "useful", "cool", "nice"
    ]
    
    neutral_keywords = [
        "okay", "ok", "fine", "average", "decent", "acceptable", "normal",
        "standard", "basic", "fair", "sometimes", "occasionally", "usually",
        "generally", "mostly", "noticed", "observed", "using", "trying",
        "updated", "changed", "feature", "option", "available", "works",
        "can", "could", "would"
    ]
    
    negative_keywords = [
        "hate", "disappointed", "disappointing", "annoying", "frustrating",
        "frustrated", "terrible", "awful", "bad", "poor", "worst", "broken",
        "bug", "issue", "problem", "error", "crash", "fails", "stuck", "boring",
        "repetitive", "repeat", "same songs", "same artists", "useless",
        "irrelevant", "inaccurate", "confusing", "slow", "lag", "missing",
        "can't", "cannot", "never", "waste", "refund", "regret"
    ]
    
    strong_negative_keywords = [
        "uninstall", "cancel", "cancelled", "unsubscribe", "switching",
        "moving to", "leaving", "fed up", "ridiculous", "pathetic", "garbage",
        "trash", "useless", "scam", "hate this app", "never again", "wasted money"
    ]
    
    emotion_keywords_map = {
        "Joy": ["love", "amazing", "awesome", "happy", "enjoyable", "favorite"],
        "Satisfaction": ["good", "works well", "helpful", "personalized", "smooth"],
        "Frustration": ["annoying", "frustrating", "repetitive", "same songs", "poor"],
        "Disappointment": ["expected better", "disappointing", "used to be better"],
        "Confusion": ["confusing", "don't understand", "difficult", "unclear"],
        "Anger": ["hate", "worst", "garbage", "pathetic", "useless"],
        "Excitement": ["discovered", "wow", "impressed", "fantastic"],
        "Trust": ["reliable", "accurate", "consistent"],
        "Boredom": ["boring", "repetitive", "stale", "predictable"]
    }
    
    def count_hits(keywords):
        hits = []
        for kw in keywords:
            if kw.isalnum():
                pattern = r'\b' + re.escape(kw) + r'\b'
                matches = re.findall(pattern, text_lower)
                if matches:
                    hits.extend([kw] * len(matches))
            else:
                count = text_lower.count(kw)
                if count > 0:
                    hits.extend([kw] * count)
        return hits

    pos_hits = count_hits(positive_keywords)
    neu_hits = count_hits(neutral_keywords)
    neg_hits = count_hits(negative_keywords)
    strong_neg_hits = count_hits(strong_negative_keywords)
    
    detected_emotions = {}
    for emotion, keywords in emotion_keywords_map.items():
        hits = count_hits(keywords)
        if hits:
            detected_emotions[emotion] = list(set(hits))
            
    return {
        "positive": pos_hits,
        "neutral": neu_hits,
        "negative": neg_hits,
        "strong_negative": strong_neg_hits,
        "detected_emotions": detected_emotions
    }


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gemini_models = settings.gemini_model_list
        self.primary_provider = "gemini"
        self.primary_model = self.gemini_models[0] if self.gemini_models else "gemini-2.5-flash"
        self.fallback_provider = "groq"
        self.fallback_model = "llama-3.3-70b-versatile"

    def generate_text(self, prompt: str, response_mime_type: str = "text/plain") -> Tuple[str, str, str, bool]:
        """
        Generates text using the Gemini model ladder, falling back to Groq if all fail.
        """
        # Try Gemini models sequentially
        for idx, model in enumerate(self.gemini_models):
            url_masked = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                logger.info(
                    f"LLM Attempt: Provider=gemini, Model={model}, Endpoint={url_masked}, FallbackTriggered={idx > 0}"
                )
                result = self._call_provider("gemini", model, prompt, response_mime_type=response_mime_type)
                logger.info(f"LLM Success: Provider=gemini, Model={model} succeeded.")
                return result, "gemini", model, idx > 0
            except InvalidAPIKeyException as exc:
                logger.error(
                    f"LLM Attempt Failed (Non-fallback): Provider=gemini, Model={model}, Status=401, Label=invalid_key, Error={exc}"
                )
                raise
            except QuotaExhaustedException as exc:
                logger.warning(
                    f"LLM Attempt Failed (Fallback eligible): Provider=gemini, Model={model}, Status=429, Label=quota_exhausted, Error={exc}"
                )
                if idx < len(self.gemini_models) - 1:
                    logger.info(f"Transition: Moving from Gemini model {model} to {self.gemini_models[idx+1]}")
                else:
                    logger.info("Transition: All Gemini models exhausted. Falling back to Groq...")
            except ModelNotFoundException as exc:
                logger.warning(
                    f"LLM Attempt Failed (Fallback eligible): Provider=gemini, Model={model}, Status=404, Label=model_not_found, Error={exc}"
                )
                if idx < len(self.gemini_models) - 1:
                    logger.info(f"Transition: Moving from Gemini model {model} to {self.gemini_models[idx+1]}")
                else:
                    logger.info("Transition: All Gemini models exhausted. Falling back to Groq...")
            except LLMException as exc:
                logger.error(
                    f"LLM Attempt Failed (Non-fallback): Provider=gemini, Model={model}, Status=400, Label=malformed_request, Error={exc}"
                )
                raise
            except Exception as exc:
                logger.warning(
                    f"LLM Attempt Failed (Fallback eligible): Provider=gemini, Model={model}, Status=Error, Label=timeout_or_network, Error={exc}"
                )
                if idx < len(self.gemini_models) - 1:
                    logger.info(f"Transition: Moving from Gemini model {model} to {self.gemini_models[idx+1]}")
                else:
                    logger.info("Transition: All Gemini models exhausted. Falling back to Groq...")

        # Try Groq fallback
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        try:
            logger.info(
                f"LLM Attempt: Provider=groq, Model={self.fallback_model}, Endpoint={groq_url}, FallbackTriggered=True"
            )
            result = self._call_provider("groq", self.fallback_model, prompt, response_mime_type=response_mime_type)
            logger.info("LLM Success: Fallback triggered successfully to Groq.")
            return result, "groq", self.fallback_model, True
        except (InvalidAPIKeyException, QuotaExhaustedException, ModelNotFoundException) as exc:
            status_code = "401" if isinstance(exc, InvalidAPIKeyException) else ("429" if isinstance(exc, QuotaExhaustedException) else "404")
            label = "invalid_api_key" if isinstance(exc, InvalidAPIKeyException) else ("quota_exhausted_or_rate_limit" if isinstance(exc, QuotaExhaustedException) else "wrong_model_or_endpoint")
            logger.error(
                f"LLM Fallback Failed: Provider=groq, Model={self.fallback_model}, Status={status_code}, Label={label}, Error={exc}"
            )
            raise
        except Exception as exc:
            logger.error(
                f"LLM Fallback Failed: Provider=groq, Model={self.fallback_model}, Status=Error, Label=network_or_unknown, Error={exc}"
            )
            raise RuntimeError(f"All LLM providers failed: {exc}") from exc

    def analyze_feedback(self, text: str, source_metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, bool]:
        """
        Analyzes a single feedback item using Gemini model ladder, with automatic fallback to Groq.
        """
        indicators = get_sentiment_emotion_indicators(text)
        
        indicators_str = (
            f"Positive hits: {', '.join(indicators['positive']) if indicators['positive'] else 'None'}\n"
            f"Neutral hits: {', '.join(indicators['neutral']) if indicators['neutral'] else 'None'}\n"
            f"Negative hits: {', '.join(indicators['negative']) if indicators['negative'] else 'None'}\n"
            f"Strong Negative hits: {', '.join(indicators['strong_negative']) if indicators['strong_negative'] else 'None'}\n"
            f"Detected Emotions: {', '.join(f'{k}({v})' for k, v in indicators['detected_emotions'].items()) if indicators['detected_emotions'] else 'None'}"
        )

        prompt = PROMPT_TEMPLATE.format(
            text=text,
            source_type=source_metadata.get("source_type", "unknown"),
            platform=source_metadata.get("platform", "unknown"),
            rating_or_score=source_metadata.get("rating_or_score", "None"),
            keyword_indicators=indicators_str
        )
        result_text, provider_used, model_used, was_fallback = self.generate_text(prompt, response_mime_type="application/json")
        parsed = self._clean_and_parse_json(result_text)

        # Normalize sentiment for database consistency
        sentiment = parsed.get("sentiment")
        if sentiment:
            s_lower = sentiment.lower().strip()
            if s_lower in ("positive", "user satisfaction"):
                parsed["sentiment"] = "positive"
            elif s_lower in ("negative", "user frustration"):
                parsed["sentiment"] = "negative"
            elif s_lower in ("neutral",):
                parsed["sentiment"] = "neutral"
            elif s_lower in ("unclear", "unknown"):
                parsed["sentiment"] = "unclear"
        else:
            parsed["sentiment"] = "unclear"

        # Aspect categories fixed allowed set
        allowed_aspects = {
            "music_discovery", "recommendation_accuracy", "playlist_experience",
            "shuffle_experience", "search_browse", "library_management",
            "premium_ads", "app_performance", "audio_quality", "other"
        }

        def normalize_aspect_list(aspects: Any) -> list:
            if not isinstance(aspects, list):
                return []
            normalized = []
            for asp in aspects:
                asp_str = str(asp).lower().strip().replace(" ", "_")
                if asp_str in allowed_aspects:
                    normalized.append(asp_str)
                else:
                    mapped = "other"
                    if any(k in asp_str for k in ("discover", "find_new", "artist", "song")):
                        mapped = "music_discovery"
                    elif any(k in asp_str for k in ("recommend", "accuracy", "suggest", "taste", "fit")):
                        mapped = "recommendation_accuracy"
                    elif any(k in asp_str for k in ("playlist", "radar", "mix", "blend", "daily")):
                        mapped = "playlist_experience"
                    elif any(k in asp_str for k in ("shuffle", "random")):
                        mapped = "shuffle_experience"
                    elif any(k in asp_str for k in ("search", "browse", "genre", "category")):
                        mapped = "search_browse"
                    elif any(k in asp_str for k in ("library", "save", "queue", "liked")):
                        mapped = "library_management"
                    elif any(k in asp_str for k in ("premium", "ad", "price", "sub", "billing")):
                        mapped = "premium_ads"
                    elif any(k in asp_str for k in ("performance", "speed", "bug", "crash", "lag", "offline")):
                        mapped = "app_performance"
                    elif any(k in asp_str for k in ("audio", "sound", "volume")):
                        mapped = "audio_quality"
                    normalized.append(mapped)
            return list(set(normalized))

        # Normalize has_mixed_sentiment
        has_mixed = parsed.get("has_mixed_sentiment")
        profile = parsed.get("sentiment_profile") or {}
        pos_asps = normalize_aspect_list(profile.get("positive_aspects") or [])
        neg_asps = normalize_aspect_list(profile.get("negative_aspects") or [])

        if has_mixed is None:
            has_mixed = bool(pos_asps and neg_asps)
        else:
            has_mixed = bool(has_mixed)

        if has_mixed:
            if not pos_asps:
                pos_asps = ["other"]
            if not neg_asps:
                neg_asps = ["other"]

        parsed["has_mixed_sentiment"] = has_mixed
        parsed["sentiment_profile"] = {
            "positive_aspects": pos_asps,
            "negative_aspects": neg_asps
        }

        return parsed, provider_used, model_used, was_fallback

    def _call_provider_with_retry(self, provider: str, model: str, prompt: str, max_retries: int = 3) -> str:
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return self._call_provider(provider, model, prompt)
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed for {provider}: {exc}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2.0
        raise RuntimeError("Retries exhausted")

    def _post_with_rate_limit_check(self, provider: str, url: str, payload: dict, headers: dict, timeout: float) -> httpx.Response:
        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            retry_after_val = 10.0  # default fallback
            if retry_after:
                try:
                    retry_after_val = float(retry_after)
                except ValueError:
                    pass
            else:
                # check x-ratelimit-reset-requests or similar rate limit reset headers
                reset_req = resp.headers.get("x-ratelimit-reset-requests")
                if reset_req:
                    try:
                        match = re.search(r"(\d+(\.\d+)?)s?", reset_req)
                        if match:
                            retry_after_val = float(match.group(1))
                    except Exception:
                        pass
            raise RateLimitException(f"{provider} rate limit exceeded", retry_after=retry_after_val, provider=provider)
        resp.raise_for_status()
        return resp

    def _call_provider(self, provider: str, model: str, prompt: str, response_mime_type: str = "text/plain") -> str:
        headers = {"Content-Type": "application/json"}
        timeout = 15.0

        if provider == "gemini":
            key = self.settings.gemini_api_key
            if not key:
                raise InvalidAPIKeyException("GEMINI_API_KEY is not configured")
            # Using currently supported v1beta endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": response_mime_type}
            }
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 400:
                    err_body = resp.text
                    if "API key not valid" in err_body or "API_KEY_INVALID" in err_body:
                        raise InvalidAPIKeyException("Gemini API key is invalid")
                    elif "Unknown name" in err_body or "INVALID_ARGUMENT" in err_body:
                        raise LLMException(f"Gemini malformed request: {err_body}")
                elif resp.status_code == 404:
                    raise ModelNotFoundException(f"Gemini model or endpoint not found: {resp.text}")
                elif resp.status_code == 429:
                    raise QuotaExhaustedException("Gemini provider quota exhausted / rate limit exceeded")
                
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                raise LLMException(f"Gemini API error: {e}")

        elif provider == "groq":
            key = self.settings.groq_api_key
            if not key:
                raise InvalidAPIKeyException("GROQ_API_KEY is not configured")
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {key}"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"} if response_mime_type == "application/json" else None
            }
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
                if resp.status_code == 401:
                    raise InvalidAPIKeyException("Groq API key is invalid (Unauthorized)")
                elif resp.status_code == 404:
                    raise ModelNotFoundException(f"Groq model or endpoint not found: {resp.text}")
                elif resp.status_code == 429:
                    raise QuotaExhaustedException("Groq provider quota exhausted / rate limit exceeded")
                
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                raise LLMException(f"Groq API error: {e}")

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """Cleans LLM response and parses it into a dictionary."""
        cleaned = text.strip()
        # Remove markdown wrapper if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Try to find json brackets if it failed
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Failed to parse cleaned JSON block: {exc}") from exc
            raise ValueError("No JSON block found in LLM response text")

    def check_health(self) -> Dict[str, Any]:
        """
        Runs lightweight connectivity health checks for the Gemini ladder and Groq.
        """
        status = {}
        
        # 1. Fetch models.list from Gemini if key is present
        gemini_api_models = None
        gemini_list_error = None
        if self.settings.gemini_api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.settings.gemini_api_key}"
                resp = httpx.get(url, timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    gemini_api_models = {
                        m["name"].replace("models/", ""): m for m in data.get("models", [])
                    }
                else:
                    gemini_list_error = f"HTTP {resp.status_code}"
            except Exception as e:
                gemini_list_error = str(e)

        # 2. Check each Gemini model in the ladder
        gemini_ladder_status = []
        allowlist = ["gemini-2.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash"]
        
        for idx, model in enumerate(self.gemini_models):
            model_info = {
                "model": model,
                "endpoint": f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                "status": "untested",
                "label": "untested"
            }
            
            is_valid_text_model = model in allowlist
            
            if gemini_api_models is not None:
                if model in gemini_api_models:
                    m_data = gemini_api_models[model]
                    methods = m_data.get("supportedGenerationMethods", [])
                    is_disallowed = any(kw in model.lower() for kw in ["tts", "embedding", "live", "robotics", "translate"])
                    if "generateContent" in methods and not is_disallowed:
                        model_info["label"] = "validated_via_api"
                    else:
                        model_info["label"] = "unsupported_generation_method"
                else:
                    model_info["label"] = "model_not_in_api_list"
            else:
                if is_valid_text_model:
                    model_info["label"] = "validated_via_allowlist"
                else:
                    model_info["label"] = "invalid_model_type"
            
            # Active ping for primary model (index 0) only
            if idx == 0 and self.settings.gemini_api_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.settings.gemini_api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": "ping"}]}],
                        "generationConfig": {"responseMimeType": "text/plain"}
                    }
                    resp = httpx.post(url, json=payload, timeout=3.0)
                    model_info["status"] = str(resp.status_code)
                    if resp.status_code == 200:
                        model_info["label"] = "ok"
                    elif resp.status_code == 400:
                        err_body = resp.text
                        if "API key not valid" in err_body or "API_KEY_INVALID" in err_body:
                            model_info["label"] = "invalid_api_key"
                        else:
                            model_info["label"] = "malformed_request"
                    elif resp.status_code == 404:
                        model_info["label"] = "wrong_model_or_endpoint"
                    elif resp.status_code == 429:
                        model_info["label"] = "quota_exhausted_or_rate_limit"
                    else:
                        model_info["label"] = f"unexpected_status_{resp.status_code}"
                except Exception as e:
                    model_info["status"] = "exception"
                    model_info["label"] = f"exception_{str(e)}"
            
            gemini_ladder_status.append(model_info)
            
        status["gemini_ladder"] = gemini_ladder_status
        if gemini_list_error:
            status["gemini_list_error"] = gemini_list_error

        # 3. Groq health check
        groq_info = {
            "provider": "groq",
            "model": self.fallback_model,
            "endpoint": "https://api.groq.com/openai/v1/chat/completions",
            "status": "N/A",
            "label": "missing_api_key"
        }
        if self.settings.groq_api_key:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.settings.groq_api_key}"
                }
                payload = {
                    "model": self.fallback_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }
                resp = httpx.post(url, json=payload, headers=headers, timeout=3.0)
                groq_info["status"] = str(resp.status_code)
                if resp.status_code == 200:
                    groq_info["label"] = "ok"
                elif resp.status_code == 401:
                    groq_info["label"] = "invalid_api_key"
                elif resp.status_code == 404:
                    groq_info["label"] = "wrong_model_or_endpoint"
                elif resp.status_code == 429:
                    groq_info["label"] = "quota_exhausted_or_rate_limit"
                else:
                    groq_info["label"] = f"unexpected_status_{resp.status_code}"
            except Exception as e:
                groq_info["status"] = "exception"
                groq_info["label"] = f"exception_{str(e)}"
        status["groq"] = groq_info

        # 4. Gemini Embedding health check
        embedding_info = {
            "provider": "gemini",
            "model": self.settings.gemini_embedding_model,
            "endpoint": f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_embedding_model}:embedContent",
            "status": "untested",
            "label": "untested"
        }
        if not self.settings.gemini_api_key:
            embedding_info["label"] = "missing_api_key"
        elif not self.settings.embedding_enabled:
            embedding_info["label"] = "disabled"
        else:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.gemini_embedding_model}:embedContent?key={self.settings.gemini_api_key}"
                payload = {
                    "model": f"models/{self.settings.gemini_embedding_model}",
                    "content": {"parts": [{"text": "ping"}]},
                    "taskType": "RETRIEVAL_DOCUMENT"
                }
                resp = httpx.post(url, json=payload, timeout=3.0)
                embedding_info["status"] = str(resp.status_code)
                if resp.status_code == 200:
                    embedding_info["label"] = "ok"
                elif resp.status_code == 400:
                    err_body = resp.text
                    if "API key not valid" in err_body or "API_KEY_INVALID" in err_body:
                        embedding_info["label"] = "invalid_api_key"
                    else:
                        embedding_info["label"] = "malformed_request"
                elif resp.status_code == 404:
                    embedding_info["label"] = "wrong_model_or_endpoint"
                elif resp.status_code == 429:
                    embedding_info["label"] = "quota_exhausted_or_rate_limit"
                else:
                    embedding_info["label"] = f"unexpected_status_{resp.status_code}"
            except Exception as e:
                embedding_info["status"] = "exception"
                embedding_info["label"] = f"exception_{str(e)}"
        status["embedding"] = embedding_info

        return status

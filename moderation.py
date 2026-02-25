"""
AI Moderation Engine for Gaav Asara News
─────────────────────────────────────────
Provides text similarity detection, AI-generated text probability,
keyword risk scanning, and user behavior scoring.
"""

import re
import math
import json
import numpy as np
from collections import Counter
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ModerationEngine:
    """Core AI moderation engine for news content analysis."""

    def __init__(self, app_config):
        self.config = app_config
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self._is_fitted = False

    def analyze(self, title, content, description, user, existing_news_texts=None):
        """
        Run full moderation analysis on submitted news.
        Returns dict with all scores and final decision.
        """
        full_text = f"{title} {description} {content}"

        # 1. Similarity score against existing news
        similarity = self._check_similarity(full_text, existing_news_texts or [])

        # 2. AI-generated text probability
        ai_prob = self._detect_ai_generated(full_text)

        # 3. Keyword risk score
        keyword_risk = self._check_keywords(full_text)

        # 4. User behavior score
        behavior_risk = self._user_behavior_score(user)

        # 5. Calculate final weighted risk score
        weights = {
            'similarity': self.config.get('SIMILARITY_WEIGHT', 0.30),
            'ai_detection': self.config.get('AI_DETECTION_WEIGHT', 0.25),
            'keyword': self.config.get('KEYWORD_WEIGHT', 0.25),
            'behavior': self.config.get('USER_BEHAVIOR_WEIGHT', 0.20),
        }

        final_risk = (
            similarity * weights['similarity'] +
            ai_prob * weights['ai_detection'] +
            keyword_risk * weights['keyword'] +
            behavior_risk * weights['behavior']
        )

        final_risk = min(100, max(0, final_risk))

        # 6. Decision
        decision = self._make_decision(final_risk, user)

        # 7. Generate content embedding for future comparisons
        embedding = self._generate_embedding(full_text)

        return {
            'ai_score': round(ai_prob, 2),
            'similarity_score': round(similarity, 2),
            'keyword_score': round(keyword_risk, 2),
            'behavior_score': round(behavior_risk, 2),
            'final_risk_score': round(final_risk, 2),
            'moderation_decision': decision,
            'content_embedding': embedding,
            'flags': self._get_flags(similarity, ai_prob, keyword_risk, behavior_risk)
        }

    def _check_similarity(self, text, existing_texts):
        """Check similarity against existing news using TF-IDF + cosine similarity."""
        if not existing_texts:
            return 0.0

        try:
            all_texts = existing_texts + [text]
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)
            self._is_fitted = True

            # Compare the new text against all existing
            new_vector = tfidf_matrix[-1]
            existing_matrix = tfidf_matrix[:-1]

            similarities = cosine_similarity(new_vector, existing_matrix).flatten()
            max_similarity = float(np.max(similarities)) if len(similarities) > 0 else 0.0

            # Scale to 0-100
            return max_similarity * 100
        except Exception:
            return 0.0

    def _detect_ai_generated(self, text):
        """
        Heuristic AI-generated text detection.
        Checks entropy, vocabulary diversity, sentence structure regularity.
        Returns score 0-100.
        """
        if not text or len(text) < 50:
            return 0.0

        words = text.lower().split()
        if len(words) < 10:
            return 0.0

        score = 0.0

        # 1. Vocabulary diversity (type-token ratio)
        unique_words = set(words)
        ttr = len(unique_words) / len(words)
        # AI text tends to have moderate TTR (0.4-0.6)
        if 0.35 < ttr < 0.55:
            score += 15

        # 2. Average word length consistency
        word_lengths = [len(w) for w in words]
        avg_length = sum(word_lengths) / len(word_lengths)
        length_variance = sum((l - avg_length) ** 2 for l in word_lengths) / len(word_lengths)
        # AI text tends to have lower variance in word length
        if length_variance < 6:
            score += 15

        # 3. Sentence length regularity
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 2:
            sent_lengths = [len(s.split()) for s in sentences]
            avg_sent = sum(sent_lengths) / len(sent_lengths)
            sent_variance = sum((l - avg_sent) ** 2 for l in sent_lengths) / len(sent_lengths)
            # AI text tends to have more uniform sentence lengths
            if sent_variance < 20:
                score += 15

        # 4. Perplexity approximation (character-level entropy)
        char_freq = Counter(text.lower())
        total_chars = sum(char_freq.values())
        entropy = -sum((count / total_chars) * math.log2(count / total_chars)
                       for count in char_freq.values() if count > 0)
        # AI text tends to have lower entropy (more predictable)
        if entropy < 4.0:
            score += 20
        elif entropy < 4.5:
            score += 10

        # 5. Repetitive phrase detection
        bigrams = [' '.join(words[i:i+2]) for i in range(len(words)-1)]
        bigram_freq = Counter(bigrams)
        repeated_bigrams = sum(1 for count in bigram_freq.values() if count > 2)
        if repeated_bigrams > 5:
            score += 15

        # 6. Formal/template language patterns
        formal_patterns = [
            r'\bin conclusion\b', r'\bfurthermore\b', r'\bmoreover\b',
            r'\bin summary\b', r'\bit is worth noting\b', r'\bit should be noted\b',
            r'\bthis highlights\b', r'\bthis underscores\b'
        ]
        pattern_matches = sum(1 for p in formal_patterns if re.search(p, text.lower()))
        score += min(20, pattern_matches * 5)

        return min(100, score)

    def _check_keywords(self, text):
        """Check for suspicious keywords. Returns score 0-100."""
        suspicious = self.config.get('SUSPICIOUS_KEYWORDS', [])
        if not suspicious:
            return 0.0

        text_lower = text.lower()
        matches = sum(1 for kw in suspicious if kw.lower() in text_lower)

        if matches == 0:
            return 0.0
        elif matches == 1:
            return 25.0
        elif matches == 2:
            return 50.0
        elif matches == 3:
            return 75.0
        else:
            return 100.0

    def _user_behavior_score(self, user):
        """Score based on user's history. Returns 0-100."""
        if not user:
            return 50.0

        score = 0.0

        # Strike history
        strikes = getattr(user, 'strike_count', 0)
        score += min(40, strikes * 15)

        # Account age factor
        if hasattr(user, 'created_at') and user.created_at:
            age_days = (datetime.utcnow() - user.created_at).days
            if age_days < 1:
                score += 30  # Brand new account
            elif age_days < 7:
                score += 20
            elif age_days < 30:
                score += 10

        # Role factor - trusted reporters get lower risk
        role = getattr(user, 'role', 'registered')
        if role == 'reporter':
            score -= 15
        elif role == 'admin' or role == 'super_admin':
            score -= 30

        return max(0, min(100, score))

    def _make_decision(self, risk_score, user):
        """Determine moderation action based on risk score and user role."""
        auto_threshold = self.config.get('AUTO_PUBLISH_THRESHOLD', 40)
        review_threshold = self.config.get('REVIEW_THRESHOLD', 70)

        role = getattr(user, 'role', 'registered') if user else 'registered'

        if risk_score <= auto_threshold and role in ('reporter', 'admin', 'super_admin'):
            return 'auto_published'
        elif risk_score <= review_threshold:
            return 'review'
        else:
            return 'hold'

    def _generate_embedding(self, text):
        """Generate a JSON-serialized TF-IDF embedding for storage."""
        try:
            if self._is_fitted:
                vector = self.vectorizer.transform([text])
            else:
                vector = self.vectorizer.fit_transform([text])
                self._is_fitted = True

            dense = vector.toarray()[0]
            # Only store non-zero values to save space
            non_zero = {str(i): round(float(v), 4) for i, v in enumerate(dense) if v != 0}
            return json.dumps(non_zero)
        except Exception:
            return None

    def _get_flags(self, similarity, ai_prob, keyword, behavior):
        """Generate human-readable flag messages."""
        flags = []
        if similarity > 60:
            flags.append(f'⚠️ High similarity ({similarity:.0f}%) with existing news')
        if ai_prob > 50:
            flags.append(f'🤖 Possibly AI-generated content ({ai_prob:.0f}%)')
        if keyword > 40:
            flags.append(f'🚨 Suspicious keywords detected')
        if behavior > 50:
            flags.append(f'👤 User behavior risk elevated')
        return flags


# Singleton-like helper
_engine_instance = None

def get_moderation_engine(app_config=None):
    """Get or create the moderation engine instance."""
    global _engine_instance
    if _engine_instance is None and app_config:
        _engine_instance = ModerationEngine(app_config)
    return _engine_instance

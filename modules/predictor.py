#!/usr/bin/env python3
"""
Prediction module for Avatar Tank system.
Handles word prediction and text suggestions.
"""

import os
import glob
import unicodedata


class SimplePredict:
    def __init__(self, dict_dir="/home/havatar/dicts"):
        self.dict_dir = dict_dir
        self.words = []
        self.reload()

    def reload(self):
        self.words.clear()
        try:
            os.makedirs(self.dict_dir, exist_ok=True)
            
            # Load words from the specific words.txt file first
            words_file = os.path.join(self.dict_dir, "words.txt")
            if os.path.exists(words_file):
                try:
                    with open(words_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            w = line.strip()
                            if w:
                                self.words.append(w)
                    print(f"[Predict] loaded {len(self.words)} words from words.txt")
                except Exception as e:
                    print(f"[Predict] failed to load words.txt: {e}")
            
            # Load additional words from other dictionary files
            for fn in glob.glob(os.path.join(self.dict_dir, "*.txt")):
                if os.path.basename(fn) == "words.txt":
                    continue  # Already loaded
                try:
                    with open(fn, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            w = line.strip()
                            if w:
                                self.words.append(w)
                    # Special logging for custom words file
                    if os.path.basename(fn) == "custom_words.txt":
                        print(f"[Predict] loaded custom learned words from {fn}")
                except Exception as e:
                    print("[Predict] failed to load", fn, e)
            
            # Remove duplicates and sort
            self.words = sorted(set(self.words))
            print(f"[Predict] total {len(self.words)} unique words loaded")
            
            # Add some common words if dictionary is empty
            if not self.words:
                self.words = ["hello", "help", "please", "thank", "you", "yes", "no", "stop", "go", "forward", "back", "left", "right", "battery", "camera", "audio", "video", "record", "snapshot", "move", "motor", "system", "status", "reboot", "volume", "microphone", "speaker"]
                print(f"[Predict] using fallback words: {len(self.words)} words")
                
        except Exception as e:
            print(f"[Predict] reload error: {e}")
            self.words = ["error", "loading", "words"]  # Minimal fallback

    def suggest(self, prefix, limit=50):
        if not prefix:
            return []
        
        # Extract just the last word being typed for word-only prediction
        prefix_parts = prefix.strip().split()
        if not prefix_parts:
            return []
        
        # Get only the last word for prediction (ignore preceding text)
        current_word = prefix_parts[-1].lower()
        
        matches = []
        
        # Enhanced diacritics support
        def normalize_text(text):
            # Remove diacritics but keep original structure
            normalized = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
            return normalized.lower()
        
        def text_similarity(word, query):
            """Calculate text similarity for better Romanian matching"""
            word_norm = normalize_text(word)
            query_norm = normalize_text(query)
            
            # Exact match gets highest score
            if word.lower().startswith(query.lower()):
                return 100
            # Normalized match gets high score
            elif word_norm.startswith(query_norm):
                return 90
            # Contains match gets medium score
            elif query.lower() in word.lower():
                return 70
            # Normalized contains gets lower score
            elif query_norm in word_norm:
                return 60
            else:
                return 0
        
        # Score and collect all potential matches
        word_scores = []
        for word in self.words:
            score = text_similarity(word, current_word)
            if score > 0:
                word_scores.append((score, word))
        
        # Sort by score (highest first) and extract words
        word_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return only individual words (no phrase building)
        for score, word in word_scores[:limit]:
            matches.append(word)
            
        return matches[:limit]

    def add_words_from_text(self, text):
        """Extract and save new words from typed text"""
        if not text or len(text.strip()) < 2:
            return 0  # Skip very short text
        
        try:
            # Clean and extract words
            import re
            # Remove punctuation and split into words
            words = re.findall(r'\b[a-zA-ZăâîșțĂÂÎȘȚ]+\b', text.lower())
            
            new_words = []
            for word in words:
                # Only save words that are 2+ characters and not already in dictionary
                if len(word) >= 2 and word not in self.words:
                    new_words.append(word)
                    self.words.append(word)
            
            # Save new words to the custom words file
            if new_words:
                custom_words_file = os.path.join(self.dict_dir, "custom_words.txt")
                with open(custom_words_file, "a", encoding="utf-8") as f:
                    for word in new_words:
                        f.write(word + "\n")
                
                # Resort the words list for better prediction performance
                self.words = sorted(set(self.words))
                print(f"[Predict] Learned {len(new_words)} new words: {', '.join(new_words[:5])}{'...' if len(new_words) > 5 else ''}")
                return len(new_words)
        except Exception as e:
            print(f"[Predict] Error learning words: {e}")
        
        return 0

_predict = SimplePredict()
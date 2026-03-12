import math
import os
import jieba
import re
from collections import defaultdict

class AtriBayesFilter:

    PERSON_WORDS = ["你", "你们", "他", "她", "你妈", "他妈"]
    SAFE_PHRASES = ["垃圾文件", "垃圾分类", "垃圾桶"]

    def __init__(self, data_dir: str):
        self.normal_words = defaultdict(int)
        self.abuse_words = defaultdict(int)

        self.total_normal = 0
        self.total_abuse = 0

        self.vocab = set()

        self.raw_normal_lines = set()
        self.raw_abuse_lines = set()

        self.load_data(data_dir)

    def load_data(self, data_dir):

        normal_path = os.path.join(data_dir, "normal.txt")
        abuse_path = os.path.join(data_dir, "abuse.txt")

        if not os.path.exists(normal_path) or not os.path.exists(abuse_path):
            self.total_normal = 1
            self.total_abuse = 1
            return

        with open(normal_path, 'r', encoding='utf-8') as f:
            for line in f:

                line = line.strip().lower()
                if not line:
                    continue

                self.raw_normal_lines.add(line)

                self.total_normal += 1
                words = jieba.lcut(line)

                for w in words:
                    self.normal_words[w] += 1
                    self.vocab.add(w)

                for bg in self._bigrams(words):
                    self.normal_words[bg] += 1
                    self.vocab.add(bg)

        with open(abuse_path, 'r', encoding='utf-8') as f:
            for line in f:

                line = line.strip().lower()
                if not line:
                    continue

                self.raw_abuse_lines.add(line)

                self.total_abuse += 1
                words = jieba.lcut(line)

                for w in words:
                    self.abuse_words[w] += 1
                    self.vocab.add(w)

                for bg in self._bigrams(words):
                    self.abuse_words[bg] += 1
                    self.vocab.add(bg)

    def _bigrams(self, words):

        for i in range(len(words) - 1):
            yield words[i] + "_" + words[i + 1]

    def _tfidf_weight(self, word, words):

        tf = words.count(word) / len(words)

        df = self.normal_words.get(word, 0) + self.abuse_words.get(word, 0)
        idf = math.log((self.total_normal + self.total_abuse + 1) / (1 + df))

        return tf * idf

    def _calc_log_prob(self, words):

        log_p_normal = math.log(
            self.total_normal / (self.total_normal + self.total_abuse)
        )

        log_p_abuse = math.log(
            self.total_abuse / (self.total_normal + self.total_abuse)
        )

        denom_normal = len(self.vocab) + sum(self.normal_words.values())
        denom_abuse = len(self.vocab) + sum(self.abuse_words.values())

        features = words + list(self._bigrams(words))

        for w in features:

            p_w_normal = (self.normal_words.get(w, 0) + 1) / denom_normal
            p_w_abuse = (self.abuse_words.get(w, 0) + 1) / denom_abuse

            weight = self._tfidf_weight(w, words) if "_" not in w else 1.2

            log_p_normal += weight * math.log(p_w_normal)
            log_p_abuse += weight * math.log(p_w_abuse)

        if words:
            log_p_normal /= len(words)
            log_p_abuse /= len(words)

        if any(p in words for p in self.PERSON_WORDS):
            log_p_abuse += 0.6

        return log_p_normal, log_p_abuse

    def _prob_from_logs(self, log_normal, log_abuse):

        try:
            return 1 / (1 + math.exp(
                min(700, max(-700, log_normal - log_abuse))
            ))
        except:
            return 0.5

    def _clean_text(self, text):

        text = text.lower()
        text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
        return text

    def is_abuse(self, text: str, threshold: float = 0.75) -> bool:

        text = self._clean_text(text)

        if not text:
            return False

        for safe in self.SAFE_PHRASES:
            if safe in text:
                return False

        if text in self.raw_abuse_lines:
            return True

        words = jieba.lcut(text)

        if not words:
            return False

        window_size = min(6, len(words))
        max_prob = 0

        for i in range(len(words) - window_size + 1):

            window = words[i:i + window_size]

            log_n, log_a = self._calc_log_prob(window)
            prob = self._prob_from_logs(log_n, log_a)

            max_prob = max(max_prob, prob)

        return max_prob > threshold

    def get_debug_info(self, text: str):

        text = self._clean_text(text)
        words = jieba.lcut(text)

        log_n, log_a = self._calc_log_prob(words)
        prob = self._prob_from_logs(log_n, log_a)

        return {
            "words": words,
            "log_normal": log_n,
            "log_abuse": log_a,
            "total_prob": prob,
            "decision": "辱骂" if prob > 0.75 else "正常"
        }
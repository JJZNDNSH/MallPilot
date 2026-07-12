import math
import re
from collections import Counter, defaultdict
from typing import Any


# 第一版轻量分词：中文按连续汉字、英文、数字切分，后续可替换为专业分词器。
def tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())


class BM25Search:
    # 初始化 BM25 索引。
    def __init__(self, documents: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        # 原始文档列表。
        self.documents = documents
        # BM25 k1 参数。
        self.k1 = k1
        # BM25 b 参数。
        self.b = b
        # 文档词频列表。
        self.term_freqs = [Counter(tokenize(doc.get("content", "") + " " + doc.get("title", ""))) for doc in documents]
        # 文档长度列表。
        self.doc_lengths = [sum(freq.values()) for freq in self.term_freqs]
        # 平均文档长度。
        self.avg_doc_length = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        # 每个词出现过的文档数量。
        self.doc_freq: dict[str, int] = defaultdict(int)

        # 建立文档频率索引。
        for freq in self.term_freqs:
            for term in freq:
                self.doc_freq[term] += 1

    # 执行关键词召回。
    def search(self, query: str, filters: dict[str, Any], top_k: int = 20) -> list[dict[str, Any]]:
        query_terms = tokenize(query)
        scored: list[dict[str, Any]] = []

        # 先执行结构化过滤，再计算 BM25 分数。
        for index, doc in enumerate(self.documents):
            if not match_filters(doc, filters):
                continue
            score = self._score_document(query_terms, index)
            if score > 0:
                scored.append({"document": doc, "score": score})

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    # 计算单篇文档 BM25 分数。
    def _score_document(self, query_terms: list[str], index: int) -> float:
        score = 0.0
        total_docs = len(self.documents)
        freqs = self.term_freqs[index]
        doc_len = self.doc_lengths[index]

        # 累加 query 中每个命中词的 BM25 得分。
        for term in query_terms:
            if term not in freqs:
                continue
            idf = math.log(1 + (total_docs - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5))
            tf = freqs[term]
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1))
            score += idf * (tf * (self.k1 + 1)) / denominator
        return score


# 校验结构化过滤条件。
def match_filters(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("category") and doc.get("category") != filters["category"]:
        return False
    if filters.get("budget_max") is not None and float(doc.get("price", 0)) > float(filters["budget_max"]):
        return False
    return True

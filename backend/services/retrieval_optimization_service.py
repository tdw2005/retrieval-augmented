import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class RetrievalOptimizationService:
    """
    检索优化服务：
    1. 检索前优化：query 清洗、标准化、关键词扩展
    2. 检索后优化：结果重排序、去重、截断
    """

    def __init__(self):
        self.synonym_map = {
            "RAG": ["检索增强生成", "Retrieval-Augmented Generation", "知识库问答"],
            "大模型": ["LLM", "语言模型", "生成式人工智能"],
            "人工智能": ["AI", "机器学习", "深度学习"],
            "向量数据库": ["vector database", "Chroma", "Milvus", "embedding 检索"],
            "嵌入": ["embedding", "向量化", "文本向量"],
            "检索": ["搜索", "召回", "相似度匹配"],
            "生成": ["回答生成", "响应生成", "LLM 生成"],
        }

    # =========================
    # 检索前优化
    # =========================

    def normalize_query(self, query: str) -> str:
        """
        对用户问题做基础清洗和标准化。
        """
        if not query:
            return ""

        query = query.strip()
        query = re.sub(r"\s+", " ", query)

        replacements = {
            "rag": "RAG",
            "llm": "LLM",
            "ai": "AI",
            "gpt": "GPT",
        }

        words = query.split(" ")
        normalized_words = []
        for word in words:
            lower_word = word.lower()
            normalized_words.append(replacements.get(lower_word, word))

        return " ".join(normalized_words)

    def expand_query(self, query: str) -> str:
        """
        对 query 做关键词扩展，提高召回率。
        """
        expanded_terms = []

        for key, synonyms in self.synonym_map.items():
            if key in query:
                expanded_terms.extend(synonyms)

        expanded_terms = list(dict.fromkeys(expanded_terms))[:8]

        if expanded_terms:
            return f"{query}。相关关键词：{'，'.join(expanded_terms)}"

        return query

    def rewrite_query_for_retrieval(self, query: str) -> Dict[str, str]:
        """
        检索前优化总入口。
        """
        original_query = query
        normalized_query = self.normalize_query(query)
        optimized_query = self.expand_query(normalized_query)

        return {
            "original_query": original_query,
            "normalized_query": normalized_query,
            "optimized_query": optimized_query
        }

    # =========================
    # 检索后优化
    # =========================

    def _tokenize(self, text: str) -> List[str]:
        """
        轻量分词，不额外依赖 jieba。
        """
        if not text:
            return []

        return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text.lower())

    def _keyword_overlap_score(self, query: str, text: str) -> float:
        """
        计算 query 与文本块之间的关键词重合度。
        """
        query_tokens = set(self._tokenize(query))
        text_tokens = set(self._tokenize(text))

        if not query_tokens or not text_tokens:
            return 0.0

        overlap = query_tokens & text_tokens
        return len(overlap) / len(query_tokens)

    def rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        检索后重排序：
        综合原向量相似度分数和关键词重合度。
        """
        reranked = []

        for item in results:
            text = item.get("text", "")
            vector_score = float(item.get("score", 0.0))
            keyword_score = self._keyword_overlap_score(query, text)

            final_score = vector_score * 0.75 + keyword_score * 0.25

            new_item = dict(item)
            new_item["original_score"] = vector_score
            new_item["keyword_score"] = round(keyword_score, 6)
            new_item["rerank_score"] = round(final_score, 6)

            reranked.append(new_item)

        reranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return reranked

    def deduplicate_results(
        self,
        results: List[Dict[str, Any]],
        similarity_threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        去掉高度重复的检索结果。
        """
        unique_results = []

        for item in results:
            text = item.get("text", "")
            if not text:
                continue

            is_duplicate = False

            for kept in unique_results:
                kept_text = kept.get("text", "")
                similarity = SequenceMatcher(None, text, kept_text).ratio()

                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_results.append(item)

        return unique_results

    def optimize_search_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        检索后优化总入口：
        1. 重排序
        2. 去重
        3. 截取 top_k
        """
        if not results:
            return []

        reranked_results = self.rerank_results(query, results)
        deduplicated_results = self.deduplicate_results(reranked_results)

        return deduplicated_results[:top_k]
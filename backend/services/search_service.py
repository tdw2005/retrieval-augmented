from datetime import datetime
from typing import Any, Dict, List
import json
import logging
import os

import chromadb
from pymilvus import MilvusClient

from services.embedding_service import EmbeddingService
from services.retrieval_optimization_service import RetrievalOptimizationService
from utils.config import MILVUS_CONFIG, VectorDBProvider

chromadb_path = "./03-vector-store/chromadb"

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.retrieval_optimizer = RetrievalOptimizationService()
        self.search_results_dir = "04-search-results"
        os.makedirs(self.search_results_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(chromadb_path)

    def _get_milvus_client(self) -> MilvusClient:
        return MilvusClient(
            uri=MILVUS_CONFIG.get("endpoint", "http://localhost:19530"),
            token=MILVUS_CONFIG.get("token", "root:Milvus"),
            db_name=MILVUS_CONFIG["uri"],
        )

    def get_providers(self) -> List[Dict[str, str]]:
        return [
            {"id": VectorDBProvider.MILVUS.value, "name": "Milvus"},
            {"id": VectorDBProvider.CHROMA.value, "name": "Chroma"},
        ]

    def list_collections(self, provider: str = VectorDBProvider.CHROMA.value) -> List[Dict[str, Any]]:
        provider = self._normalise_provider(provider)
        if provider == VectorDBProvider.MILVUS.value:
            return self._list_milvus_collections()
        return self._list_chroma_collections()

    def _list_chroma_collections(self) -> List[Dict[str, Any]]:
        collections = []
        for item in self.chroma_client.list_collections():
            name = item if isinstance(item, str) else item.name
            try:
                collection = self.chroma_client.get_collection(name)
                collections.append({"id": name, "name": name, "count": collection.count()})
            except Exception as e:
                logger.error(f"Error getting Chroma collection {name}: {str(e)}")
                collections.append({"id": name, "name": name, "count": None})
        return collections

    def _list_milvus_collections(self) -> List[Dict[str, Any]]:
        client = self._get_milvus_client()
        collections = []
        for name in client.list_collections():
            try:
                stats = client.get_collection_stats(name)
                collections.append({
                    "id": name,
                    "name": name,
                    "count": int(stats.get("row_count", 0)),
                })
            except Exception as e:
                logger.error(f"Error getting Milvus collection {name}: {str(e)}")
                collections.append({"id": name, "name": name, "count": None})
        return collections

    def save_search_results(self, query: str, collection_id: str, results: List[Dict[str, Any]]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        collection_base = os.path.basename(collection_id)
        filename = f"search_{collection_base}_{timestamp}.json"
        filepath = os.path.join(self.search_results_dir, filename)

        search_data = {
            "query": query,
            "collection_id": collection_id,
            "timestamp": datetime.now().isoformat(),
            "results": results,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(search_data, f, ensure_ascii=False, indent=2)

        return filepath

    async def search(
        self,
        query: str,
        collection_id: str,
        provider: str = VectorDBProvider.CHROMA.value,
        top_k: int = 3,
        threshold: float = 0.0,
        word_count_threshold: int = 0,
        save_results: bool = False,
        enable_pre_optimization: bool = True,
        enable_post_optimization: bool = True,
    ) -> Dict[str, Any]:
        provider = self._normalise_provider(provider)
        logger.info(
            "Search request provider=%s collection=%s top_k=%s threshold=%s word_count_threshold=%s",
            provider,
            collection_id,
            top_k,
            threshold,
            word_count_threshold,
        )

        query_info = self.retrieval_optimizer.rewrite_query_for_retrieval(query)
        retrieval_query = query_info["optimized_query"] if enable_pre_optimization else query

        if provider == VectorDBProvider.MILVUS.value:
            processed_results = self._search_milvus(
                collection_id=collection_id,
                retrieval_query=retrieval_query,
                top_k=top_k,
                threshold=threshold,
                word_count_threshold=word_count_threshold,
            )
        else:
            processed_results = self._search_chroma(
                collection_id=collection_id,
                retrieval_query=retrieval_query,
                top_k=top_k,
                threshold=threshold,
                word_count_threshold=word_count_threshold,
            )

        if enable_post_optimization:
            final_results = self.retrieval_optimizer.optimize_search_results(
                query=query,
                results=processed_results,
                top_k=top_k,
            )
        else:
            final_results = processed_results[:top_k]

        response_data = {
            "query_info": query_info,
            "used_query": retrieval_query,
            "provider": provider,
            "results": final_results,
        }

        if save_results and final_results:
            response_data["saved_filepath"] = self.save_search_results(
                retrieval_query,
                collection_id,
                final_results,
            )

        return response_data

    def _search_chroma(
        self,
        collection_id: str,
        retrieval_query: str,
        top_k: int,
        threshold: float,
        word_count_threshold: int,
    ) -> List[Dict[str, Any]]:
        collection = self.chroma_client.get_collection(collection_id)
        num_entities = collection.count()
        if num_entities == 0:
            raise ValueError(f"Collection {collection_id} is empty")

        sample_entity = collection.get(limit=1, include=["metadatas"])
        sample_metadata = sample_entity["metadatas"][0]
        query_embedding = self.embedding_service.create_single_embedding(
            retrieval_query,
            provider=sample_metadata.get("embedding_provider"),
            model=sample_metadata.get("embedding_model"),
        )

        candidate_k = min(max(top_k * 3, top_k), num_entities)
        results = collection.query(query_embeddings=[query_embedding], n_results=candidate_k)
        result_count = len(results["ids"][0]) if results.get("ids") else 0

        processed_results = []
        for index in range(result_count):
            hit_score = 1 - results["distances"][0][index]
            metadata = results["metadatas"][0][index]
            word_count = int(metadata.get("word_count", 0))
            if hit_score < threshold or word_count < word_count_threshold:
                continue
            processed_results.append({
                "text": results["documents"][0][index],
                "score": float(hit_score),
                "metadata": self._result_metadata(
                    source=metadata.get("document_name"),
                    page=metadata.get("page_number"),
                    chunk=results["ids"][0][index],
                    total_chunks=metadata.get("total_chunks"),
                    page_range=metadata.get("page_range"),
                    word_count=word_count,
                    embedding_provider=metadata.get("embedding_provider"),
                    embedding_model=metadata.get("embedding_model"),
                    embedding_timestamp=metadata.get("embedding_timestamp"),
                    vector_db=VectorDBProvider.CHROMA.value,
                ),
            })
        return processed_results

    def _search_milvus(
        self,
        collection_id: str,
        retrieval_query: str,
        top_k: int,
        threshold: float,
        word_count_threshold: int,
    ) -> List[Dict[str, Any]]:
        client = self._get_milvus_client()
        stats = client.get_collection_stats(collection_id)
        num_entities = int(stats.get("row_count", 0))
        if num_entities == 0:
            raise ValueError(f"Collection {collection_id} is empty")

        sample_entities = client.query(
            collection_name=collection_id,
            filter="id >= 0",
            limit=1,
            output_fields=["embedding_provider", "embedding_model"],
        )
        if not sample_entities:
            raise ValueError(f"Collection {collection_id} has no embedding metadata")

        sample_metadata = sample_entities[0]
        query_embedding = self.embedding_service.create_single_embedding(
            retrieval_query,
            provider=sample_metadata.get("embedding_provider"),
            model=sample_metadata.get("embedding_model"),
        )

        candidate_k = min(max(top_k * 3, top_k), num_entities)
        client.load_collection(collection_id)
        results = client.search(
            collection_name=collection_id,
            data=[query_embedding],
            anns_field="vector",
            search_params={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=candidate_k,
            output_fields=[
                "content",
                "document_name",
                "chunk_id",
                "total_chunks",
                "word_count",
                "page_number",
                "page_range",
                "embedding_provider",
                "embedding_model",
                "embedding_timestamp",
            ],
        )

        processed_results = []
        for hit in (results[0] if results else []):
            score = float(hit.get("distance", hit.get("score", 0)))
            entity = hit.get("entity", {})
            word_count = int(entity.get("word_count", 0))
            if score < threshold or word_count < word_count_threshold:
                continue
            processed_results.append({
                "text": entity.get("content", ""),
                "score": score,
                "metadata": self._result_metadata(
                    source=entity.get("document_name"),
                    page=entity.get("page_number"),
                    chunk=entity.get("chunk_id", hit.get("id")),
                    total_chunks=entity.get("total_chunks"),
                    page_range=entity.get("page_range"),
                    word_count=word_count,
                    embedding_provider=entity.get("embedding_provider"),
                    embedding_model=entity.get("embedding_model"),
                    embedding_timestamp=entity.get("embedding_timestamp"),
                    vector_db=VectorDBProvider.MILVUS.value,
                ),
            })
        return processed_results

    def _result_metadata(
        self,
        source,
        page,
        chunk,
        total_chunks,
        page_range,
        word_count,
        embedding_provider,
        embedding_model,
        embedding_timestamp,
        vector_db,
    ) -> Dict[str, Any]:
        return {
            "source": source,
            "page": page,
            "chunk": chunk,
            "total_chunks": total_chunks,
            "page_range": page_range,
            "word_count": word_count,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embedding_timestamp": embedding_timestamp,
            "vector_db": vector_db,
        }

    def _normalise_provider(self, provider: str) -> str:
        provider = (provider or VectorDBProvider.CHROMA.value).lower()
        if provider not in {VectorDBProvider.MILVUS.value, VectorDBProvider.CHROMA.value}:
            raise ValueError(f"Unsupported vector database provider: {provider}")
        return provider

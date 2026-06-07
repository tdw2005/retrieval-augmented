"""Run a reproducible retrieval baseline on the repository's chunked documents.

The script intentionally uses only Python's standard library. It provides a
stable baseline when the full embedding/model environment or API keys are not
available. The existing vector-search endpoint can later be compared against
the same labelled benchmark.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Tokenize English words and Chinese characters without third-party tools."""
    normalized = text.lower().replace("\n", " ")
    tokens = TOKEN_PATTERN.findall(normalized)
    chinese = [token for token in tokens if "\u4e00" <= token <= "\u9fff"]
    bigrams = [chinese[i] + chinese[i + 1] for i in range(len(chinese) - 1)]
    return tokens + bigrams


class BM25Retriever:
    def __init__(self, chunks: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.term_counts = [Counter(tokenize(chunk["content"])) for chunk in chunks]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1)
        document_frequency: Counter[str] = Counter()
        for counts in self.term_counts:
            document_frequency.update(counts.keys())
        count = len(chunks)
        self.idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_terms = Counter(tokenize(query))
        ranked: list[dict[str, Any]] = []
        for chunk, counts, length in zip(self.chunks, self.term_counts, self.lengths):
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / max(self.average_length, 1)
                )
                score += self.idf.get(term, 0.0) * (
                    frequency * (self.k1 + 1) / denominator
                ) * query_frequency
            ranked.append(
                {
                    "score": score,
                    "page": int(chunk["metadata"]["page_number"]),
                    "chunk_id": chunk["metadata"]["chunk_id"],
                    "text": chunk["content"],
                }
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]


def evaluate_query(results: list[dict[str, Any]], expected_pages: list[int]) -> dict[str, float]:
    found_pages = [result["page"] for result in results]
    expected = set(expected_pages)
    relevant = [page for page in found_pages if page in expected]
    reciprocal_rank = 0.0
    for rank, page in enumerate(found_pages, 1):
        if page in expected:
            reciprocal_rank = 1 / rank
            break
    return {
        "precision_at_k": len(relevant) / max(len(found_pages), 1),
        "recall_at_k": len(set(relevant)) / max(len(expected), 1),
        "mrr": reciprocal_rank,
        "hit": float(bool(relevant)),
    }


def average_metrics(results: list[dict[str, Any]]) -> dict[str, float]:
    metric_names = ("precision_at_k", "recall_at_k", "mrr", "hit")
    return {
        name: sum(item["metrics"][name] for item in results) / max(len(results), 1)
        for name in metric_names
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Retriever: {report['retriever']}",
        f"- Top K: {report['top_k']}",
        "",
        "| Dataset | Queries | Precision@K | Recall@K | MRR | Hit Rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for dataset in report["datasets"]:
        metrics = dataset["metrics"]
        lines.append(
            f"| {dataset['name']} | {len(dataset['queries'])} | "
            f"{metrics['precision_at_k']:.3f} | {metrics['recall_at_k']:.3f} | "
            f"{metrics['mrr']:.3f} | {metrics['hit']:.3f} |"
        )
    lines.extend(["", "## Query Details", ""])
    for dataset in report["datasets"]:
        lines.append(f"### {dataset['name']}")
        lines.append("")
        for item in dataset["queries"]:
            lines.append(
                f"- `{item['query']}` expected={item['expected_pages']} "
                f"found={item['found_pages']} MRR={item['metrics']['mrr']:.3f}"
            )
        lines.append("")
    return "\n".join(lines)


def run(benchmark_path: Path, output_dir: Path, top_k: int) -> dict[str, Any]:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    dataset_reports = []
    for dataset in benchmark["datasets"]:
        document_path = (benchmark_path.parent / dataset["document"]).resolve()
        document = json.loads(document_path.read_text(encoding="utf-8"))
        retriever = BM25Retriever(document["chunks"])
        query_reports = []
        for case in dataset["queries"]:
            results = retriever.search(case["query"], top_k)
            metrics = evaluate_query(results, case["expected_pages"])
            query_reports.append(
                {
                    "query": case["query"],
                    "expected_pages": case["expected_pages"],
                    "found_pages": [result["page"] for result in results],
                    "metrics": metrics,
                    "results": results,
                }
            )
        dataset_reports.append(
            {
                "name": dataset["name"],
                "document": dataset["document"],
                "chunking_method": document.get("chunking_method"),
                "total_chunks": document.get("total_chunks"),
                "metrics": average_metrics(query_reports),
                "queries": query_reports,
            }
        )

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "retriever": "BM25 character-and-bigram baseline",
        "top_k": top_k,
        "datasets": dataset_reports,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "retrieval_evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "retrieval_evaluation.md").write_text(
        build_markdown(report), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path(__file__).with_name("retrieval_benchmark.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "06-evaluation-result",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    report = run(args.benchmark.resolve(), args.output_dir.resolve(), args.top_k)
    for dataset in report["datasets"]:
        metrics = dataset["metrics"]
        print(
            f"{dataset['name']}: P@K={metrics['precision_at_k']:.3f}, "
            f"R@K={metrics['recall_at_k']:.3f}, MRR={metrics['mrr']:.3f}, "
            f"Hit={metrics['hit']:.3f}"
        )


if __name__ == "__main__":
    main()

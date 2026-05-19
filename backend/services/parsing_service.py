import logging
import re
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

class ParsingService:
    """
    PDF文档解析服务类
    
    该类提供多种解析策略来提取和构建PDF文档内容，包括：
    - 全文提取
    - 逐页解析
    - 基于标题的分段
    - 文本和表格混合解析
    """

    def parse_pdf(self, text: str, method: str, metadata: dict, page_map: list = None) -> dict:
        """
        使用指定方法解析PDF文档

        参数:
            text (str): PDF文档的文本内容
            method (str): 解析方法 ('all_text', 'by_pages', 'by_titles', 或 'text_and_tables')
            metadata (dict): 文档元数据，包括文件名和其他属性
            page_map (list): 包含每页内容和元数据的字典列表

        返回:
            dict: 解析后的文档数据，包括元数据和结构化内容

        异常:
            ValueError: 当page_map为空或指定了不支持的解析方法时抛出
        """
        try:
            if not page_map:
                raise ValueError("Page map is required for parsing.")

            normalized_page_map = self._normalize_page_map(page_map)
            parsed_content = []
            total_pages = len(normalized_page_map)

            if method == "all_text":
                parsed_content = self._parse_all_text(normalized_page_map)
            elif method == "by_pages":
                parsed_content = self._parse_by_pages(normalized_page_map)
            elif method == "by_titles":
                parsed_content = self._parse_by_titles(normalized_page_map)
            elif method == "text_and_tables":
                parsed_content = self._parse_text_and_tables(normalized_page_map)
            else:
                raise ValueError(f"Unsupported parsing method: {method}")

            summary = self._build_summary(parsed_content, total_pages)

            document_data = {
                "metadata": {
                    "filename": metadata.get("filename", ""),
                    "total_pages": total_pages,
                    "loading_method": metadata.get("loading_method", ""),
                    "parsing_method": method,
                    "timestamp": datetime.now().isoformat()
                },
                "summary": summary,
                "content": parsed_content
            }

            return document_data

        except Exception as e:
            logger.error(f"Error in parse_pdf: {str(e)}")
            raise

    def _parse_all_text(self, page_map: list) -> list:
        """
        将文档中的所有文本内容提取为连续流

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的文本内容的字典列表
        """
        merged_text = "\n\n".join(page["text"] for page in page_map if page["text"])
        if not merged_text.strip():
            return []

        total_pages = len(page_map)
        return [self._build_item(
            item_type="text",
            content=merged_text,
            page=1,
            start_page=1,
            end_page=page_map[-1]["page"] if total_pages else 1,
            page_range=f"1-{page_map[-1]['page']}" if total_pages > 1 else "1",
            label="全文连续文本"
        )]

    def _parse_by_pages(self, page_map: list) -> list:
        """
        逐页解析文档，保持页面边界

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带页码的分页内容的字典列表
        """
        parsed_content = []
        for page in page_map:
            parsed_content.append(self._build_item(
                item_type="page",
                content=page["text"],
                page=page["page"],
                start_page=page["page"],
                end_page=page["page"],
                page_range=str(page["page"]),
                label=f"第 {page['page']} 页"
            ))
        return parsed_content

    def _parse_by_titles(self, page_map: list) -> list:
        """
        通过识别标题来解析文档并将内容组织成章节

        使用简单的启发式方法识别标题：
        长度小于60个字符且全部大写的行被视为章节标题

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含带标题和页码的分章节内容的字典列表
        """
        parsed_content = []
        current_title = None
        current_content = []
        current_start_page = None
        last_content_page = None
        title_count = 0

        for page in page_map:
            lines = page["text"].split("\n")
            for line in lines:
                cleaned_line = line.strip()
                if self._is_title_line(cleaned_line):
                    if current_title:
                        section_content = "\n".join(current_content).strip()
                        parsed_content.append(self._build_item(
                            item_type="section",
                            content=section_content,
                            page=current_start_page or page["page"],
                            start_page=current_start_page or page["page"],
                            end_page=last_content_page or current_start_page or page["page"],
                            page_range=self._format_page_range(
                                current_start_page or page["page"],
                                last_content_page or current_start_page or page["page"]
                            ),
                            title=current_title,
                            label=current_title,
                            title_level=self._infer_title_level(current_title)
                        ))
                    current_title = cleaned_line
                    current_content = []
                    current_start_page = page["page"]
                    last_content_page = page["page"]
                    title_count += 1
                else:
                    if cleaned_line:
                        last_content_page = page["page"]
                    current_content.append(line)

        if current_title:
            section_content = "\n".join(current_content).strip()
            parsed_content.append(self._build_item(
                item_type="section",
                content=section_content,
                page=current_start_page or page_map[0]["page"],
                start_page=current_start_page or page_map[0]["page"],
                end_page=last_content_page or current_start_page or page_map[-1]["page"],
                page_range=self._format_page_range(
                    current_start_page or page_map[0]["page"],
                    last_content_page or current_start_page or page_map[-1]["page"]
                ),
                title=current_title,
                label=current_title,
                title_level=self._infer_title_level(current_title)
            ))

        if not parsed_content:
            fallback_content = "\n\n".join(page["text"] for page in page_map if page["text"]).strip()
            if fallback_content:
                parsed_content.append(self._build_item(
                    item_type="section",
                    content=fallback_content,
                    page=page_map[0]["page"],
                    start_page=page_map[0]["page"],
                    end_page=page_map[-1]["page"],
                    page_range=self._format_page_range(page_map[0]["page"], page_map[-1]["page"]),
                    title="未识别出明确标题，按全文返回",
                    label="全文章节"
                ))

        if parsed_content:
            parsed_content[0]["detected_title_count"] = title_count

        return parsed_content

    def _parse_text_and_tables(self, page_map: list) -> list:
        """
        通过分离文本和表格内容来解析文档

        使用基本的表格检测启发式方法（存在'|'或制表符）
        来识别潜在的表格内容

        参数:
            page_map (list): 包含每页内容的字典列表

        返回:
            list: 包含分离的文本和表格内容（带页码）的字典列表
        """
        parsed_content = []
        for page in page_map:
            blocks = self._split_into_blocks(page["text"])
            if not blocks:
                blocks = [page["text"]]

            for index, block in enumerate(blocks, 1):
                block_type = "table" if self._is_table_block(block) else "text"
                parsed_content.append(self._build_item(
                    item_type=block_type,
                    content=block,
                    page=page["page"],
                    start_page=page["page"],
                    end_page=page["page"],
                    page_range=str(page["page"]),
                    label=f"第 {page['page']} 页第 {index} 块",
                    block_index=index,
                    row_count=len([line for line in block.splitlines() if line.strip()]),
                    estimated_columns=self._estimate_column_count(block) if block_type == "table" else None
                ))
        return parsed_content

    def _normalize_page_map(self, page_map: list) -> list:
        normalized = []
        for entry in page_map:
            page_number = int(entry.get("page", len(normalized) + 1))
            text = self._clean_text(entry.get("text", ""))
            normalized.append({
                "page": page_number,
                "text": text,
                "metadata": entry.get("metadata", {})
            })
        return normalized

    def _build_item(
        self,
        item_type: str,
        content: str,
        page: int,
        start_page: int,
        end_page: int,
        page_range: str,
        title: str = None,
        label: str = None,
        title_level: int = None,
        block_index: int = None,
        row_count: int = None,
        estimated_columns: int = None
    ) -> dict:
        cleaned_content = content.strip()
        item = {
            "type": item_type,
            "page": page,
            "start_page": start_page,
            "end_page": end_page,
            "page_range": page_range,
            "content": cleaned_content,
            "char_count": len(cleaned_content),
            "word_count": self._count_words(cleaned_content),
            "line_count": len([line for line in cleaned_content.splitlines() if line.strip()]),
            "preview": cleaned_content[:180]
        }
        if title:
            item["title"] = title
        if label:
            item["label"] = label
        if title_level is not None:
            item["title_level"] = title_level
        if block_index is not None:
            item["block_index"] = block_index
        if row_count is not None:
            item["row_count"] = row_count
        if estimated_columns is not None:
            item["estimated_columns"] = estimated_columns
        return item

    def _build_summary(self, parsed_content: list, total_pages: int) -> dict:
        type_counts: Dict[str, int] = {}
        total_words = 0
        total_chars = 0

        for item in parsed_content:
            item_type = item.get("type", "unknown")
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            total_words += item.get("word_count", 0)
            total_chars += item.get("char_count", 0)

        return {
            "block_count": len(parsed_content),
            "total_pages": total_pages,
            "section_count": type_counts.get("section", 0),
            "table_block_count": type_counts.get("table", 0),
            "text_block_count": type_counts.get("text", 0),
            "page_block_count": type_counts.get("page", 0),
            "total_words": total_words,
            "total_characters": total_chars,
            "average_words_per_block": round(total_words / len(parsed_content), 2) if parsed_content else 0,
            "content_type_distribution": type_counts
        }

    def _clean_text(self, text: str) -> str:
        lines = [re.sub(r"\s+$", "", line) for line in text.splitlines()]
        return "\n".join(lines).strip()

    def _count_words(self, text: str) -> int:
        return len([token for token in re.split(r"\s+", text.strip()) if token])

    def _format_page_range(self, start_page: int, end_page: int) -> str:
        if start_page == end_page:
            return str(start_page)
        return f"{start_page}-{end_page}"

    def _split_into_blocks(self, text: str) -> List[str]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
        return blocks

    def _is_title_line(self, line: str) -> bool:
        if not line or len(line) > 80:
            return False

        if line.endswith(("。", "；", ";", ".", "?", "！", ":", "：", ",")):
            return False

        chinese_heading_pattern = (
            r"^(第[一二三四五六七八九十百零0-9]+[章节部分篇]|"
            r"[一二三四五六七八九十]+、|"
            r"[0-9]+(\.[0-9]+){0,3}\s+|"
            r"[(（][一二三四五六七八九十0-9]+[)）])"
        )
        if re.match(chinese_heading_pattern, line):
            return True

        if any(char.isalpha() for char in line) and line.upper() == line and len(line.split()) <= 12:
            return True

        words = [word for word in re.split(r"\s+", line) if word]
        if 1 <= len(words) <= 10:
            title_case_words = [word for word in words if word[:1].isupper()]
            if len(title_case_words) >= max(1, int(len(words) * 0.6)):
                return True

        return False

    def _infer_title_level(self, title: str) -> int:
        if re.match(r"^第[一二三四五六七八九十百零0-9]+篇", title):
            return 1
        if re.match(r"^第[一二三四五六七八九十百零0-9]+章", title):
            return 2
        if re.match(r"^第[一二三四五六七八九十百零0-9]+节", title):
            return 3
        if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", title):
            return 3
        if re.match(r"^[0-9]+\.[0-9]+", title):
            return 2
        if re.match(r"^[0-9]+", title) or re.match(r"^[一二三四五六七八九十]+、", title):
            return 1
        return 1

    def _is_table_block(self, block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            return False

        if any(("|" in line or "\t" in line) for line in lines):
            return True

        aligned_lines = sum(1 for line in lines if re.search(r"\S+\s{2,}\S+", line))
        numeric_lines = sum(1 for line in lines if re.search(r"\d", line))

        return aligned_lines >= 2 and numeric_lines >= 1

    def _estimate_column_count(self, block: str) -> int:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            return 0

        if any("|" in line for line in lines):
            return max(len([cell for cell in line.split("|") if cell.strip()]) for line in lines)

        return max(len(re.split(r"\s{2,}|\t+", line)) for line in lines)

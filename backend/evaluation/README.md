# 可复现检索评估

该目录用于完成“将课程提供的程序在数据上调通运行，并根据测试实例分析优缺点”。

## 当前状态

- 仓库已提供完整 RAG 程序，包括解析、分块、Embedding、Chroma/Milvus 索引、检索和生成。
- 仓库已包含论文、解析结果、分块结果、Embedding、Chroma 数据库和历史检索结果。
- 原仓库未提交 README 中提到的 Python requirements 文件；现已补充 `backend/requirements-backend.txt`。
- 已在 `backend/.venv` 安装完整依赖，FastAPI 后端可成功导入并读取现有 Chroma 数据库。
- React 前端已通过 `npm run build` 验证。
- 本目录提供零额外依赖的 BM25 基线，确保测试实例和评估指标可以立即复现。

## 运行

在仓库根目录执行：

```powershell
python backend/evaluation/run_retrieval_evaluation.py
```

结果写入：

- `backend/06-evaluation-result/retrieval_evaluation.json`
- `backend/06-evaluation-result/retrieval_evaluation.md`

完整后端与前端运行：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-backend.txt
cd backend
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8001
```

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

## 指标

- `Precision@K`：前 K 个结果中相关结果的比例。
- `Recall@K`：标准答案页面中被前 K 个结果覆盖的比例。
- `MRR`：第一个相关结果排名的倒数，越接近 1 越好。
- `Hit Rate`：查询是否至少检索到一个相关页面。

## 初步优缺点

优点：

- 数据处理链路完整，模块边界清楚，支持多种 PDF 解析、分块、Embedding、向量库和生成模型。
- 保存了页码、分块编号和模型信息，具备进行检索评估和错误分析的基础。
- Chroma 路径适合本地实验，避免必须部署独立 Milvus 服务。

缺点：

- 原 README 的依赖链接指向外部原始仓库，且未固定依赖版本；本次补充了依赖清单，但未来仍需要维护版本兼容性。
- 原有 `/evaluate` 依赖人工 CSV；本次增加了标准测试集和 BM25 基线，但向量检索尚未覆盖全部测试实例。
- Chroma 相似度直接使用 `1 - distance`，但没有明确固定距离度量，阈值含义不稳定。
- 不同分块数据可能丢失真实页码。例如 `phone_by_paragraphs` 把三页内容合并为一页，会影响引用定位。
- 代码、测试数据和大量历史运行产物混在一起，后续比较实验容易选错版本。

## 已完成的实际向量检索

集合：`phone_huggingface_20260510170119`

问题：`哪款手机支持无线充电，充电功率是多少？`

使用模型：`BAAI/bge-small-zh-v1.5`

向量检索排序：

1. 第 2 页，分数 0.5520，正确答案：iPhone 17 支持 40W 无线充电。
2. 第 1 页，分数 0.5107。
3. 第 3 页，分数 0.5096，内容明确为“不支持无线充电”。

同一问题在 BM25 基线中正确页排第 2，向量检索将其提升到第 1，说明语义检索对自然语言问句更有优势。但第 3 页包含“不支持无线充电”，仍获得较高相似度，说明单纯向量相似度不擅长处理否定关系，需要重排序或在生成阶段进一步判断。

## 后续向量检索对照

后续可使用同一份 `retrieval_benchmark.json` 批量调用 `/search`，将向量检索结果与本 BM25 基线对照。重点比较：

- 同义改写和语义问题上，向量检索是否优于关键词基线。
- 精确型号、数字、命令和专有名词问题上，关键词基线是否更稳定。
- 不同 `top_k`、阈值和分块策略对 Precision、Recall 与 MRR 的影响。

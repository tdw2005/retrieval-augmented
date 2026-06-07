# Retrieval Evaluation Report

- Generated at: 2026-06-07T15:32:06
- Retriever: BM25 character-and-bigram baseline
- Top K: 3

| Dataset | Queries | Precision@K | Recall@K | MRR | Hit Rate |
|---|---:|---:|---:|---:|---:|
| phone_by_pages | 5 | 0.533 | 1.000 | 0.700 | 1.000 |
| uv_tutorial_by_pages | 5 | 0.333 | 1.000 | 1.000 | 1.000 |

## Query Details

### phone_by_pages

- `哪款手机支持无线充电，充电功率是多少？` expected=[2] found=[3, 2, 1] MRR=0.500
- `天玑7025-Ultra处理器属于哪款手机？` expected=[3] found=[1, 3, 2] MRR=0.500
- `哪款手机支持IP68防水防尘？` expected=[1] found=[1, 3, 2] MRR=1.000
- `比较三款手机的后置摄像头像素` expected=[1, 2, 3] found=[1, 2, 3] MRR=1.000
- `哪两款手机的屏幕刷新率是120Hz？` expected=[2, 3] found=[1, 2, 3] MRR=0.500

### uv_tutorial_by_pages

- `uv是什么，它比pip快多少？` expected=[1] found=[1, 2, 5] MRR=1.000
- `如何使用PowerShell一键安装uv？` expected=[2] found=[2, 1, 3] MRR=1.000
- `如何将uv.exe加入用户级PATH？` expected=[3] found=[3, 2, 4] MRR=1.000
- `国内网络无法从GitHub下载uv时怎么办？` expected=[4] found=[4, 1, 2] MRR=1.000
- `如何在VS Code中选择uv虚拟环境的解释器？` expected=[5] found=[5, 2, 1] MRR=1.000

import React, { useMemo, useState } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const parsingMethods = [
  { value: 'all_text', label: '全文连续文本' },
  { value: 'by_pages', label: '按页解析' },
  { value: 'by_titles', label: '按标题解析' },
  { value: 'text_and_tables', label: '文本与表格拆分' }
];

const loadingMethods = [
  { value: 'pymupdf', label: 'PyMuPDF' },
  { value: 'pypdf', label: 'PyPDF' },
  { value: 'unstructured', label: 'Unstructured' },
  { value: 'pdfplumber', label: 'PDF Plumber' }
];

const methodLabelMap = parsingMethods.reduce((accumulator, method) => {
  accumulator[method.value] = method.label;
  return accumulator;
}, {});

const ParseFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('pymupdf');
  const [parsingOption, setParsingOption] = useState('all_text');
  const [comparisonMethods, setComparisonMethods] = useState(['by_pages', 'by_titles']);
  const [parseResults, setParseResults] = useState([]);
  const [status, setStatus] = useState('');
  const [contentTypeFilter, setContentTypeFilter] = useState('all');
  const [pageFilter, setPageFilter] = useState('');
  const [keywordFilter, setKeywordFilter] = useState('');

  const requestedMethods = useMemo(() => {
    const ordered = [parsingOption, ...comparisonMethods.filter((method) => method !== parsingOption)];
    return Array.from(new Set(ordered));
  }, [comparisonMethods, parsingOption]);

  const filteredResults = useMemo(() => {
    const pageValue = Number(pageFilter);
    return parseResults.map((result) => {
      const filteredContent = (result.content || []).filter((item) => {
        const matchType = contentTypeFilter === 'all' || item.type === contentTypeFilter;
        const matchPage = !pageFilter || (
          Number.isFinite(pageValue) &&
          item.start_page <= pageValue &&
          item.end_page >= pageValue
        );
        const matchKeyword = !keywordFilter || (
          `${item.title || ''}\n${item.content || ''}`.toLowerCase().includes(keywordFilter.toLowerCase())
        );
        return matchType && matchPage && matchKeyword;
      });

      return {
        ...result,
        filteredContent
      };
    });
  }, [contentTypeFilter, keywordFilter, pageFilter, parseResults]);

  const handleMethodToggle = (method) => {
    setComparisonMethods((current) => (
      current.includes(method)
        ? current.filter((item) => item !== method)
        : [...current, method]
    ));
  };

  const handleProcess = async () => {
    if (!file || !loadingMethod || !parsingOption) {
      setStatus('请先选择文件、装载工具和主解析方式');
      return;
    }

    setStatus('正在解析并生成对比结果...');
    setParseResults([]);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('loading_method', loadingMethod);
      formData.append('parsing_option', parsingOption);
      formData.append('parsing_options', JSON.stringify(requestedMethods));

      const response = await fetch(`${apiBaseUrl}/parse`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const results = data.comparison_results || (data.parsed_content ? [data.parsed_content] : []);
      setParseResults(results);
      setStatus(`解析完成，共返回 ${results.length} 种解析结果`);
    } catch (error) {
      console.error('Error:', error);
      setStatus(`解析失败：${error.message}`);
    }
  };

  const handleFileSelect = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setStatus('');
    }
  };

  const buildExportText = (result) => {
    const blocks = result.filteredContent || result.content || [];
    const lines = [
      `文件名: ${result.metadata?.filename || '未知文件'}`,
      `解析方式: ${methodLabelMap[result.metadata?.parsing_method] || result.metadata?.parsing_method || '未知'}`,
      `总页数: ${result.metadata?.total_pages || 'N/A'}`,
      `块数量: ${result.summary?.block_count || 0}`,
      `章节块: ${result.summary?.section_count || 0}`,
      `表格块: ${result.summary?.table_block_count || 0}`,
      `文本块: ${result.summary?.text_block_count || 0}`,
      ''
    ];

    blocks.forEach((item, index) => {
      lines.push(`### 块 ${index + 1}`);
      lines.push(`类型: ${item.type}`);
      lines.push(`页码范围: ${item.page_range}`);
      if (item.title) {
        lines.push(`标题: ${item.title}`);
      }
      lines.push(`字数: ${item.word_count || 0}`);
      lines.push(item.content || '');
      lines.push('');
    });

    return lines.join('\n');
  };

  const downloadBlob = (filename, content, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const exportSingleResult = (result, format) => {
    const method = result.metadata?.parsing_method || 'parse';
    const baseName = (result.metadata?.filename || 'parsed_document').replace(/\.pdf$/i, '');
    const exportPayload = {
      ...result,
      content: result.filteredContent || result.content || []
    };

    if (format === 'json') {
      downloadBlob(
        `${baseName}_${method}.json`,
        JSON.stringify(exportPayload, null, 2),
        'application/json;charset=utf-8'
      );
      return;
    }

    downloadBlob(
      `${baseName}_${method}.txt`,
      buildExportText(exportPayload),
      'text/plain;charset=utf-8'
    );
  };

  const exportAllResults = () => {
    const payload = filteredResults.map((result) => ({
      ...result,
      content: result.filteredContent || result.content || []
    }));
    const baseName = file?.name?.replace(/\.pdf$/i, '') || 'parsed_document';
    downloadBlob(
      `${baseName}_comparison_results.json`,
      JSON.stringify(payload, null, 2),
      'application/json;charset=utf-8'
    );
  };

  const renderResultCard = (result) => {
    const method = result.metadata?.parsing_method;
    const displayItems = result.filteredContent || [];

    return (
      <div
        key={method}
        className="border rounded-lg bg-white shadow-sm overflow-hidden"
      >
        <div className="p-4 border-b bg-gray-50">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-gray-800">
                {methodLabelMap[method] || method}
              </h3>
              <div className="text-sm text-gray-600 mt-1">
                <p>总页数：{result.metadata?.total_pages || 'N/A'}</p>
                <p>块数量：{result.summary?.block_count || 0}</p>
                <p>表格块：{result.summary?.table_block_count || 0}</p>
                <p>章节块：{result.summary?.section_count || 0}</p>
              </div>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => exportSingleResult(result, 'json')}
                className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                导出 JSON
              </button>
              <button
                onClick={() => exportSingleResult(result, 'txt')}
                className="px-3 py-1.5 text-sm bg-slate-600 text-white rounded hover:bg-slate-700"
              >
                导出 TXT
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-3 p-4 border-b bg-white">
          <div className="p-3 rounded border bg-gray-50">
            <div className="text-xs text-gray-500">当前显示块数</div>
            <div className="text-xl font-semibold">{displayItems.length}</div>
          </div>
          <div className="p-3 rounded border bg-gray-50">
            <div className="text-xs text-gray-500">总字数</div>
            <div className="text-xl font-semibold">{result.summary?.total_words || 0}</div>
          </div>
          <div className="p-3 rounded border bg-gray-50">
            <div className="text-xs text-gray-500">平均块字数</div>
            <div className="text-xl font-semibold">{result.summary?.average_words_per_block || 0}</div>
          </div>
          <div className="p-3 rounded border bg-gray-50">
            <div className="text-xs text-gray-500">类型分布</div>
            <div className="text-xs text-gray-700 mt-1">
              {Object.entries(result.summary?.content_type_distribution || {}).map(([key, value]) => (
                <div key={key}>
                  {key}: {value}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="max-h-[calc(100vh-360px)] overflow-y-auto p-4 space-y-3">
          {displayItems.length > 0 ? (
            displayItems.map((item, index) => (
              <div key={`${method}-${index}`} className="p-3 border rounded bg-gray-50">
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="text-sm font-medium text-gray-700">
                    {item.label || item.title || `${item.type} 块`}
                  </div>
                  <div className="text-xs text-gray-500">
                    {item.type} | 页码 {item.page_range} | 字数 {item.word_count || 0}
                  </div>
                </div>
                {item.title && (
                  <div className="text-sm font-semibold text-blue-600 mb-2">
                    {item.title}
                  </div>
                )}
                <div className="text-sm text-gray-700 whitespace-pre-wrap break-words">
                  {item.content}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center text-gray-500 py-10">
              当前筛选条件下没有可显示的解析块
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6">检索增强生成工具</h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">文件解析与结果对比</h2>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">选择 PDF 文件</label>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="block w-full border rounded px-3 py-2"
              />
              {file && (
                <p className="text-xs text-gray-500 mt-2">当前文件：{file.name}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">装载工具</label>
              <select
                value={loadingMethod}
                onChange={(event) => setLoadingMethod(event.target.value)}
                className="block w-full p-2 border rounded"
              >
                {loadingMethods.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">主解析方式</label>
              <select
                value={parsingOption}
                onChange={(event) => setParsingOption(event.target.value)}
                className="block w-full p-2 border rounded"
              >
                {parsingMethods.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">附加对比方式</label>
              <div className="space-y-2">
                {parsingMethods.map((method) => (
                  <label key={method.value} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={comparisonMethods.includes(method.value)}
                      onChange={() => handleMethodToggle(method.value)}
                    />
                    <span>{method.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={handleProcess}
              className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
              disabled={!file}
            >
              解析并生成对比
            </button>
          </div>

          <div className="p-4 border rounded-lg bg-white shadow-sm space-y-4">
            <h3 className="text-lg font-semibold">结果筛选</h3>
            <div>
              <label className="block text-sm font-medium mb-1">按类型筛选</label>
              <select
                value={contentTypeFilter}
                onChange={(event) => setContentTypeFilter(event.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="all">全部类型</option>
                <option value="text">文本块</option>
                <option value="table">表格块</option>
                <option value="section">章节块</option>
                <option value="page">分页块</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">按页码筛选</label>
              <input
                type="number"
                min="1"
                value={pageFilter}
                onChange={(event) => setPageFilter(event.target.value)}
                placeholder="如 3"
                className="block w-full p-2 border rounded"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">按关键词筛选</label>
              <input
                type="text"
                value={keywordFilter}
                onChange={(event) => setKeywordFilter(event.target.value)}
                placeholder="输入标题或正文关键词"
                className="block w-full p-2 border rounded"
              />
            </div>

            <button
              onClick={exportAllResults}
              disabled={filteredResults.length === 0}
              className="w-full px-4 py-2 bg-emerald-500 text-white rounded hover:bg-emerald-600 disabled:bg-emerald-300"
            >
              导出全部对比结果
            </button>
          </div>

          {status && (
            <div className={`p-4 rounded-lg ${
              status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
            }`}>
              {status}
            </div>
          )}
        </div>

        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {filteredResults.length > 0 ? (
            <div className="p-4 space-y-4">
              <div className="flex items-center justify-between gap-4 border-b pb-4">
                <div>
                  <h3 className="text-xl font-semibold">解析结果对比</h3>
                  <p className="text-sm text-gray-600 mt-1">
                    已展示 {filteredResults.length} 种解析方式，主方式为 {methodLabelMap[parsingOption]}
                  </p>
                </div>
                <div className="text-sm text-gray-500">
                  当前筛选：{contentTypeFilter === 'all' ? '全部类型' : contentTypeFilter}
                  {pageFilter ? ` | 页码 ${pageFilter}` : ''}
                  {keywordFilter ? ` | 关键词 ${keywordFilter}` : ''}
                </div>
              </div>

              <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
                {filteredResults.map(renderResultCard)}
              </div>
            </div>
          ) : (
            <RandomImage message="上传 PDF 后即可查看多种解析方式的对比结果，并支持筛选与导出" />
          )}
        </div>
      </div>
    </div>
  );
};

export default ParseFile;

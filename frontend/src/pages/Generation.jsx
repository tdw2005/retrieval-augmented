import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MarkdownViewer = ({ markdownText }) => (
  <div className="markdown-container">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownText}</ReactMarkdown>
  </div>
);

const Generation = () => {
  const location = useLocation();
  const [provider, setProvider] = useState('');
  const [modelName, setModelName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [response, setResponse] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [searchFiles, setSearchFiles] = useState([]);
  const [showReasoning, setShowReasoning] = useState(true);
  const [loadModel, setLoadModel] = useState(false);
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [vectorProviders, setVectorProviders] = useState([]);
  const [selectedVectorProvider, setSelectedVectorProvider] = useState('milvus');
  const [topK, setTopK] = useState(3);
  const [threshold, setThreshold] = useState(0);
  const [wordCountThreshold, setWordCountThreshold] = useState(0);
  const [maxContextChars, setMaxContextChars] = useState(6000);
  const [enablePreOptimization, setEnablePreOptimization] = useState(true);
  const [enablePostOptimization, setEnablePostOptimization] = useState(true);
  const [optimizedContext, setOptimizedContext] = useState('');
  const [optimizationInfo, setOptimizationInfo] = useState(null);

  const canUseApiKey = provider === 'openai' || provider === 'deepseek';
  const activeContextLabel = selectedCollection ? '生成时自动检索' : '已有检索结果';

  const modelOptions = useMemo(() => Object.entries(models[provider] || {}), [models, provider]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [modelsResponse, filesResponse, providersResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/generation/models`),
          fetch(`${apiBaseUrl}/search-results`),
          fetch(`${apiBaseUrl}/providers`),
        ]);

        const modelsData = await modelsResponse.json();
        const filesData = await filesResponse.json();
        const providersData = await providersResponse.json();

        setModels(modelsData.models || {});
        setSearchFiles(filesData.files || []);
        setVectorProviders(providersData.providers || []);
      } catch (error) {
        console.error('Error fetching generation data:', error);
        setStatus('获取生成配置失败');
      }
    };

    fetchData();
  }, []);

  useEffect(() => {
    const fetchCollections = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/collections?provider=${selectedVectorProvider}`);
        const data = await response.json();
        setCollections(data.collections || []);
        setSelectedCollection('');
      } catch (error) {
        console.error('Error fetching generation collections:', error);
        setCollections([]);
        setStatus('获取检索集合失败');
      }
    };

    fetchCollections();
  }, [selectedVectorProvider]);

  useEffect(() => {
    const loadSearchResults = async () => {
      if (!selectedFile) {
        setSearchResults([]);
        return;
      }

      try {
        const resultResponse = await fetch(`${apiBaseUrl}/search-results/${selectedFile}`);
        const data = await resultResponse.json();
        setQuery(data.query || '');
        setSearchResults(data.results || []);
      } catch (error) {
        console.error('Error loading search results:', error);
        setStatus('加载检索结果失败');
      }
    };

    loadSearchResults();
  }, [selectedFile]);

  useEffect(() => {
    if (location.state) {
      const { query: searchQuery, results } = location.state;
      if (searchQuery) setQuery(searchQuery);
      if (results) setSearchResults(results);
    }
  }, [location]);

  const handleGenerate = async () => {
    if (!provider || !modelName) {
      setStatus('请选择生成模型');
      return;
    }

    if (!query) {
      setStatus('请输入问题');
      return;
    }

    if (!selectedCollection && searchResults.length === 0) {
      setStatus('请选择集合自动检索，或加载已有检索结果');
      return;
    }

    setIsGenerating(true);
    setStatus('');
    setResponse('');
    setOptimizedContext('');
    setOptimizationInfo(null);

    try {
      const generateResponse = await fetch(`${apiBaseUrl}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          provider,
          model_name: modelName,
          search_results: searchResults,
          load_model: loadModel,
          api_key: apiKey || null,
          show_reasoning: showReasoning,
          collection_id: selectedCollection || null,
          vector_db_provider: selectedVectorProvider,
          top_k: topK,
          threshold,
          word_count_threshold: wordCountThreshold,
          enable_pre_retrieval_optimization: enablePreOptimization,
          enable_post_retrieval_optimization: enablePostOptimization,
          max_context_chars: maxContextChars,
        }),
      });

      if (!generateResponse.ok) {
        throw new Error(`HTTP error! status: ${generateResponse.status}`);
      }

      const data = await generateResponse.json();
      setResponse(data.response || '');
      setOptimizedContext(data.optimized_context || '');
      setOptimizationInfo(data.retrieval_optimization || null);

      if (Array.isArray(data.context)) {
        setSearchResults(data.context);
      }

      setLoadModel(false);
      setStatus(`生成完成，结果已保存至: ${data.saved_filepath}`);
    } catch (error) {
      console.error('Generation error:', error);
      setStatus(`生成失败: ${error.message}`);
    } finally {
      setIsGenerating(false);
      setLoadModel(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6">检索增强生成工具</h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">响应生成</h2>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-4 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">问题</label>
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Enter your question..."
                  className="block w-full p-2 border rounded h-32 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">检索向量库</label>
                <select
                  value={selectedVectorProvider}
                  onChange={(event) => {
                    setSelectedVectorProvider(event.target.value);
                    setSearchResults([]);
                  }}
                  className="block w-full p-2 border rounded"
                >
                  {vectorProviders.map((vectorProvider) => (
                    <option key={vectorProvider.id} value={vectorProvider.id}>
                      {vectorProvider.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">生成时检索集合</label>
                <select
                  value={selectedCollection}
                  onChange={(event) => setSelectedCollection(event.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">不自动检索</option>
                  {collections.map((collection) => (
                    <option key={collection.id} value={collection.id}>
                      {collection.name} ({collection.count} documents)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">已有检索结果</label>
                <select
                  value={selectedFile}
                  onChange={(event) => setSelectedFile(event.target.value)}
                  className="block w-full p-2 border rounded"
                  disabled={Boolean(selectedCollection)}
                >
                  <option value="">Select search results file...</option>
                  {searchFiles.map((file) => (
                    <option key={file.id} value={file.id}>
                      {file.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Top K</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={topK}
                    onChange={(event) => setTopK(Number(event.target.value))}
                    className="block w-full p-2 border rounded"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">上下文长度</label>
                  <input
                    type="number"
                    min="1000"
                    max="20000"
                    step="500"
                    value={maxContextChars}
                    onChange={(event) => setMaxContextChars(Number(event.target.value))}
                    className="block w-full p-2 border rounded"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">相似度阈值 {threshold}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={threshold}
                  onChange={(event) => setThreshold(Number(event.target.value))}
                  className="block w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  最少词数 {wordCountThreshold}
                </label>
                <input
                  type="range"
                  min="0"
                  max="500"
                  step="10"
                  value={wordCountThreshold}
                  onChange={(event) => setWordCountThreshold(Number(event.target.value))}
                  className="block w-full"
                />
              </div>

              <div className="space-y-2">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enablePreOptimization}
                    onChange={(event) => setEnablePreOptimization(event.target.checked)}
                    className="form-checkbox h-4 w-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">启用检索前优化</span>
                </label>
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enablePostOptimization}
                    onChange={(event) => setEnablePostOptimization(event.target.checked)}
                    className="form-checkbox h-4 w-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">启用检索后优化</span>
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">生成模型提供方</label>
                <select
                  value={provider}
                  onChange={(event) => {
                    setProvider(event.target.value);
                    setModelName('');
                  }}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Select provider...</option>
                  {Object.keys(models).map((modelProvider) => (
                    <option key={modelProvider} value={modelProvider}>
                      {modelProvider}
                    </option>
                  ))}
                </select>
              </div>

              {provider && (
                <div>
                  <label className="block text-sm font-medium mb-1">生成模型</label>
                  <select
                    value={modelName}
                    onChange={(event) => {
                      setModelName(event.target.value);
                      setLoadModel(true);
                    }}
                    className="block w-full p-2 border rounded"
                  >
                    <option value="">Select model...</option>
                    {modelOptions.map(([id, name]) => (
                      <option key={id} value={id}>
                        {id === 'deepseek-v3' ? 'DeepSeek V3' : id === 'deepseek-r1' ? 'DeepSeek R1' : name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {canUseApiKey && (
                <div>
                  <label className="block text-sm font-medium mb-1">API Key</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder="Enter your API key..."
                    className="block w-full p-2 border rounded"
                  />
                </div>
              )}

              {provider === 'deepseek' && modelName === 'deepseek-r1' && (
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showReasoning}
                    onChange={(event) => setShowReasoning(event.target.checked)}
                    className="form-checkbox h-4 w-4 text-green-600"
                  />
                  <span className="text-sm font-medium">显示推理过程</span>
                </label>
              )}

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-green-300"
              >
                {isGenerating ? '生成回答中...' : '生成回答'}
              </button>

              {status && (
                <div className={`p-4 rounded-lg ${
                  status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                }`}>
                  {status}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="col-span-8 space-y-6">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold">检索上下文</h3>
              <span className="text-sm text-gray-500">{activeContextLabel}</span>
            </div>

            {optimizationInfo && (
              <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 border rounded bg-gray-50">
                  <div className="font-medium text-gray-600">原始 query</div>
                  <div className="break-words">{optimizationInfo.query_info?.original_query || query}</div>
                </div>
                <div className="p-3 border rounded bg-gray-50">
                  <div className="font-medium text-gray-600">检索 query</div>
                  <div className="break-words">{optimizationInfo.used_query || query}</div>
                </div>
              </div>
            )}

            {searchResults.length > 0 ? (
              <div className="space-y-4 max-h-[300px] overflow-y-auto">
                {searchResults.map((result, index) => (
                  <div key={`${result.metadata?.chunk || index}-${index}`} className="p-4 border rounded bg-gray-50">
                    <div className="flex justify-between items-start mb-2 gap-4">
                      <span className="font-medium text-sm text-gray-500">
                        Match Score: {((result.rerank_score ?? result.score ?? 0) * 100).toFixed(1)}%
                      </span>
                      <div className="text-sm text-gray-500 text-right">
                        <div>Source: {result.metadata?.source || '-'}</div>
                        <div>Page: {result.metadata?.page || '-'}</div>
                      </div>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{result.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <RandomImage message="Search context will appear here" />
            )}
          </div>

          {optimizedContext && (
            <div className="p-4 border rounded-lg bg-white shadow-sm">
              <h3 className="text-xl font-semibold mb-4">优化后的上下文</h3>
              <pre className="p-4 border rounded bg-gray-50 whitespace-pre-wrap text-sm max-h-[260px] overflow-y-auto">
                {optimizedContext}
              </pre>
            </div>
          )}

          {response && (
            <div className="p-4 border rounded-lg bg-white shadow-sm">
              <h3 className="text-xl font-semibold mb-4">生成的回答</h3>
              <div className="p-4 border rounded bg-gray-50">
                <MarkdownViewer markdownText={response} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Generation;

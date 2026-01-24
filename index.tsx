
import React, { useState, useEffect, useMemo } from 'react';
import { 
  AlertTriangle, 
  Mail, 
  BarChart3, 
  TrendingDown, 
  MessageSquare, 
  Search, 
  ShieldAlert, 
  Clock, 
  Sparkles,
  RefreshCw,
  Loader2,
  X,
  ExternalLink,
  Hospital
} from 'lucide-react';
import { 
  ResponsiveContainer,
  AreaChart,
  Area,
  Tooltip
} from 'recharts';

// --- 类型定义 ---
type Severity = "low" | "medium" | "high";

interface OpinionItem {
  id: string;           
  hospital: string;
  title: string;
  source: string;
  content: string;
  reason: string;
  severity: Severity;
  score: number;        
  url?: string;
  status: "active" | "dismissed";
  dismissed_at?: string;
  createdAt: string;
}

export default function OpinionDashboard() {
  const [opinions, setOpinions] = useState<OpinionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [aiAnalysis, setAiAnalysis] = useState<string>('');
  const [analyzing, setAnalyzing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  // 详情与分析抽屉状态
  const [selectedItem, setSelectedItem] = useState<OpinionItem | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [insightText, setInsightText] = useState('');

  // 1. 获取基础数据
  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/opinions');
      if (!response.ok) throw new Error('无法连接到后端接口');
      const data = await response.json();
      setOpinions(data);
      
      if (data.length > 0) {
        requestGlobalSummary(data);
      }
    } catch (err) {
      console.error("Fetch error:", err);
      setError("无法连接后端服务，请检查 API 接口是否正常。");
    } finally {
      setIsLoading(false);
    }
  };

  // 2. 全局 AI 简报
  const requestGlobalSummary = async (items: OpinionItem[]) => {
    setAnalyzing(true);
    try {
      const res = await fetch('/api/ai/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opinions: items })
      });
      const result = await res.json();
      setAiAnalysis(result.text || "总结生成失败");
    } catch (err) {
      setAiAnalysis("AI 分析服务暂时不可用");
    } finally {
      setAnalyzing(false);
    }
  };

  // 3. 穿透分析：请求单条舆情洞察
  const handleInsight = async (item: OpinionItem) => {
    setSelectedItem(item);
    setInsightLoading(true);
    setInsightText('');
    try {
      const res = await fetch('/api/ai/insight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opinion: item })
      });
      const result = await res.json();
      setInsightText(result.text || "未能生成深度洞察");
    } catch (err) {
      setInsightText("无法调用 AI 洞察服务。");
    } finally {
      setInsightLoading(false);
    }
  };

  // 4. 搜索功能
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchTerm.trim()) {
      fetchData();
      return;
    }
    
    setIsLoading(true);
    try {
      const res = await fetch(`/api/search?query=${encodeURIComponent(searchTerm)}`);
      const data = await res.json();
      setOpinions(data);
    } catch (err) {
      setError("搜索接口响应异常。");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const stats = useMemo(() => {
    const highRisk = opinions.filter(o => o.severity === 'high').length;
    const avgScore = opinions.length ? Math.round(opinions.reduce((acc, curr) => acc + (curr.score || 0), 0) / opinions.length) : 0;
    return { highRisk, avgScore, total: opinions.length };
  }, [opinions]);

  const getSeverityColor = (s: Severity) => {
    switch(s) {
      case 'high': return 'bg-red-500 shadow-lg shadow-red-500/40';
      case 'medium': return 'bg-amber-500 shadow-lg shadow-amber-500/40';
      case 'low': return 'bg-emerald-500 shadow-lg shadow-emerald-500/40';
      default: return 'bg-slate-500';
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-500">
        <Loader2 className="w-12 h-12 animate-spin text-indigo-500 mb-4" />
        <div className="text-sm font-medium tracking-widest uppercase animate-pulse">正在解析最新舆情态势...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500/40">
      {/* Navbar */}
      <nav className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="bg-indigo-600 p-2 rounded-xl">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight">舆情监控指挥大屏</h1>
              <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase font-bold tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                系统实时在线
              </div>
            </div>
          </div>
          
          <form onSubmit={handleSearch} className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="自然语言搜索 (如: 态度恶劣的投诉)" 
                className="bg-slate-800 border-slate-700/50 rounded-xl py-2 pl-10 pr-4 text-sm focus:ring-2 ring-indigo-500 w-80 transition-all border outline-none"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button 
              onClick={(e) => { e.preventDefault(); fetchData(); }}
              className="p-2 hover:bg-slate-800 rounded-xl transition-all border border-slate-700/50"
            >
              <RefreshCw className="w-4 h-4 text-slate-400" />
            </button>
          </form>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8 grid grid-cols-12 gap-8">
        {error && (
          <div className="col-span-12 bg-red-900/20 border border-red-500/30 p-4 rounded-2xl text-red-200 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        )}

        {/* Sidebar */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-900/40 border border-slate-800/50 p-6 rounded-3xl group">
              <p className="text-[10px] font-black text-red-500 uppercase tracking-widest mb-1">高危预警</p>
              <p className="text-4xl font-black tabular-nums">{stats.highRisk}</p>
            </div>
            <div className="bg-slate-900/40 border border-slate-800/50 p-6 rounded-3xl group">
              <p className="text-[10px] font-black text-indigo-400 uppercase tracking-widest mb-1">平均风险指数</p>
              <p className="text-4xl font-black tabular-nums">{stats.avgScore}</p>
            </div>
          </div>

          <div className="bg-slate-900/40 border border-slate-800/50 p-8 rounded-3xl">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-8 flex items-center gap-2">
              <BarChart3 className="w-4 h-4" /> 24H 压力趋势
            </h2>
            <div className="h-40 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={[
                  {n: '08:00', v: 45}, {n: '12:00', v: 75}, {n: '16:00', v: 50}, {n: 'Now', v: stats.avgScore}
                ]}>
                  <Area type="monotone" dataKey="v" stroke="#6366f1" fill="#6366f1" fillOpacity={0.1} strokeWidth={3} />
                  <Tooltip contentStyle={{backgroundColor: '#0f172a', border: 'none', borderRadius: '12px'}} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-indigo-600/5 border border-indigo-500/20 p-8 rounded-3xl">
            <h2 className="text-indigo-400 text-xs font-black uppercase tracking-widest flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4" /> AI 舆情简报
            </h2>
            <div className="text-sm text-slate-400 leading-relaxed font-medium">
              {analyzing ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-2 bg-slate-800 rounded w-full" />
                  <div className="h-2 bg-slate-800 rounded w-5/6" />
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: aiAnalysis.replace(/\n/g, '<br/>') }} />
              )}
            </div>
          </div>
        </div>

        {/* List Content */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-lg font-bold">舆情列表 ({opinions.length})</h2>
          </div>

          <div className="grid gap-4">
            {opinions.map((item) => (
              <div 
                key={item.id} 
                className="bg-slate-900/30 hover:bg-slate-900/50 border border-slate-800/50 p-6 rounded-3xl transition-all group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="flex items-center gap-3">
                    <span className={`w-2 h-2 rounded-full ${getSeverityColor(item.severity)}`} />
                    <h3 className="font-bold text-lg group-hover:text-white transition-colors">
                      {item.title}
                    </h3>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest bg-slate-800 px-2 py-1 rounded">
                      {item.hospital}
                    </span>
                  </div>
                </div>

                <div className="bg-red-500/5 border border-red-500/10 p-3 rounded-xl mb-4 text-xs flex gap-2">
                  <span className="text-red-400 font-bold whitespace-nowrap">警示理由:</span>
                  <span className="text-slate-400">{item.reason}</span>
                </div>

                <p className="text-sm text-slate-400 line-clamp-2 mb-6 group-hover:text-slate-300">
                  {item.content}
                </p>

                <div className="flex items-center justify-between pt-4 border-t border-slate-800/50">
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {item.createdAt}</span>
                    <span>来源: {item.source}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => handleInsight(item)}
                      className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all"
                    >
                      穿透分析
                    </button>
                    {item.url && (
                      <a href={item.url} target="_blank" className="p-2 hover:bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-all border border-slate-800">
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Side Drawer */}
      {selectedItem && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSelectedItem(null)} />
          <div className="relative w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-300">
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 sticky top-0 z-10">
              <div className="flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                <h2 className="text-lg font-bold">AI 深度洞察</h2>
              </div>
              <button onClick={() => setSelectedItem(null)} className="p-2 hover:bg-slate-800 rounded-xl">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-8 space-y-8">
              <section className="space-y-4">
                <div className={`inline-flex px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${getSeverityColor(selectedItem.severity)}`}>
                  {selectedItem.severity} RISK
                </div>
                <h1 className="text-2xl font-black leading-tight text-white">{selectedItem.title}</h1>
                <p className="text-sm text-slate-500">
                  {selectedItem.hospital} • {selectedItem.createdAt}
                </p>
              </section>

              <div className="bg-slate-800/40 p-6 rounded-2xl border border-slate-700/30">
                <p className="text-sm text-slate-300 italic leading-relaxed">"{selectedItem.content}"</p>
              </div>

              <section className="space-y-4">
                <h3 className="text-xs font-black text-indigo-400 uppercase tracking-widest flex items-center gap-2">
                  <Sparkles className="w-4 h-4" /> 风险评估与应对方案
                </h3>
                {insightLoading ? (
                  <div className="flex flex-col items-center py-12 gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                    <p className="text-xs text-slate-500 animate-pulse uppercase font-bold tracking-widest">正在生成专家建议...</p>
                  </div>
                ) : (
                  <div className="text-sm text-slate-300 leading-loose prose prose-invert">
                    <div dangerouslySetInnerHTML={{ __html: insightText.replace(/\n/g, '<br/>') }} />
                  </div>
                )}
              </section>
            </div>

            <div className="p-6 border-t border-slate-800 bg-slate-900">
              <button 
                onClick={() => setSelectedItem(null)}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-black text-sm transition-all"
              >
                已处理/关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

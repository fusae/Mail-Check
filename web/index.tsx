
import "./index.css";
import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  ClipboardList,
  Clock,
  ExternalLink,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Link as LinkIcon,
  X,
  Loader2,
} from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip } from "recharts";

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

const severityMeta = {
  high: {
    label: "高危",
    pill: "bg-red-500/20 text-red-200 border-red-500/40",
    glow: "shadow-[0_0_25px_rgba(239,68,68,0.35)]",
    score: 0.92,
  },
  medium: {
    label: "中危",
    pill: "bg-orange-500/20 text-orange-200 border-orange-500/40",
    glow: "shadow-[0_0_20px_rgba(249,115,22,0.3)]",
    score: 0.6,
  },
  low: {
    label: "低危",
    pill: "bg-emerald-500/20 text-emerald-200 border-emerald-500/40",
    glow: "shadow-[0_0_18px_rgba(16,185,129,0.25)]",
    score: 0.35,
  },
};

const normalizeSeverity = (value?: Severity | null) => {
  if (value === "high" || value === "medium" || value === "low") return value;
  return "low";
};

const formatTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const OpinionDashboard = () => {
  const [opinions, setOpinions] = useState<OpinionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [summaryAt, setSummaryAt] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<OpinionItem | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [insightText, setInsightText] = useState("");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [hospitalFilter, setHospitalFilter] = useState("all");
  const [showDismissed, setShowDismissed] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/opinions?status=all");
      if (!response.ok) throw new Error("无法连接到后端接口");
      const data = await response.json();
      setOpinions(data);
      if (data.length > 0) {
        requestGlobalSummary(data);
      } else {
        setAiAnalysis("暂无负面舆情数据。");
      }
    } catch (err) {
      setError("无法连接后端服务，请检查 API 接口是否正常。");
    } finally {
      setIsLoading(false);
    }
  };

  const requestGlobalSummary = async (items: OpinionItem[]) => {
    setAnalyzing(true);
    try {
      const res = await fetch("/api/ai/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opinions: items }),
      });
      const result = await res.json();
      setAiAnalysis(result.text || "总结生成失败");
      setSummaryAt(new Date().toLocaleString("zh-CN"));
    } catch (err) {
      setAiAnalysis("AI 分析服务暂时不可用");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleInsight = async (item: OpinionItem) => {
    setSelectedItem(item);
    setInsightLoading(true);
    setInsightText("");
    try {
      const res = await fetch("/api/ai/insight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opinion: item }),
      });
      const result = await res.json();
      setInsightText(result.text || "未能生成深度洞察");
    } catch (err) {
      setInsightText("无法调用 AI 洞察服务。");
    } finally {
      setInsightLoading(false);
    }
  };

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
    const active = opinions.filter((o) => o.status !== "dismissed");
    const highRisk = active.filter((o) => o.severity === "high").length;
    const dismissed = opinions.filter((o) => o.status === "dismissed").length;
    const avgScore = active.length
      ? Math.round(
          (active.reduce((acc, curr) => acc + (curr.score || severityMeta[normalizeSeverity(curr.severity)].score), 0) /
            active.length) * 100
        )
      : 0;
    return { highRisk, dismissed, total: active.length, avgScore };
  }, [opinions]);

  const trendData = useMemo(() => {
    const items = [...opinions]
      .filter((o) => o.status !== "dismissed")
      .slice(0, 12)
      .reverse();
    return items.map((item) => ({
      label: formatTime(item.createdAt),
      value: Math.round((item.score || severityMeta[normalizeSeverity(item.severity)].score) * 100),
    }));
  }, [opinions]);

  const hospitalOptions = useMemo(() => {
    const set = new Set(opinions.map((o) => o.hospital).filter(Boolean));
    return ["all", ...Array.from(set)];
  }, [opinions]);

  const filteredOpinions = useMemo(() => {
    return opinions.filter((item) => {
      if (!showDismissed && item.status === "dismissed") return false;
      if (severityFilter !== "all" && item.severity !== severityFilter) return false;
      if (hospitalFilter !== "all" && item.hospital !== hospitalFilter) return false;
      return true;
    });
  }, [opinions, severityFilter, hospitalFilter, showDismissed]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.15),_transparent_55%),radial-gradient(circle_at_20%_30%,_rgba(249,115,22,0.08),_transparent_45%),radial-gradient(circle_at_80%_20%,_rgba(16,185,129,0.12),_transparent_40%)]" />

      <header className="relative z-10 border-b border-slate-800/70 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-4">
            <div className="rounded-2xl bg-indigo-500/20 p-3 shadow-[0_0_30px_rgba(99,102,241,0.35)]">
              <ShieldAlert className="h-6 w-6 text-indigo-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold">
                Crisis Command Center
              </p>
              <h1 className="font-display text-2xl font-bold tracking-tight">舆情监控指挥中心</h1>
            </div>
          </div>

          <form onSubmit={handleSearch} className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="自然语言搜索：比如“产品质量投诉”"
                className="w-80 rounded-2xl border border-slate-800/60 bg-slate-900/60 py-2.5 pl-10 pr-4 text-sm text-slate-200 outline-none transition focus:border-indigo-500/70"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-indigo-200"
            >
              搜索
            </button>
            <button
              type="button"
              onClick={fetchData}
              className="rounded-2xl border border-slate-800/70 p-2 text-slate-400 transition hover:bg-slate-900/70"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </form>
        </div>
      </header>

      <main className="relative z-10 mx-auto grid max-w-7xl grid-cols-12 gap-6 px-6 py-8">
        {error && (
          <div className="col-span-12 flex items-center gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            {error}
          </div>
        )}

        <section className="col-span-12 lg:col-span-4 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-3xl border border-red-500/30 bg-red-500/10 p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-red-300">高危舆情</p>
              <p className="font-display text-3xl font-bold">{stats.highRisk}</p>
            </div>
            <div className="rounded-3xl border border-indigo-500/30 bg-indigo-500/10 p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-200">平均风险指数</p>
              <p className="font-display text-3xl font-bold">{stats.avgScore}</p>
            </div>
            <div className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-200">当前监控</p>
              <p className="font-display text-3xl font-bold">{stats.total}</p>
            </div>
            <div className="rounded-3xl border border-slate-700/40 bg-slate-900/60 p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">已误报</p>
              <p className="font-display text-3xl font-bold text-slate-200">{stats.dismissed}</p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/70 bg-slate-900/50 p-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">压力走势</h2>
              <BarChart3 className="h-4 w-4 text-slate-500" />
            </div>
            <div className="mt-6 h-40">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <Area dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#trendGradient)" />
                  <Tooltip
                    contentStyle={{
                      background: "#0f172a",
                      border: "1px solid #1f2937",
                      borderRadius: "12px",
                      color: "#e2e8f0",
                    }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-3xl border border-indigo-500/30 bg-indigo-500/10 p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-indigo-200">AI 舆情简报</h2>
              <div className="flex items-center gap-2 text-[10px] text-indigo-200">
                {summaryAt ? `更新于 ${summaryAt}` : "未生成"}
                <button
                  type="button"
                  onClick={() => requestGlobalSummary(opinions)}
                  className="rounded-full border border-indigo-400/40 px-2 py-1 text-[10px] uppercase tracking-wider"
                >
                  刷新简报
                </button>
              </div>
            </div>
            <div className="mt-4 text-sm text-slate-200/80 leading-relaxed">
              {analyzing ? (
                <div className="space-y-2">
                  <div className="h-2 w-full animate-pulse rounded-full bg-slate-700" />
                  <div className="h-2 w-5/6 animate-pulse rounded-full bg-slate-700" />
                  <div className="h-2 w-4/6 animate-pulse rounded-full bg-slate-700" />
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: aiAnalysis.replace(/\n/g, "<br/>") }} />
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/70 bg-slate-900/40 p-6">
            <div className="flex items-center gap-3 text-xs uppercase tracking-widest text-slate-400">
              <ClipboardList className="h-4 w-4" /> 值班提醒
            </div>
            <p className="mt-4 text-sm text-slate-300">
              高危舆情将触发红色预警灯，请优先查看“穿透分析”并结合 AI 建议进行处置。
            </p>
          </div>
        </section>

        <section className="col-span-12 lg:col-span-8 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="font-display text-xl font-semibold">实时舆情列表</h2>
            <span className="text-xs text-slate-500">{filteredOpinions.length} 条记录</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-800/70 bg-slate-900/40 px-4 py-3 text-xs text-slate-400">
            <Filter className="h-4 w-4 text-slate-500" />
            <div className="flex items-center gap-2">
              <span>严重度</span>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
                className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              >
                <option value="all">全部</option>
                <option value="high">高危</option>
                <option value="medium">中危</option>
                <option value="low">低危</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span>医院</span>
              <select
                value={hospitalFilter}
                onChange={(e) => setHospitalFilter(e.target.value)}
                className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200"
              >
                {hospitalOptions.map((h) => (
                  <option key={h} value={h}>
                    {h === "all" ? "全部医院" : h}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={showDismissed}
                onChange={(e) => setShowDismissed(e.target.checked)}
                className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-indigo-500"
              />
              显示误报
            </label>
          </div>

          {isLoading ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-800/70 bg-slate-900/40">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
              <p className="mt-4 text-xs uppercase tracking-widest text-slate-500">加载中</p>
            </div>
          ) : filteredOpinions.length === 0 ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-800/70 bg-slate-900/40 text-slate-500">
              暂无舆情数据
            </div>
          ) : (
            <div className="space-y-4">
              {filteredOpinions.map((item) => {
                const meta = severityMeta[normalizeSeverity(item.severity)];
                const scoreValue = Math.round((item.score || meta.score) * 100);
                return (
                  <article
                    key={item.id}
                    className={`group rounded-3xl border border-slate-800/70 bg-slate-900/45 p-6 backdrop-blur transition hover:border-indigo-500/50 ${meta.glow}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-3">
                          <span className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-widest ${meta.pill}`}>
                            {meta.label}
                          </span>
                          {item.status === "dismissed" && (
                            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[10px] uppercase tracking-wider text-emerald-200">
                              已误报
                            </span>
                          )}
                        </div>
                        <h3 className="mt-3 text-lg font-semibold text-white">{item.title}</h3>
                        <p className="mt-2 text-sm text-slate-400">
                          {item.hospital} · {item.source}
                        </p>
                      </div>
                      <button
                        className="flex items-center gap-2 rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-200 transition hover:bg-indigo-500/20"
                        onClick={() => handleInsight(item)}
                      >
                        穿透分析
                        <ArrowUpRight className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-4 flex items-center gap-3 text-xs text-slate-400">
                      <span className="uppercase tracking-widest text-slate-500">风险分值</span>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 via-rose-500 to-amber-400" style={{ width: `${scoreValue}%` }} />
                      </div>
                      <span className="min-w-[40px] text-right text-slate-200">{scoreValue}</span>
                    </div>

                    <div className="mt-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 text-sm text-slate-300">
                      <span className="mr-2 text-xs uppercase tracking-wider text-rose-300">警示理由</span>
                      {item.reason}
                    </div>

                    <p className="mt-4 text-sm text-slate-400 leading-relaxed">
                      {((item.content || "").length > 220)
                        ? `${(item.content || "").slice(0, 220)}...`
                        : (item.content || "")}
                    </p>

                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        {formatTime(item.createdAt)}
                      </div>
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 rounded-full border border-slate-700/60 px-3 py-1 text-slate-300 transition hover:border-indigo-400/60 hover:text-indigo-200"
                        >
                          原文链接
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </main>

      {selectedItem && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSelectedItem(null)} />
          <aside className="relative h-full w-full max-w-xl border-l border-slate-800/80 bg-slate-900/95 p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-widest text-slate-500">穿透分析</p>
                <h2 className="text-xl font-semibold">{selectedItem.title}</h2>
              </div>
              <button onClick={() => setSelectedItem(null)} className="rounded-full p-2 text-slate-400 hover:bg-slate-800">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-6 space-y-5 text-sm text-slate-300">
              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                <p className="text-xs uppercase tracking-widest text-slate-500">舆情信息</p>
                <p className="mt-2 text-base font-semibold text-white">{selectedItem.hospital}</p>
                <p className="mt-1 text-xs text-slate-400">{selectedItem.source} · {formatTime(selectedItem.createdAt)}</p>
                {selectedItem.url && (
                  <a
                    href={selectedItem.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-700/60 px-3 py-1 text-xs text-slate-300 transition hover:border-indigo-400/60 hover:text-indigo-200"
                  >
                    <LinkIcon className="h-4 w-4" /> 原文链接
                  </a>
                )}
              </div>

              <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                <p className="text-xs uppercase tracking-widest text-slate-500">舆情内容</p>
                <p className="mt-2 leading-relaxed">{selectedItem.content}</p>
              </div>

              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
                <p className="text-xs uppercase tracking-widest text-rose-200">AI 判断理由</p>
                <p className="mt-2 text-sm text-rose-100">{selectedItem.reason || "暂无说明"}</p>
              </div>

              <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 p-4">
                <p className="flex items-center gap-2 text-xs uppercase tracking-widest text-indigo-200">
                  <Sparkles className="h-4 w-4" /> AI 洞察
                </p>
                <div className="mt-3">
                  {insightLoading ? (
                    <div className="flex items-center gap-3 text-slate-400">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      正在生成建议...
                    </div>
                  ) : (
                    <div dangerouslySetInnerHTML={{ __html: insightText.replace(/\n/g, "<br/>") }} />
                  )}
                </div>
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
};

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<OpinionDashboard />);
}

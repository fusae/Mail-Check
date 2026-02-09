
import "./index.css";
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
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
  Calendar,
  TrendingUp,
  PieChart as PieChartIcon,
  Activity,
  Download,
  FileText,
  ChevronDown,
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Severity = "low" | "medium" | "high";

interface OpinionItem {
  id: string;
  event_id?: number | null;
  event_total?: number | null;
  is_duplicate?: boolean;
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
  content_truncated?: boolean;
  createdAt: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.trim() || "";
const apiFetch = (path: string, options?: RequestInit) => {
  if (!API_BASE) {
    return Promise.reject(new Error("未配置 VITE_API_BASE（前端无法找到后端API地址）"));
  }
  return fetch(`${API_BASE}${path}`, options);
};

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

const pad2 = (value: number) => `${value}`.padStart(2, "0");

const parseLocalDateTime = (value: string) => {
  const match = value.match(/(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return null;
  const [, y, m, d, hh, mm, ss] = match;
  return new Date(
    Number(y),
    Number(m) - 1,
    Number(d),
    Number(hh),
    Number(mm),
    Number(ss || "0")
  );
};

const getLocalParts = (value: string | Date) => {
  if (typeof value === "string") {
    const match = value.match(/(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
    if (match) {
      return {
        year: match[1],
        month: match[2],
        day: match[3],
        hour: match[4],
        minute: match[5],
      };
    }
    const parsed = parseLocalDateTime(value);
    if (!parsed) return null;
    return {
      year: `${parsed.getFullYear()}`,
      month: pad2(parsed.getMonth() + 1),
      day: pad2(parsed.getDate()),
      hour: pad2(parsed.getHours()),
      minute: pad2(parsed.getMinutes()),
    };
  }

  if (Number.isNaN(value.getTime())) return null;
  return {
    year: `${value.getFullYear()}`,
    month: pad2(value.getMonth() + 1),
    day: pad2(value.getDate()),
    hour: pad2(value.getHours()),
    minute: pad2(value.getMinutes()),
  };
};

const formatLocalDate = (date: Date | string) => {
  const parts = getLocalParts(date);
  if (!parts) return "";
  return `${parts.year}-${parts.month}-${parts.day}`;
};

const formatLocalMonthDay = (date: Date | string) => {
  const parts = getLocalParts(date);
  if (!parts) return "";
  return `${parts.month}-${parts.day}`;
};

const formatLocalHour = (date: Date | string) => {
  const parts = getLocalParts(date);
  if (!parts) return "";
  return `${parts.hour}:00`;
};

const parseDateInput = (value: string) => {
  if (!value) return null;
  const match = value.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const [, y, m, d] = match;
  return new Date(Number(y), Number(m) - 1, Number(d));
};

const parseChinaDate = (value: string) => {
  if (!value) return null;
  return new Date(`${value}T00:00:00+08:00`);
};

const formatTime = (value: string | Date) => {
  const parts = getLocalParts(value);
  if (!parts) {
    return typeof value === "string" ? value : "";
  }
  return `${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
};

const formatDateInput = (date: Date) => {
  return formatLocalDate(date);
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
  const [insightCache, setInsightCache] = useState<Record<string, string>>({});
  const [leftColHeight, setLeftColHeight] = useState<number | null>(null);
  const leftColRef = useRef<HTMLDivElement | null>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [hospitalFilter, setHospitalFilter] = useState("all");
  const [showDismissed, setShowDismissed] = useState(false);
  const [groupByEvent, setGroupByEvent] = useState(true);
  const [timeRange, setTimeRange] = useState<"24h" | "7d" | "30d">("7d");
  const [trendMode, setTrendMode] = useState<"count" | "score">("count");
  const [tooltipContent, setTooltipContent] = useState<{ title: string; content: string; position: { x: number; y: number } } | null>(null);
  const [statsOverride, setStatsOverride] = useState<{ total: number; dismissed: number; highRisk: number } | null>(null);
  const [statsDetail, setStatsDetail] = useState<{
    severity: { high: number; medium: number; low: number };
    hospitals: Array<{ hospital: string; high: number; medium: number; low: number; total: number }>;
    sources: Array<{ source: string; count: number }>;
    hospitalList: string[];
    avgScore?: number;
  } | null>(null);
  const [trendOverride, setTrendOverride] = useState<Array<{ label: string; count: number; avgScore: number }> | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportDateRange, setExportDateRange] = useState<{ start: string; end: string }>({
    start: "",
    end: ""
  });
  const [exportHospital, setExportHospital] = useState("all");
  const [isExporting, setIsExporting] = useState(false);
  const [exportReportOpen, setExportReportOpen] = useState(false);
  const [reportDateRange, setReportDateRange] = useState<{ start: string; end: string }>({
    start: "",
    end: ""
  });
  const [reportHospital, setReportHospital] = useState("all");
  const [reportFormat, setReportFormat] = useState<"markdown" | "word">("word");
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [suppressModalOpen, setSuppressModalOpen] = useState(false);
  const [suppressKeywords, setSuppressKeywords] = useState<string[]>([]);
  const [newKeyword, setNewKeyword] = useState("");
  const [suppressLoading, setSuppressLoading] = useState(false);
  const [suppressSaving, setSuppressSaving] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiFetch("/api/opinions?status=all&compact=1&preview=240");
      if (!response.ok) throw new Error("无法连接到后端接口");
      const data = await response.json();
      setOpinions(data);
      if (data.length > 0) {
        if (!aiAnalysis) {
          setAiAnalysis("未生成，点击右侧“刷新简报”获取。");
        }
      } else {
        setAiAnalysis("暂无负面舆情数据。");
      }
      fetchStats();
    } catch (err) {
      setError("无法连接后端服务，请检查 API 接口是否正常。");
    } finally {
      setIsLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const resp = await apiFetch(`/api/stats?range=${timeRange}`);
      if (!resp.ok) return;
      const data = await resp.json();
      setStatsOverride({
        total: data.active_total ?? 0,
        dismissed: data.dismissed_total ?? 0,
        highRisk: data.high_total ?? 0,
      });
      if (data.severity || data.hospitals || data.sources || data.hospital_list) {
        setStatsDetail({
          severity: {
            high: data.severity?.high ?? data.high_total ?? 0,
            medium: data.severity?.medium ?? 0,
            low: data.severity?.low ?? 0,
          },
          hospitals: Array.isArray(data.hospitals) ? data.hospitals : [],
          sources: Array.isArray(data.sources) ? data.sources : [],
          hospitalList: Array.isArray(data.hospital_list) ? data.hospital_list : [],
          avgScore: data.avg_score ?? undefined,
        });
      }
    } catch (err) {
      // ignore
    }
  };

  const fetchTrend = async () => {
    try {
      const resp = await apiFetch(`/api/stats/trend?range=${timeRange}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (Array.isArray(data.data)) {
        setTrendOverride(data.data);
      }
    } catch (err) {
      // ignore
    }
  };

  const requestGlobalSummary = async (items: OpinionItem[]) => {
    setAnalyzing(true);
    try {
      const res = await apiFetch("/api/ai/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opinions: items }),
      });
      const result = await res.json();
      setAiAnalysis(result.text || "总结生成失败");
      setSummaryAt(formatTime(new Date()));
    } catch (err) {
      setAiAnalysis("AI 分析服务暂时不可用");
    } finally {
      setAnalyzing(false);
    }
  };

  const ensureFullOpinion = async (item: OpinionItem) => {
    if (!item.content_truncated) return item;
    try {
      const res = await apiFetch(`/api/opinions/${item.id}`);
      if (!res.ok) return item;
      const full = await res.json();
      setOpinions((prev) => prev.map((o) => (o.id === item.id ? { ...o, ...full } : o)));
      setSelectedItem(full);
      return full;
    } catch (err) {
      return item;
    }
  };

  const handleInsight = async (item: OpinionItem) => {
    setSelectedItem(item);
    const cached = insightCache[item.id];
    if (cached) {
      setInsightText(cached);
      setInsightLoading(false);
      return;
    }

    setInsightLoading(true);
    setInsightText("");
    try {
      const fullItem = await ensureFullOpinion(item);
      const res = await apiFetch("/api/ai/insight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opinion: fullItem }),
      });
      const result = await res.json();
      const text = result.text || "未能生成深度洞察";
      setInsightText(text);
      setInsightCache((prev) => ({ ...prev, [item.id]: text }));
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
      const res = await apiFetch(`/api/search?query=${encodeURIComponent(searchTerm)}&compact=1&preview=240`);
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

  useEffect(() => {
    fetchTrend();
    fetchStats();
  }, [timeRange]);

  useLayoutEffect(() => {
    const leftEl = leftColRef.current;
    if (!leftEl) return;
    const update = () => setLeftColHeight(leftEl.offsetHeight);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(leftEl);
    return () => observer.disconnect();
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
    if (statsOverride) {
      return {
        highRisk: statsOverride.highRisk,
        dismissed: statsOverride.dismissed,
        total: statsOverride.total,
        avgScore: statsDetail?.avgScore ?? avgScore,
      };
    }
    return { highRisk, dismissed, total: active.length, avgScore };
  }, [opinions, statsOverride, statsDetail]);

  const hospitalOptions = useMemo(() => {
    if (statsDetail?.hospitalList?.length) {
      return ["all", ...statsDetail.hospitalList.filter(Boolean)];
    }
    const set = new Set(opinions.map((o) => o.hospital).filter(Boolean));
    return ["all", ...Array.from(set)];
  }, [opinions, statsDetail]);

  const filteredOpinions = useMemo(() => {
    return opinions.filter((item) => {
      if (!showDismissed && item.status === "dismissed") return false;
      if (severityFilter !== "all" && item.severity !== severityFilter) return false;
      if (hospitalFilter !== "all" && item.hospital !== hospitalFilter) return false;
      return true;
    });
  }, [opinions, severityFilter, hospitalFilter, showDismissed]);

  const displayOpinions = useMemo(() => {
    if (!groupByEvent) return filteredOpinions;

    // Keep the most recent item per event. If no event_id, fall back to sentiment id.
    const keyOf = (item: OpinionItem) => (item.event_id ? `e:${item.event_id}` : `s:${item.id}`);
    const counts = new Map<string, number>();
    for (const item of filteredOpinions) {
      const k = keyOf(item);
      counts.set(k, (counts.get(k) || 0) + 1);
    }

    const seen = new Set<string>();
    const out: OpinionItem[] = [];
    for (const item of filteredOpinions) {
      const k = keyOf(item);
      if (seen.has(k)) continue;
      seen.add(k);
      const inferredTotal = counts.get(k) || 1;
      const mergedTotal = Number(item.event_total || 0) > 0 ? item.event_total : inferredTotal;
      out.push({ ...item, event_total: mergedTotal });
    }
    return out;
  }, [filteredOpinions, groupByEvent]);

  const listStatsLabel = useMemo(() => {
    if (!groupByEvent) {
      return `${filteredOpinions.length} 条记录${statsOverride ? ` / 共 ${statsOverride.total} 条` : ""}`;
    }
    return `${displayOpinions.length} 个事件 / ${filteredOpinions.length} 条舆情${statsOverride ? ` / 共 ${statsOverride.total} 条` : ""}`;
  }, [groupByEvent, displayOpinions.length, filteredOpinions.length, statsOverride]);

  const activeOpinions = useMemo(() => {
    return opinions.filter((o) => o.status !== "dismissed");
  }, [opinions]);

  const trendData = useMemo(() => {
    if (trendOverride) return trendOverride;
    const now = new Date();
    const cutoffTime = new Date(now.getTime() - getTimeRangeMs(timeRange));

    const grouped = new Map<string, { count: number; totalScore: number }>();

    activeOpinions
      .filter((o) => {
        const parsed = typeof o.createdAt === "string" ? parseLocalDateTime(o.createdAt) : null;
        return parsed ? parsed >= cutoffTime : false;
      })
      .sort((a, b) => {
        const aTime = typeof a.createdAt === "string" ? parseLocalDateTime(a.createdAt)?.getTime() ?? 0 : 0;
        const bTime = typeof b.createdAt === "string" ? parseLocalDateTime(b.createdAt)?.getTime() ?? 0 : 0;
        return aTime - bTime;
      })
      .forEach((item) => {
        const date = typeof item.createdAt === "string" ? parseLocalDateTime(item.createdAt) : null;
        if (!date) return;
        let key: string;

        if (timeRange === "24h") {
          key = formatLocalHour(date);
        } else if (timeRange === "7d") {
          key = formatLocalMonthDay(date);
        } else {
          key = formatLocalMonthDay(date);
        }

        if (!grouped.has(key)) {
          grouped.set(key, { count: 0, totalScore: 0 });
        }
        const data = grouped.get(key)!;
        data.count += 1;
        data.totalScore += item.score || severityMeta[normalizeSeverity(item.severity)].score;
      });

    return Array.from(grouped.entries()).map(([label, data]) => ({
      label,
      count: data.count,
      avgScore: Math.round((data.totalScore / data.count) * 100),
    }));
  }, [activeOpinions, timeRange, trendOverride]);

  const hospitalComparisonData = useMemo(() => {
    if (statsDetail?.hospitals?.length) {
      return statsDetail.hospitals.slice(0, 10);
    }
    const grouped = new Map<string, { high: number; medium: number; low: number }>();

    activeOpinions.forEach((item) => {
      const hospital = item.hospital || "未知";
      if (!grouped.has(hospital)) {
        grouped.set(hospital, { high: 0, medium: 0, low: 0 });
      }
      const data = grouped.get(hospital)!;
      if (item.severity === "high") data.high++;
      else if (item.severity === "medium") data.medium++;
      else data.low++;
    });

    return Array.from(grouped.entries())
      .map(([hospital, severity]) => ({
        hospital,
        total: severity.high + severity.medium + severity.low,
        ...severity,
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [activeOpinions, statsDetail]);

  const hospitalLegendItems = [
    { id: "low", label: "低危", color: "#10b981" },
    { id: "medium", label: "中危", color: "#f97316" },
    { id: "high", label: "高危", color: "#ef4444" },
  ];


  const sourceDistributionData = useMemo(() => {
    if (statsDetail?.sources?.length) {
      return statsDetail.sources.slice(0, 8);
    }
    const grouped = new Map<string, number>();

    activeOpinions.forEach((item) => {
      const source = item.source || "未知";
      grouped.set(source, (grouped.get(source) || 0) + 1);
    });

    return Array.from(grouped.entries())
      .map(([source, count]) => ({ source, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [activeOpinions, statsDetail]);

  const severityDistributionData = useMemo(() => {
    if (statsDetail?.severity) {
      const data = [
        { name: "高危", value: statsDetail.severity.high ?? 0, color: "#ef4444" },
        { name: "中危", value: statsDetail.severity.medium ?? 0, color: "#f97316" },
        { name: "低危", value: statsDetail.severity.low ?? 0, color: "#10b981" },
      ];
      return data.filter((d) => d.value > 0);
    }
    const data = [
      { name: "高危", value: activeOpinions.filter((o) => o.severity === "high").length, color: "#ef4444" },
      { name: "中危", value: activeOpinions.filter((o) => o.severity === "medium").length, color: "#f97316" },
      { name: "低危", value: activeOpinions.filter((o) => o.severity === "low").length, color: "#10b981" },
    ];
    return data.filter((d) => d.value > 0);
  }, [activeOpinions, statsDetail]);

  function getTimeRangeMs(range: "24h" | "7d" | "30d"): number {
    switch (range) {
      case "24h":
        return 24 * 60 * 60 * 1000;
      case "7d":
        return 7 * 24 * 60 * 60 * 1000;
      case "30d":
        return 30 * 24 * 60 * 60 * 1000;
    }
  }

  const handleMouseEnter = (e: React.MouseEvent, title: string, content: string) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipContent({
      title,
      content,
      position: { x: rect.left + rect.width / 2, y: rect.bottom + 10 }
    });
  };

  const handleMouseLeave = () => {
    setTooltipContent(null);
  };

  const openSuppressModal = async () => {
    setSuppressModalOpen(true);
    setSuppressLoading(true);
    try {
      const resp = await apiFetch("/api/notification/suppress_keywords");
      if (resp.ok) {
        const data = await resp.json();
        setSuppressKeywords(Array.isArray(data.keywords) ? data.keywords : []);
      }
    } catch (err) {
      // ignore
    } finally {
      setSuppressLoading(false);
    }
  };

  const addSuppressKeyword = () => {
    const text = newKeyword.trim();
    if (!text) return;
    if (!suppressKeywords.includes(text)) {
      setSuppressKeywords([...suppressKeywords, text]);
    }
    setNewKeyword("");
  };

  const removeSuppressKeyword = (keyword: string) => {
    setSuppressKeywords(suppressKeywords.filter((k) => k !== keyword));
  };

  const saveSuppressKeywords = async () => {
    setSuppressSaving(true);
    try {
      const resp = await apiFetch("/api/notification/suppress_keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keywords: suppressKeywords }),
      });
      if (!resp.ok) throw new Error("保存失败");
      setSuppressModalOpen(false);
    } catch (err) {
      alert("保存失败，请检查后端接口。");
    } finally {
      setSuppressSaving(false);
    }
  };

  const exportToCSV = (data: OpinionItem[], filename: string) => {
    const headers = ['ID', '医院', '标题', '来源', '严重程度', '风险分', '状态', '创建时间', '警示理由', '内容', '原文链接'];
    const rows = data.map(item => [
      item.id,
      item.hospital,
      item.title,
      item.source,
      item.severity,
      Math.round((item.score || severityMeta[normalizeSeverity(item.severity)].score) * 100),
      item.status,
      item.createdAt,
      item.reason,
      item.content,
      item.url || ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const exportToExcel = (data: OpinionItem[], filename: string) => {
    const headers = ['ID', '医院', '标题', '来源', '严重程度', '风险分', '状态', '创建时间', '警示理由', '内容', '原文链接'];
    const rows = data.map(item => [
      item.id,
      item.hospital,
      item.title,
      item.source,
      item.severity,
      Math.round((item.score || severityMeta[normalizeSeverity(item.severity)].score) * 100),
      item.status,
      item.createdAt,
      item.reason,
      item.content,
      item.url || ''
    ]);

    const excelContent = [
      headers.join('\t'),
      ...rows.map(row => row.join('\t'))
    ].join('\n');

    const blob = new Blob([excelContent], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}.xls`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const generateHospitalReport = async () => {
    if (!reportHospital) {
      alert('请选择医院');
      return;
    }

    setIsGeneratingReport(true);
    try {
      const response = await apiFetch("/api/report/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hospital: reportHospital,
          start_date: reportDateRange.start || "",
          end_date: reportDateRange.end || "",
          format: reportFormat,
        }),
      });

      if (!response.ok) {
        throw new Error("报告生成失败");
      }

      const data = await response.json();
      if (!data?.success) {
        throw new Error(data?.message || "报告生成失败");
      }

      const downloadPath =
        data?.files?.[reportFormat] ||
        data?.files?.markdown ||
        data?.files?.word;

      if (!downloadPath) {
        throw new Error("未返回可下载的报告文件");
      }

      const downloadUrl = downloadPath.startsWith("http")
        ? downloadPath
        : `${API_BASE}${downloadPath}`;

      const fileResponse = await fetch(downloadUrl);
      if (!fileResponse.ok) {
        throw new Error("报告下载失败");
      }

      const blob = await fileResponse.blob();
      const reportName = reportHospital === "all" ? "全院汇总" : reportHospital;
      const filename = `${reportName}_舆情报告_${formatLocalDate(new Date())}.${reportFormat === "word" ? "docx" : "md"}`;
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);

      setExportReportOpen(false);
    } catch (err) {
      alert("报告生成失败，请检查后端接口。");
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const handleExport = (format: 'csv' | 'excel') => {
    setIsExporting(true);

    let filteredData = activeOpinions;

    if (exportHospital !== 'all') {
      filteredData = filteredData.filter(item => item.hospital === exportHospital);
    }

    if (exportDateRange.start || exportDateRange.end) {
      filteredData = filteredData.filter(item => {
        const itemDate = typeof item.createdAt === "string" ? parseLocalDateTime(item.createdAt) : null;
        if (!itemDate) return false;

        if (exportDateRange.start) {
          const startDate = parseDateInput(exportDateRange.start);
          if (startDate && itemDate < startDate) return false;
        }

        if (exportDateRange.end) {
          const endDate = parseDateInput(exportDateRange.end);
          if (endDate) {
            endDate.setHours(23, 59, 59, 999);
            if (itemDate > endDate) return false;
          }
        }

        return true;
      });
    }

    const filename = `舆情数据_${formatLocalDate(new Date())}`;

    if (format === 'csv') {
      exportToCSV(filteredData, filename);
    } else {
      exportToExcel(filteredData, filename);
    }

    setIsExporting(false);
    setExportModalOpen(false);
    setExportDateRange({ start: "", end: "" });
    setExportHospital("all");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.15),_transparent_55%),radial-gradient(circle_at_20%_30%,_rgba(249,115,22,0.08),_transparent_45%),radial-gradient(circle_at_80%_20%,_rgba(16,185,129,0.12),_transparent_40%)]" />

      <header className="relative z-10 border-b border-slate-800/70 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="rounded-2xl bg-indigo-500/20 p-3 shadow-[0_0_30px_rgba(99,102,241,0.35)]">
              <ShieldAlert className="h-6 w-6 text-indigo-300" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight">医院舆情监控</h1>
            </div>
          </div>

          <div className="hidden lg:flex lg:w-auto lg:flex-row lg:items-center lg:gap-3">
            <div className="flex items-center gap-2 rounded-2xl border border-slate-800/60 bg-slate-900/60 px-3 py-2">
              <Calendar className="h-4 w-4 text-slate-400" />
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value as "24h" | "7d" | "30d")}
                className="border-none bg-transparent text-sm text-slate-200 outline-none"
              >
                <option value="24h">最近24小时</option>
                <option value="7d">最近7天</option>
                <option value="30d">最近30天</option>
              </select>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setExportModalOpen(true)}
                className="flex items-center gap-2 rounded-2xl border border-slate-800/60 bg-slate-900/60 px-4 py-2 text-sm text-slate-200 transition hover:bg-slate-800/80 hover:border-slate-700/80"
              >
                <Download className="h-4 w-4" />
                <span>导出数据</span>
              </button>

              <button
                onClick={openSuppressModal}
                className="flex items-center gap-2 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
              >
                <ShieldAlert className="h-4 w-4" />
                <span>屏蔽关键词</span>
              </button>

              <button
                onClick={() => setExportReportOpen(true)}
                className="flex items-center gap-2 rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-2 text-sm font-semibold text-indigo-200 transition hover:bg-indigo-500/20"
              >
                <FileText className="h-4 w-4" />
                <span>生成报告</span>
              </button>
            </div>
          </div>

          <form onSubmit={handleSearch} className="hidden lg:flex lg:w-auto lg:flex-row lg:items-center lg:gap-3">
            <div className="relative w-full lg:w-auto">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="自然语言搜索：比如“产品质量投诉”"
                className="w-full rounded-2xl border border-slate-800/60 bg-slate-900/60 py-2.5 pl-10 pr-4 text-sm text-slate-200 outline-none transition focus:border-indigo-500/70 lg:w-80"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
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
            </div>
          </form>
        </div>
      </header>

      <main className="relative z-10 mx-auto grid max-w-7xl grid-cols-12 items-stretch gap-6 px-6 py-8 lg:min-h-[calc(100vh-10rem)]">
        <section className="col-span-12 lg:hidden space-y-3">
          <div className="flex items-center gap-2 rounded-2xl border border-slate-800/60 bg-slate-900/60 px-3 py-2">
            <Calendar className="h-4 w-4 text-slate-400" />
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as "24h" | "7d" | "30d")}
              className="border-none bg-transparent text-sm text-slate-200 outline-none"
            >
              <option value="24h">最近24小时</option>
              <option value="7d">最近7天</option>
              <option value="30d">最近30天</option>
            </select>
          </div>

          <form onSubmit={handleSearch} className="flex flex-col gap-2">
            <div className="relative w-full">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="自然语言搜索：比如“产品质量投诉”"
                className="w-full rounded-2xl border border-slate-800/60 bg-slate-900/60 py-2.5 pl-10 pr-4 text-sm text-slate-200 outline-none transition focus:border-indigo-500/70"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                className="flex-1 rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-indigo-200"
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
            </div>
          </form>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setExportModalOpen(true)}
              className="flex items-center justify-center gap-2 rounded-2xl border border-slate-800/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 transition hover:bg-slate-800/80"
            >
              <Download className="h-4 w-4" />
              <span>导出</span>
            </button>
            <button
              onClick={openSuppressModal}
              className="flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
            >
              <ShieldAlert className="h-4 w-4" />
              <span>屏蔽</span>
            </button>
            <button
              onClick={() => setExportReportOpen(true)}
              className="col-span-2 flex items-center justify-center gap-2 rounded-2xl border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-sm font-semibold text-indigo-200 transition hover:bg-indigo-500/20"
            >
              <FileText className="h-4 w-4" />
              <span>生成报告</span>
            </button>
          </div>
        </section>
        {error && (
          <div className="col-span-12 flex items-center gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            {error}
          </div>
        )}

          <section ref={leftColRef} className="col-span-12 lg:col-span-4 space-y-6 lg:h-full lg:min-h-0">
          <div className="grid grid-cols-2 gap-4">
            <div
              className="rounded-3xl border border-red-500/30 bg-red-500/10 p-6 cursor-help"
              onMouseEnter={(e) => handleMouseEnter(e, '高危舆情', '当前标记为"高危"等级的负面舆情数量\n\n需要立即处理，避免危机扩大\n涉及医疗事故、重大纠纷、隐私泄露等')}
              onMouseLeave={handleMouseLeave}
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-red-300">高危舆情</p>
              <p className="font-display text-3xl font-bold">{stats.highRisk}</p>
            </div>
            <div
              className="rounded-3xl border border-indigo-500/30 bg-indigo-500/10 p-6 cursor-help"
              onMouseEnter={(e) => handleMouseEnter(e, '平均风险指数', '所有活跃舆情的平均风险分值（0-100分）\n\n高危：92分 | 中危：60分 | 低危：35分\n指数越高 → 整体舆情态势越严峻\n可作为舆情健康度的参考指标')}
              onMouseLeave={handleMouseLeave}
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-200">平均风险指数</p>
              <p className="font-display text-3xl font-bold">{stats.avgScore}</p>
            </div>
            <div
              className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-6 cursor-help"
              onMouseEnter={(e) => handleMouseEnter(e, '当前监控', '系统中正在监控的活跃负面舆情总数\n\n包含所有未标记为误报的舆情\n与"已误报"对应，区分有效舆情和误判\n数量越大 → 处理压力越大')}
              onMouseLeave={handleMouseLeave}
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-200">当前监控</p>
              <p className="font-display text-3xl font-bold">{stats.total}</p>
            </div>
            <div
              className="rounded-3xl border border-slate-700/40 bg-slate-900/60 p-6 cursor-help"
              onMouseEnter={(e) => handleMouseEnter(e, '已误报', '用户已标记为误判的舆情数量\n\n这些舆情不会被计入风险指标\n可以随时恢复为负面舆情')}
              onMouseLeave={handleMouseLeave}
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">已误报</p>
              <p className="font-display text-3xl font-bold text-slate-200">{stats.dismissed}</p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/70 bg-slate-900/50 p-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">压力走势</h2>
              <div className="flex items-center gap-2">
                <select
                  value={trendMode}
                  onChange={(e) => setTrendMode(e.target.value as "count" | "score")}
                  className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1 text-xs text-slate-200"
                >
                  <option value="count">舆情数量</option>
                  <option value="score">平均风险分</option>
                </select>
                <BarChart3 className="h-4 w-4 text-slate-500" />
              </div>
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
                  <XAxis
                    dataKey="label"
                    stroke="#475569"
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                  />
                  <YAxis
                    stroke="#475569"
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                    label={{
                      value: trendMode === "count" ? "数量" : "平均风险分",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#94a3b8",
                      fontSize: 11,
                    }}
                  />
                  <Area dataKey={trendMode === "count" ? "count" : "avgScore"} stroke="#6366f1" strokeWidth={2} fill="url(#trendGradient)" />
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

          <div className="rounded-3xl border border-slate-800/70 bg-slate-900/50 p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">医院舆情对比</h2>
              <Activity className="h-4 w-4 text-slate-500" />
            </div>
            <div className="mt-6 h-48">
              <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hospitalComparisonData.slice(0, 5)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="hospital"
                  stroke="#475569"
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  angle={-30}
                  textAnchor="end"
                  height={60}
                />
                <YAxis stroke="#475569" fontSize={11} tick={{ fill: "#94a3b8" }} />
                <Tooltip
                  contentStyle={{
                    background: "#0f172a",
                    border: "1px solid #1f2937",
                    borderRadius: "12px",
                    color: "#e2e8f0",
                  }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <Legend
                  content={() => (
                    <ul className="flex items-center justify-center gap-4 text-xs">
                      {hospitalLegendItems.map((item) => (
                        <li key={item.id} className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: item.color }} />
                          <span style={{ color: item.color }}>{item.label}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                />
                <Bar dataKey="low" name="低危" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
                <Bar dataKey="medium" name="中危" stackId="a" fill="#f97316" radius={[0, 0, 0, 0]} />
                <Bar dataKey="high" name="高危" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
              </BarChart>
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

        <section
          className="col-span-12 lg:col-span-8 space-y-6 lg:flex lg:flex-col lg:gap-6 lg:h-[var(--left-col-height)] lg:min-h-0 lg:overflow-hidden"
          style={leftColHeight ? ({ "--left-col-height": `${leftColHeight}px` } as React.CSSProperties) : undefined}
        >
          <div className="grid grid-cols-1 gap-6">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="rounded-3xl border border-slate-800/70 bg-slate-900/50 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">渠道分布</h2>
                  <PieChartIcon className="h-4 w-4 text-slate-500" />
                </div>
                <div className="mt-6 h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={sourceDistributionData}
                      layout="vertical"
                      margin={{ left: 16, right: 8, top: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis type="number" stroke="#475569" fontSize={11} tick={{ fill: "#94a3b8" }} />
                      <YAxis
                        type="category"
                        dataKey="source"
                        stroke="#475569"
                        fontSize={11}
                        tick={{ fill: "#94a3b8" }}
                        width={110}
                        tickMargin={8}
                        interval={0}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid #1f2937",
                          borderRadius: "12px",
                          color: "#e2e8f0",
                        }}
                        labelStyle={{ color: "#94a3b8" }}
                      />
                      <Bar dataKey="count" fill="#6366f1" radius={[0, 8, 8, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-3xl border border-slate-800/70 bg-slate-900/50 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">严重程度分布</h2>
                  <TrendingUp className="h-4 w-4 text-slate-500" />
                </div>
                <div className="mt-6 space-y-3">
                  {severityDistributionData.map((item) => (
                    <div key={item.name}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-400">{item.name}</span>
                        <span className="font-semibold" style={{ color: item.color }}>{item.value} 条</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${(item.value / Math.max(activeOpinions.length, 1)) * 100}%`,
                            backgroundColor: item.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="font-display text-xl font-semibold">实时舆情列表</h2>
              <span className="text-xs text-slate-500">
                {listStatsLabel}
              </span>
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
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={groupByEvent}
                  onChange={(e) => setGroupByEvent(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-indigo-500"
                />
                按事件聚合
              </label>
            </div>

            <div className="flex-1 min-h-0">
              {isLoading ? (
                <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-800/70 bg-slate-900/40">
                  <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
                  <p className="mt-4 text-xs uppercase tracking-widest text-slate-500">加载中</p>
                </div>
              ) : displayOpinions.length === 0 ? (
                <div className="flex h-full min-h-[320px] flex-col items-center justify-center rounded-3xl border border-slate-800/70 bg-slate-900/40 text-slate-500">
                  暂无舆情数据
                </div>
              ) : (
                <div className="h-full space-y-4 overflow-y-auto pr-2">
                  {displayOpinions.map((item) => {
                    const meta = severityMeta[normalizeSeverity(item.severity)];
                    const scoreValue = Math.round((item.score || meta.score) * 100);
                    const eventTotal = Number(item.event_total || 0) || 0;
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
                          {eventTotal > 1 && (
                            <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-1 text-[10px] uppercase tracking-wider text-indigo-200">
                              事件池 {eventTotal} 条
                            </span>
                          )}
                          {item.is_duplicate && (
                            <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-[10px] uppercase tracking-wider text-amber-200">
                              重复
                            </span>
                          )}
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
            </div>
          </div>
        </section>
      </main>

      {tooltipContent && (
        <div
          className="fixed z-50 max-w-xs animate-in fade-in duration-200"
          style={{
            left: `${tooltipContent.position.x}px`,
            top: `${tooltipContent.position.y}px`,
            transform: 'translate(-50%, 0)'
          }}
        >
          <div className="rounded-2xl border border-slate-700/80 bg-slate-800/95 p-5 shadow-2xl backdrop-blur-sm">
            <div className="flex items-center gap-3 mb-3 pb-3 border-b border-slate-700/50">
              <div className="rounded-xl bg-gradient-to-r from-indigo-500/20 to-purple-500/20 p-2">
                <Sparkles className="h-5 w-5 text-indigo-300" />
              </div>
              <h3 className="text-base font-semibold text-slate-100">{tooltipContent.title}</h3>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{tooltipContent.content}</p>
          </div>
        </div>
      )}

      {selectedItem && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSelectedItem(null)} />
          <aside className="relative h-full w-full max-w-xl overflow-y-auto border-l border-slate-800/80 bg-slate-900/95 p-6 shadow-2xl touch-pan-y">
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
                {(selectedItem.event_id || selectedItem.event_total || selectedItem.is_duplicate) && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-slate-300">
                    {selectedItem.event_total ? (
                      <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-1 uppercase tracking-wider text-indigo-200">
                        事件池 {selectedItem.event_total} 条
                      </span>
                    ) : null}
                    {selectedItem.is_duplicate ? (
                      <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-1 uppercase tracking-wider text-amber-200">
                        重复舆情
                      </span>
                    ) : null}
                    {selectedItem.event_id ? (
                      <span className="rounded-full border border-slate-700/60 bg-slate-900/40 px-2 py-1 uppercase tracking-wider text-slate-300">
                        Event #{selectedItem.event_id}
                      </span>
                    ) : null}
                  </div>
                )}
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

              {selectedItem.event_id && (
                <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                  <p className="text-xs uppercase tracking-widest text-slate-500">事件追踪（本地已加载范围）</p>
                  <div className="mt-3 space-y-2">
                    {opinions
                      .filter((o) => o.event_id && o.event_id === selectedItem.event_id)
                      .slice()
                      .sort((a, b) => {
                        const at = parseLocalDateTime(a.createdAt)?.getTime() ?? 0;
                        const bt = parseLocalDateTime(b.createdAt)?.getTime() ?? 0;
                        return at - bt;
                      })
                      .slice(0, 12)
                      .map((o) => (
                        <button
                          key={o.id}
                          type="button"
                          onClick={() => handleInsight(o)}
                          className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-800/70 bg-slate-900/40 px-3 py-2 text-left text-xs text-slate-300 hover:border-indigo-500/40"
                        >
                          <div className="min-w-0">
                            <div className="truncate text-slate-200">{o.title}</div>
                            <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                              <span>{formatTime(o.createdAt)}</span>
                              <span>·</span>
                              <span>{o.source}</span>
                              {o.is_duplicate ? (
                                <>
                                  <span>·</span>
                                  <span className="text-amber-200">重复</span>
                                </>
                              ) : null}
                            </div>
                          </div>
                          <ArrowUpRight className="h-4 w-4 flex-none text-slate-500" />
                        </button>
                      ))}
                    {selectedItem.event_total && selectedItem.event_total > 12 && (
                      <p className="pt-1 text-[10px] text-slate-500">
                        注：事件池共 {selectedItem.event_total} 条，这里仅展示当前已加载的最多 12 条。
                      </p>
                    )}
                  </div>
                </div>
              )}

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

      {exportModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setExportModalOpen(false)} />
          <div className="relative w-full max-w-md rounded-3xl border border-slate-800/70 bg-slate-900/95 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">导出数据</h3>
              <button onClick={() => setExportModalOpen(false)} className="rounded-full p-2 text-slate-400 hover:bg-slate-800">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">时间范围</label>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <DatePicker
                      selected={exportDateRange.start ? parseDateInput(exportDateRange.start) : null}
                      onChange={(date: Date | null) => setExportDateRange({ ...exportDateRange, start: date ? formatDateInput(date) : "" })}
                      selectsStart
                      startDate={exportDateRange.start ? parseDateInput(exportDateRange.start) : null}
                      endDate={exportDateRange.end ? parseDateInput(exportDateRange.end) : null}
                      dateFormat="yyyy-MM-dd"
                      placeholderText="开始日期"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <span className="text-slate-500">至</span>
                  <div className="flex-1">
                    <DatePicker
                      selected={exportDateRange.end ? parseDateInput(exportDateRange.end) : null}
                      onChange={(date: Date | null) => setExportDateRange({ ...exportDateRange, end: date ? formatDateInput(date) : "" })}
                      selectsEnd
                      startDate={exportDateRange.start ? parseDateInput(exportDateRange.start) : null}
                      endDate={exportDateRange.end ? parseDateInput(exportDateRange.end) : null}
                      minDate={exportDateRange.start ? parseDateInput(exportDateRange.start) : null}
                      dateFormat="yyyy-MM-dd"
                      placeholderText="结束日期"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">医院筛选</label>
                <select
                  value={exportHospital}
                  onChange={(e) => setExportHospital(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">全部医院</option>
                  {hospitalOptions.filter(h => h !== 'all').map(h => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div className="pt-4 border-t border-slate-800">
                <p className="text-sm font-medium text-slate-300 mb-3">导出格式</p>
                <div className="flex gap-3">
                  <button
                    onClick={() => handleExport('csv')}
                    disabled={isExporting}
                    className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-medium text-slate-200 transition hover:bg-slate-900 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    CSV 格式
                  </button>
                  <button
                    onClick={() => handleExport('excel')}
                    disabled={isExporting}
                    className="flex-1 rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-3 text-sm font-medium text-indigo-200 transition hover:bg-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Excel 格式
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {exportReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setExportReportOpen(false)} />
          <div className="relative w-full max-w-md rounded-3xl border border-indigo-500/30 bg-slate-900/95 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">生成医院舆情报告</h3>
              <button onClick={() => setExportReportOpen(false)} className="rounded-full p-2 text-slate-400 hover:bg-slate-800">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  选择医院 <span className="text-red-400">*</span>
                </label>
                <select
                  value={reportHospital}
                  onChange={(e) => setReportHospital(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">全院汇总</option>
                  {hospitalOptions.filter(h => h !== 'all').map(h => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">时间范围</label>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <DatePicker
                      selected={reportDateRange.start ? parseDateInput(reportDateRange.start) : null}
                      onChange={(date: Date | null) => setReportDateRange({ ...reportDateRange, start: date ? formatDateInput(date) : "" })}
                      selectsStart
                      startDate={reportDateRange.start ? parseDateInput(reportDateRange.start) : null}
                      endDate={reportDateRange.end ? parseDateInput(reportDateRange.end) : null}
                      dateFormat="yyyy-MM-dd"
                      placeholderText="开始日期"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <span className="text-slate-500">至</span>
                  <div className="flex-1">
                    <DatePicker
                      selected={reportDateRange.end ? parseDateInput(reportDateRange.end) : null}
                      onChange={(date: Date | null) => setReportDateRange({ ...reportDateRange, end: date ? formatDateInput(date) : "" })}
                      selectsEnd
                      startDate={reportDateRange.start ? parseDateInput(reportDateRange.start) : null}
                      endDate={reportDateRange.end ? parseDateInput(reportDateRange.end) : null}
                      minDate={reportDateRange.start ? parseDateInput(reportDateRange.start) : null}
                      dateFormat="yyyy-MM-dd"
                      placeholderText="结束日期"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-500 mt-1">留空则导出该医院全部时间范围</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">报告格式</label>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setReportFormat("markdown")}
                    className={`flex-1 rounded-xl border px-4 py-3 text-sm font-medium transition ${
                      reportFormat === "markdown"
                        ? "border-indigo-500/60 bg-indigo-500/20 text-indigo-100"
                        : "border-slate-700 bg-slate-950 text-slate-300 hover:bg-slate-900"
                    }`}
                  >
                    Markdown
                  </button>
                  <button
                    type="button"
                    onClick={() => setReportFormat("word")}
                    className={`flex-1 rounded-xl border px-4 py-3 text-sm font-medium transition ${
                      reportFormat === "word"
                        ? "border-indigo-500/60 bg-indigo-500/20 text-indigo-100"
                        : "border-slate-700 bg-slate-950 text-slate-300 hover:bg-slate-900"
                    }`}
                  >
                    Word
                  </button>
                </div>
              </div>

              <button
                onClick={generateHospitalReport}
                disabled={isGeneratingReport || !reportHospital}
                className="w-full rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-3 text-sm font-medium text-indigo-200 transition hover:bg-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isGeneratingReport ? '生成中...' : '生成报告'}
              </button>
            </div>
          </div>
        </div>
      )}

      {suppressModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSuppressModalOpen(false)} />
          <div className="relative w-full max-w-md rounded-3xl border border-emerald-500/30 bg-slate-900/95 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold">屏蔽关键词</h3>
              <button onClick={() => setSuppressModalOpen(false)} className="rounded-full p-2 text-slate-400 hover:bg-slate-800">
                <X className="h-4 w-4" />
              </button>
            </div>

            {suppressLoading ? (
              <div className="flex items-center gap-3 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                正在加载...
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">新增关键词</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newKeyword}
                      onChange={(e) => setNewKeyword(e.target.value)}
                      className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none"
                      placeholder="例如：红包回扣"
                    />
                    <button
                      type="button"
                      onClick={addSuppressKeyword}
                      className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
                    >
                      添加
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">当前关键词</label>
                  {suppressKeywords.length === 0 ? (
                    <p className="text-sm text-slate-500">暂无关键词</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {suppressKeywords.map((keyword) => (
                        <span key={keyword} className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1 text-xs text-slate-200">
                          {keyword}
                          <button
                            type="button"
                            onClick={() => removeSuppressKeyword(keyword)}
                            className="text-slate-400 hover:text-slate-200"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-800">
                  <button
                    onClick={saveSuppressKeywords}
                    disabled={suppressSaving}
                    className="w-full rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {suppressSaving ? "保存中..." : "保存并生效"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<OpinionDashboard />);
}

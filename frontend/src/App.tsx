import { DocumentTasks, Flow, Home, Moon, Sun } from "@carbon/icons-react";
import { Button, Content, Header, HeaderGlobalAction, HeaderGlobalBar, HeaderName, SideNav, SideNavItems, SideNavLink, SkipToContent } from "@carbon/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { CaseDetail } from "./components/CaseDetail";
import { Dashboard } from "./components/Dashboard";
import { ReviewQueue } from "./components/ReviewQueue";
import { UploadDialog } from "./components/UploadDialog";
import type { AcceptedTask, CaseDetail as CaseDetailType, CaseSummary, DashboardSummary, SystemStatus } from "./types";
import { errorMessage, hasActiveWork, hasProcessingCases } from "./workflow";

type View = "dashboard" | "queue" | "detail";

function readLocation(): { view: View; caseId: string | null } {
  const match = window.location.hash.match(/^#case\/(.+)$/);
  if (match) {
    try { return { view: "detail", caseId: decodeURIComponent(match[1]) }; } catch { /* Invalid link returns to the overview. */ }
  }
  return { view: window.location.hash === "#queue" ? "queue" : "dashboard", caseId: null };
}

export default function App() {
  const [view, setView] = useState<View>(() => readLocation().view);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(() => readLocation().caseId);
  const [dark, setDark] = useState(() => localStorage.getItem("review-console-theme") === "dark" || (!localStorage.getItem("review-console-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches));
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [detail, setDetail] = useState<CaseDetailType | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const dataController = useRef<AbortController | null>(null);
  const detailController = useRef<AbortController | null>(null);

  const loadData = useCallback(async (foreground = true, signal?: AbortSignal) => {
    if (foreground) {
      dataController.current?.abort();
      dataController.current = new AbortController();
      signal = dataController.current.signal;
      setLoading(true);
    }
    const results = await Promise.allSettled([api.summary(signal), api.cases(signal), api.systemStatus(signal)]);
    if (signal?.aborted) return;
    if (results[0].status === "fulfilled") setSummary(results[0].value);
    if (results[1].status === "fulfilled") setCases(results[1].value);
    if (results[0].status === "rejected" || results[1].status === "rejected") {
      const failed = results.find((result) => result.status === "rejected");
      setError(failed?.status === "rejected" ? errorMessage(failed.reason, "加载失败") : "加载失败");
    } else setError(null);
    setSystemStatus(results[2].status === "fulfilled" && results[2].value.services ? results[2].value : null);
    if (foreground) setLoading(false);
  }, []);

  const loadDetail = useCallback(async (foreground = true, signal?: AbortSignal) => {
    if (!selectedCaseId) return;
    if (foreground) {
      detailController.current?.abort();
      detailController.current = new AbortController();
      signal = detailController.current.signal;
      setDetailLoading(true);
    }
    try {
      const next = await api.case(selectedCaseId, signal);
      if (!signal?.aborted) { setDetail(next); setDetailError(null); }
    } catch (requestError) {
      if (!signal?.aborted) setDetailError(errorMessage(requestError, "案件加载失败"));
    } finally {
      if (foreground && !signal?.aborted) setDetailLoading(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    void loadData();
    return () => dataController.current?.abort();
  }, [loadData]);
  useEffect(() => {
    if (view === "detail") void loadDetail();
    return () => detailController.current?.abort();
  }, [loadDetail, view]);
  useEffect(() => {
    document.documentElement.dataset.carbonTheme = dark ? "g100" : "white";
    localStorage.setItem("review-console-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if ((view === "detail" && !detailLoading && detail) || (view !== "detail" && !loading)) document.querySelector<HTMLElement>("#main-content h1")?.focus({ preventScroll: true });
  }, [view, selectedCaseId, detailLoading, loading]);

  const active = view === "detail" ? hasActiveWork(detail) : hasProcessingCases(cases);
  useEffect(() => {
    if (!active) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | null = null;
    const schedule = () => {
      timer = setTimeout(async () => {
        const current = new AbortController();
        controller = current;
        if (view === "detail") await loadDetail(false, current.signal);
        if (!disposed && !current.signal.aborted) await loadData(false, current.signal);
        if (!disposed && !current.signal.aborted) schedule();
      }, document.hidden ? 15_000 : 2_000);
    };
    const visibilityChanged = () => { clearTimeout(timer); controller?.abort(); schedule(); };
    schedule();
    document.addEventListener("visibilitychange", visibilityChanged);
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); document.removeEventListener("visibilitychange", visibilityChanged); };
  }, [active, view, loadData, loadDetail]);

  function navigate(nextView: View, caseId: string | null = null) {
    setView(nextView);
    setSelectedCaseId(caseId);
    if (caseId !== selectedCaseId) setDetail(null);
    setDetailError(null);
    history.replaceState(null, "", nextView === "detail" && caseId ? `#case/${encodeURIComponent(caseId)}` : `#${nextView}`);
  }

  function handleDecided(updated: CaseDetailType) {
    setDetail(updated);
    setCases((items) => items.map((item) => item.id === updated.id ? updated : item));
    void loadData(false);
  }

  function handleUploaded(task: AcceptedTask) {
    setUploadOpen(false);
    setUploadNotice(task.duplicate_of ? `文档已提交。相同内容曾用于案件 ${task.duplicate_of}，本次将独立审查。` : "文档已接受，后台正在处理。刷新或关闭页面不会取消任务。");
    navigate("detail", task.case_id);
    void loadData(false);
  }

  return (
    <div className={dark ? "app theme-dark" : "app"}>
      <Header aria-label="AI Review Console">
        <SkipToContent />
        <HeaderName prefix="AI">Review Console</HeaderName>
        <span className="header-attribution">Built on Langflow</span>
        <HeaderGlobalBar><HeaderGlobalAction aria-label={dark ? "切换到浅色模式" : "切换到深色模式"} onClick={() => setDark((value) => !value)}>{dark ? <Sun size={20} /> : <Moon size={20} />}</HeaderGlobalAction></HeaderGlobalBar>
      </Header>
      <SideNav aria-label="主导航" isFixedNav expanded isChildOfHeader={false}>
        <SideNavItems>
          <SideNavLink href="#dashboard" isActive={view === "dashboard"} renderIcon={Home} onClick={(event) => { event.preventDefault(); navigate("dashboard"); }}>总览</SideNavLink>
          <SideNavLink href="#queue" isActive={view === "queue" || view === "detail"} renderIcon={DocumentTasks} onClick={(event) => { event.preventDefault(); navigate("queue"); }}>审查队列</SideNavLink>
          <SideNavLink renderIcon={Flow} href="http://localhost:7860" target="_blank" rel="noreferrer">Langflow 管理</SideNavLink>
        </SideNavItems>
        <div className="side-notice"><strong>SYNTHETIC</strong><span>仅使用虚构演示数据</span><span>演示身份：demo-reviewer</span></div>
      </SideNav>
      <Content id="main-content" className="main-content">
        <nav className="mobile-navigation" aria-label="移动主导航"><Button size="sm" kind={view === "dashboard" ? "primary" : "ghost"} onClick={() => navigate("dashboard")}>总览</Button><Button size="sm" kind={view !== "dashboard" ? "primary" : "ghost"} onClick={() => navigate("queue")}>审查队列</Button></nav>
        {view === "dashboard" && <Dashboard summary={summary} systemStatus={systemStatus} cases={cases.filter((item) => item.status === "pending_approval" || (item.risk_level !== null && ["high", "critical"].includes(item.risk_level)))} loading={loading} error={error} onRetry={() => void loadData()} onSelectCase={(id) => navigate("detail", id)} onOpenQueue={() => navigate("queue")} />}
        {view === "queue" && <ReviewQueue cases={cases} loading={loading} error={error} onRetry={() => void loadData()} onSelectCase={(id) => navigate("detail", id)} onUpload={() => setUploadOpen(true)} />}
        {view === "detail" && <CaseDetail key={selectedCaseId} detail={detail} loading={detailLoading} error={detailError} notice={uploadNotice} onDismissNotice={() => setUploadNotice(null)} onBack={() => navigate("queue")} onReload={() => void loadDetail()} onRefresh={() => loadDetail(false)} onDecided={handleDecided} />}
      </Content>
      <footer><span>仅使用虚构数据。演示身份：demo-reviewer。不构成法律意见。</span><span>基于 Langflow / Built on Langflow</span></footer>
      {uploadOpen && <UploadDialog onClose={() => setUploadOpen(false)} onAccepted={handleUploaded} />}
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import STAGES from "./data/stages";
import WALKTHROUGHS from "./data/walkthrough";
import ProgressBar from "./components/ProgressBar";
import MainPanel from "./components/MainPanel";
import Sidebar from "./components/Sidebar";
import StagePopup from "./components/StagePopup";
import GuidedCallout from "./components/GuidedCallout";
import { ThemeContext, fontsFor } from "./lib/theme";

const TOTAL = 1 + STAGES.length + 1;

function getStageId(current: number): string | null {
  if (current === 0 || current === TOTAL - 1) return null;
  return STAGES[current - 1]?.id ?? null;
}

function getCalloutSteps(stageId: string | null): number {
  if (!stageId) return 0;
  const wt = WALKTHROUGHS[stageId];
  if (!wt) return 0;
  return wt.steps.filter((s) => s.type === "callout").length;
}

function getPopupStep(stageId: string | null) {
  if (!stageId) return null;
  const wt = WALKTHROUGHS[stageId];
  if (!wt) return null;
  return wt.steps.find((s) => s.type === "popup") ?? null;
}

function getCalloutStep(stageId: string | null, calloutIndex: number) {
  if (!stageId) return null;
  const wt = WALKTHROUGHS[stageId];
  if (!wt) return null;
  const callouts = wt.steps.filter((s) => s.type === "callout");
  return callouts[calloutIndex] ?? null;
}

export default function App() {
  const [current, setCurrent] = useState(0);
  // subStep: -1 = free browse, 0 = popup (first visit only), 1..N = callout index (1-based), N+1 = free browse after callouts
  const [subStep, setSubStep] = useState(-1);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("tiny-dec-theme");
    return saved === "dark" ? "dark" : "light";
  });
  const [visited, setVisited] = useState<Set<number>>(() => new Set());
  const [popupSeen, setPopupSeen] = useState<Set<number>>(() => new Set());
  const [anchorRect, setAnchorRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null);
  const [cfgFn, setCfgFn] = useState<string>("parse_record");
  const lockRef = useRef(false);
  const prevHighlightRef = useRef<Element | null>(null);
  const highlightedElRef = useRef<Element | null>(null);
  const scrollingRef = useRef(false);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const safetyRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      setCfgFn((e as CustomEvent).detail as string);
    };
    window.addEventListener("cfg-fn-changed", handler);
    return () => window.removeEventListener("cfg-fn-changed", handler);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("tiny-dec-theme", theme);
    const root = document.documentElement.style;
    if (theme === "dark") {
      root.setProperty("--font-display", '"Syne", sans-serif');
      root.setProperty("--font-body", '"DM Sans", sans-serif');
      document.body.style.fontFamily = '"DM Sans", sans-serif';
    } else {
      root.setProperty("--font-display", '"Quicksand", sans-serif');
      root.setProperty("--font-body", '"Nunito", sans-serif');
      document.body.style.fontFamily = '"Nunito", sans-serif';
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => t === "light" ? "dark" : "light");
  }, []);

  const stageId = getStageId(current);
  const totalCallouts = getCalloutSteps(stageId);
  const hasPopup = !!getPopupStep(stageId);
  const popupAlreadySeen = popupSeen.has(current);
  const stage = current > 0 && current < TOTAL - 1 ? STAGES[current - 1] : null;

  // Determine what to show
  const showPopup = hasPopup && !popupAlreadySeen && subStep === 0;
  const isCalloutStep = subStep >= 1 && subStep <= totalCallouts;
  const currentCallout = isCalloutStep ? getCalloutStep(stageId, subStep - 1) : null;
  const isFree = subStep === -1 || subStep > totalCallouts;

  const calloutTargetFn = currentCallout?.target?.fn
    ?? (currentCallout?.target?.kind === "block" ? "parse_record" : undefined);
  const calloutFnMismatch = isCalloutStep && calloutTargetFn && cfgFn !== calloutTargetFn;

  const clearHighlight = useCallback(() => {
    if (prevHighlightRef.current) {
      prevHighlightRef.current.classList.remove("walkthrough-highlight");
      prevHighlightRef.current = null;
    }
    const prevInner = document.querySelector(".walkthrough-highlight-line");
    if (prevInner) prevInner.classList.remove("walkthrough-highlight-line");
    highlightedElRef.current = null;
  }, []);

  const goToStageRaw = useCallback((idx: number, skipAll?: boolean) => {
    if (lockRef.current) return;
    const clamped = Math.max(0, Math.min(TOTAL - 1, idx));
    if (clamped === current && !skipAll) return;
    lockRef.current = true;
    clearHighlight();
    setVisited((prev) => new Set(prev).add(current));
    setCurrent(clamped);
    setAnchorRect(null);

    const nextStageId = getStageId(clamped);
    const nextHasPopup = !!getPopupStep(nextStageId);
    const nextCallouts = getCalloutSteps(nextStageId);

    if (skipAll) {
      setSubStep(nextCallouts > 0 ? nextCallouts + 1 : -1);
    } else if (nextHasPopup && !popupSeen.has(clamped)) {
      setSubStep(0);
    } else if (nextCallouts > 0) {
      setSubStep(1);
    } else {
      setSubStep(-1);
    }

    setTimeout(() => { lockRef.current = false; }, 400);
  }, [current, clearHighlight, popupSeen]);

  const goToStage = useCallback((idx: number) => goToStageRaw(idx), [goToStageRaw]);

  const advanceSubStep = useCallback(() => {
    clearHighlight();
    setAnchorRect(null);
    if (showPopup) {
      // Mark popup as seen, move to first callout or free browse
      setPopupSeen((prev) => new Set(prev).add(current));
      if (totalCallouts > 0) {
        setSubStep(1);
      } else {
        setSubStep(-1);
        goToStage(current + 1);
      }
    } else if (isCalloutStep) {
      if (subStep < totalCallouts) {
        setSubStep(subStep + 1);
      } else {
        // Last callout done, go to free browse
        setSubStep(totalCallouts + 1);
      }
    } else {
      // Free browse - go to next stage
      goToStage(current + 1);
    }
  }, [showPopup, isCalloutStep, subStep, totalCallouts, goToStage, current, clearHighlight]);

  const prevSubStep = useCallback(() => {
    clearHighlight();
    setAnchorRect(null);
    if (showPopup) {
      // At popup, go to previous stage's last free-browse or callout
      if (current > 0) {
        const prevIdx = current - 1;
        const prevStageId = getStageId(prevIdx);
        const prevCallouts = getCalloutSteps(prevStageId);
        lockRef.current = true;
        setVisited((prev) => new Set(prev).add(current));
        setCurrent(prevIdx);
        setSubStep(prevCallouts > 0 ? prevCallouts : -1);
        setAnchorRect(null);
        setTimeout(() => { lockRef.current = false; }, 400);
      }
    } else if (isCalloutStep && subStep > 1) {
      setSubStep(subStep - 1);
    } else if (isCalloutStep && subStep === 1) {
      // At first callout, go to popup if not seen, or previous stage
      if (hasPopup && !popupAlreadySeen) {
        setSubStep(0);
      } else if (current > 0) {
        const prevIdx = current - 1;
        const prevStageId = getStageId(prevIdx);
        const prevCallouts = getCalloutSteps(prevStageId);
        lockRef.current = true;
        setVisited((prev) => new Set(prev).add(current));
        setCurrent(prevIdx);
        setSubStep(prevCallouts > 0 ? prevCallouts : -1);
        setAnchorRect(null);
        setTimeout(() => { lockRef.current = false; }, 400);
      }
    } else if (isFree && subStep > totalCallouts && totalCallouts > 0) {
      // At free browse after callouts, go back to last callout
      setSubStep(totalCallouts);
    } else {
      // Free browse without callouts, go to previous stage
      if (current > 0) {
        const prevIdx = current - 1;
        goToStageRaw(prevIdx, true);
      }
    }
  }, [showPopup, isCalloutStep, isFree, subStep, totalCallouts, hasPopup, popupAlreadySeen, current, clearHighlight, goToStageRaw]);

  // Auto-switch CFG function to match callout target (must run before mismatch guard)
  useEffect(() => {
    if (!currentCallout?.target) return;
    const target = currentCallout.target;
    const targetFn = target.fn ?? (target.kind === "block" ? "parse_record" : undefined);
    if (targetFn) {
      setCfgFn(targetFn);
      window.dispatchEvent(new CustomEvent("walkthrough-fn", { detail: targetFn }));
    }
  }, [currentCallout]);

  // Find and highlight target element for callouts
  useEffect(() => {
    if (!currentCallout || calloutFnMismatch) {
      clearHighlight();
      setAnchorRect(null);
      return;
    }
    const target = currentCallout.target;
    if (!target) {
      setAnchorRect(null);
      return;
    }

    const findElement = (): Element | null => {
      if (target.kind === "block" && target.address) {
        const blocks = document.querySelectorAll(".cfg-block");
        for (const b of blocks) {
          const header = b.querySelector(".cfg-block-header");
          if (header?.textContent?.includes(target.address)) return b;
        }
      } else if (target.kind === "instruction" && target.address) {
        const rows = document.querySelectorAll("[data-addr]");
        for (const r of rows) {
          if ((r as HTMLElement).dataset.addr === target.address) return r;
        }
      } else if (target.kind === "element" && target.selector) {
        return document.querySelector(target.selector);
      } else if (target.kind === "text-line" && target.lineIndex !== undefined) {
        return document.querySelector(".code-surface");
      }
      return null;
    };

    const highlightEl = (el: Element) => {
      clearHighlight();
      el.classList.add("walkthrough-highlight");
      prevHighlightRef.current = el;
      highlightedElRef.current = el;

      if (target.highlightLine) {
        const lines = el.querySelectorAll(".cfg-line");
        for (const line of lines) {
          if (line.textContent?.includes(target.highlightLine)) {
            line.classList.add("walkthrough-highlight-line");
            break;
          }
        }
      }

      setAnchorRect(null);
      scrollingRef.current = true;
      el.scrollIntoView({ behavior: "smooth", block: "center" });

      let settled = 0;
      let lastY = el.getBoundingClientRect().top;
      const finish = () => {
        scrollingRef.current = false;
        const rect = el.getBoundingClientRect();
        setAnchorRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height });
      };
      pollRef.current = setInterval(() => {
        const nowY = el.getBoundingClientRect().top;
        if (Math.abs(nowY - lastY) < 1) settled++;
        else settled = 0;
        lastY = nowY;
        if (settled >= 3) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          finish();
        }
      }, 60);
      safetyRef.current = setTimeout(() => {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        finish();
      }, 800);
    };

    let retries = 0;
    const tryFind = () => {
      const el = findElement();
      if (el) {
        highlightEl(el);
      } else if (retries < 10) {
        retries++;
        retryRef.current = setTimeout(tryFind, 150);
      } else {
        setAnchorRect(null);
      }
    };

    retryRef.current = setTimeout(tryFind, 100);
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
      if (safetyRef.current) clearTimeout(safetyRef.current);
    };
  }, [currentCallout, subStep, clearHighlight, calloutFnMismatch]);

  // Track highlighted element position with RAF for smooth callout following during scroll
  useEffect(() => {
    if (!isCalloutStep || calloutFnMismatch) return;

    let rafId: number;
    let lastTop = 0;
    let lastLeft = 0;

    const tick = () => {
      const el = highlightedElRef.current;
      if (el && !scrollingRef.current) {
        const rect = el.getBoundingClientRect();
        if (rect.top !== lastTop || rect.left !== lastLeft) {
          lastTop = rect.top;
          lastLeft = rect.left;
          setAnchorRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height });
        }
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [isCalloutStep, subStep, calloutFnMismatch]);

  // Keyboard handler when callout is hidden due to function mismatch
  useEffect(() => {
    if (!calloutFnMismatch) return;

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        advanceSubStep();
      } else if (e.key === "ArrowLeft" || e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        e.stopPropagation();
        prevSubStep();
      }
    };
    window.addEventListener("keydown", handler, true);
    return () => window.removeEventListener("keydown", handler, true);
  }, [calloutFnMismatch, advanceSubStep, prevSubStep]);

  // Keyboard handler for free-browse mode (no popup/callout visible)
  useEffect(() => {
    if (showPopup || isCalloutStep) return;

    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault();
        goToStage(current + 1);
      } else if (e.key === "ArrowLeft" || e.key === "Backspace") {
        e.preventDefault();
        if (current > 0) {
          goToStageRaw(current - 1, true);
        }
      } else if (e.key === "Home") { e.preventDefault(); goToStageRaw(0, true); }
      else if (e.key === "End") { e.preventDefault(); goToStageRaw(TOTAL - 1, true); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [goToStage, goToStageRaw, current, showPopup, isCalloutStep]);

  const totalStepsLabel = totalCallouts > 0
    ? `${subStep}/${totalCallouts}`
    : "";

  const fonts = fontsFor(theme);

  return (
    <ThemeContext.Provider value={theme}>
      <div className="app-layout" style={{ fontFamily: fonts.body }}>
        <ProgressBar current={current} visited={visited} onGo={(idx) => goToStageRaw(idx, true)} theme={theme} />
        <div className="main-panel">
          <MainPanel current={current} />
        </div>
        <Sidebar current={current} subStep={subStep} totalCallouts={totalCallouts} />

        {showPopup && (
          <StagePopup
            title={getPopupStep(stageId)?.title ?? stage?.name ?? ""}
            text={getPopupStep(stageId)?.text ?? ""}
            phase={stage?.phase ?? null}
            onNext={advanceSubStep}
            onPrev={prevSubStep}
          />
        )}

        {currentCallout && !calloutFnMismatch && (
          <GuidedCallout
            text={currentCallout.text}
            color={currentCallout.color ?? "var(--accent)"}
            anchorRect={anchorRect}
            side={currentCallout.target?.side ?? "right"}
            stepLabel={totalStepsLabel}
            onNext={advanceSubStep}
            onPrev={prevSubStep}
          />
        )}

        {isFree && stage && !showPopup && !currentCallout && (
          <div className="free-browse-hint" style={{ fontFamily: fonts.body }}>
            <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f50e.svg" alt="" style={{ width: 16, height: 16 }} />
            <span>Explore this stage freely</span>
            <span className="free-browse-hint-sep" />
            <span>Press <kbd>→</kbd> to continue</span>
          </div>
        )}

        <button className="theme-toggle" onClick={toggleTheme} style={{ fontFamily: fonts.body }}>
          {theme === "light" ? (
            <>
              <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f5a5.svg" alt="" />
              Tech Mode
            </>
          ) : (
            <>
              <img src="https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg/1f31f.svg" alt="" />
              Cute Mode
            </>
          )}
        </button>
      </div>
    </ThemeContext.Provider>
  );
}

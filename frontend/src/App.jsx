import { useState, useEffect, useRef, useMemo } from "react";
import axios from "axios";
axios.defaults.baseURL = import.meta.env.VITE_API_URL || "";
import MapView from "./components/MapView";
import Sidebar from "./components/Sidebar";
import FilterBar, { ROLE_KEYWORDS, EXP_RANGES } from "./components/FilterBar";
import useBookmarks from "./hooks/useBookmarks";
import "./App.css";

const SCRAPE_INTERVAL_MS = 10 * 60 * 1000; // repeat every 10 min
const POLL_INTERVAL_MS   = 5000;            // refresh pins every 5s while scraping
const INITIAL_DELAY_MS   = 10000;           // start scraping 10s after load

export default function App() {
  const [companies, setCompanies]       = useState([]);
  const [selected, setSelected]         = useState(null);
  const [loading, setLoading]           = useState(true);
  const [scrapeActive, setScrapeActive] = useState(false);
  const [search, setSearch]             = useState("");
  const [loadError, setLoadError]       = useState(false);
  const [locationDenied, setLocationDenied] = useState(false);
  const [filters, setFilters]           = useState({ role: "All", expIndex: 0, sources: [] });
  const [showSaved, setShowSaved]       = useState(false);
  const { bookmarks, toggle: toggleBookmark, isBookmarked } = useBookmarks();

  // Ref so runScrapeCycle can schedule itself without stale closures
  const cycleTimerRef = useRef(null);
  const pollRef       = useRef(null);

  // ── initial load + auto-scrape ─────────────────────────────────────────────
  useEffect(() => {
    fetchCompanies();

    const startTimer = setTimeout(() => runScrapeCycle(), INITIAL_DELAY_MS);

    return () => {
      clearTimeout(startTimer);
      clearTimeout(cycleTimerRef.current);
      clearInterval(pollRef.current);
    };
  }, []);

  async function fetchCompanies() {
    try {
      const { data } = await axios.get("/api/companies");
      setCompanies(data);
      setLoadError(false);

      const stats = await axios.get("/api/stats").then(r => r.data).catch(() => null);
      if (!stats) return;
      const total = Object.values(stats).reduce((a, b) => a + b, 0);
      console.group("%c Ahmedabad Jobs — Platform Breakdown", "color:#0fbcf9;font-weight:bold;font-size:14px");
      Object.entries(stats)
        .sort((a, b) => b[1] - a[1])
        .forEach(([source, count]) => {
          const colors = { linkedin: "#0d47a1", internshala: "#e65100", timesjobs: "#6a1b9a", shine: "#1b5e20" };
          const color = colors[source] || "#555";
          console.log(`%c ${source.padEnd(14)} %c ${count} jobs`, `color:${color};font-weight:bold`, "color:#333");
        });
      console.log(`%c ${"TOTAL".padEnd(14)} %c ${total} jobs`, "color:#333;font-weight:bold", "color:#333;font-weight:bold");
      console.groupEnd();
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }

  async function runScrapeCycle() {
    setScrapeActive(true);
    console.log("[AutoScrape] Starting scrape cycle…");

    try {
      // Check what's already running so we don't double-trigger
      const [ls, ss] = await Promise.allSettled([
        axios.get("/api/scrape/linkedin/status"),
        axios.get("/api/scrape/status"),
      ]);
      const linkedinRunning = ls.value?.data?.running ?? false;
      const scrapeRunning   = ss.value?.data?.running ?? false;

      if (!linkedinRunning) axios.post("/api/scrape/linkedin?queries=3").catch(() => {});
      if (!scrapeRunning)   axios.post("/api/scrape?pages=3").catch(() => {});

      // Poll: refresh companies (live pins) + watch for completion
      pollRef.current = setInterval(async () => {
        fetchCompanies(); // update pins as new jobs arrive

        const [lStatus, sStatus] = await Promise.allSettled([
          axios.get("/api/scrape/linkedin/status"),
          axios.get("/api/scrape/status"),
        ]);
        const lDone = lStatus.value?.data?.running === false;
        const sDone = sStatus.value?.data?.running === false;

        if (lDone && sDone) {
          clearInterval(pollRef.current);
          setScrapeActive(false);
          fetchCompanies(); // final refresh
          console.log("[AutoScrape] Cycle done. Next in 10 min.");
          cycleTimerRef.current = setTimeout(() => runScrapeCycle(), SCRAPE_INTERVAL_MS);
        }
      }, POLL_INTERVAL_MS);

    } catch (e) {
      console.warn("[AutoScrape] Error:", e.message);
      setScrapeActive(false);
      cycleTimerRef.current = setTimeout(() => runScrapeCycle(), SCRAPE_INTERVAL_MS);
    }
  }

  // ── dynamic filter options — derived from full company list ───────────────
  const availableSources = useMemo(
    () => new Set(companies.flatMap((c) => c.sources || [])),
    [companies]
  );

  const availableRoles = useMemo(() => {
    const roles = new Set(["All"]);
    companies.forEach((c) => {
      Object.entries(ROLE_KEYWORDS).forEach(([role, keywords]) => {
        if ((c.titles || []).some((t) => keywords.some((kw) => t.toLowerCase().includes(kw)))) {
          roles.add(role);
        }
      });
    });
    return roles;
  }, [companies]);

  // ── filter helpers ─────────────────────────────────────────────────────────
  function parseExpYears(expStr) {
    if (!expStr) return null;
    const nums = expStr.match(/\d+/g);
    if (!nums) return null;
    return parseFloat(nums[0]);
  }

  const filtered = companies.filter((c) => {
    if (showSaved && !isBookmarked(c.id)) return false;
    if (!c.name.toLowerCase().includes(search.toLowerCase())) return false;

    if (filters.sources.length > 0) {
      if (!(c.sources || []).some((s) => filters.sources.includes(s))) return false;
    }

    if (filters.role !== "All") {
      const keywords = ROLE_KEYWORDS[filters.role] || [];
      if (!(c.titles || []).some((t) => keywords.some((kw) => t.toLowerCase().includes(kw)))) return false;
    }

    const expRange = EXP_RANGES[filters.expIndex];
    if (expRange && expRange.min >= 0) {
      if (!(c.experiences || []).some((exp) => {
        const yrs = parseExpYears(exp);
        return yrs !== null && yrs >= expRange.min && yrs <= expRange.max;
      })) return false;
    }

    return true;
  });

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 className="logo">Ahmedabad Jobs</h1>
          <span className="count">{companies.length} hiring</span>
          {scrapeActive && (
            <span className="scrape-indicator" title="Fetching new jobs…">
              <span className="scrape-dot" />
              Live
            </span>
          )}
        </div>
        <div className="header-right">
          <div className="search-wrap">
            <span className="material-symbols-outlined">search</span>
            <input
              className="search"
              placeholder="Search company..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {bookmarks.size > 0 && (
            <span className="bookmark-count" onClick={() => setShowSaved(v => !v)}>
              ★ {bookmarks.size} saved
            </span>
          )}
        </div>
      </header>

      {loadError && (
        <div className="error-banner">
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>wifi_off</span>
          Could not load companies — backend may be offline.
          <button onClick={() => { setLoadError(false); fetchCompanies(); }} className="error-retry">Retry</button>
          <button onClick={() => setLoadError(false)} className="error-dismiss">✕</button>
        </div>
      )}
      {locationDenied && (
        <div className="location-banner">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>location_off</span>
          Enable location to see nearby jobs
          <button onClick={() => setLocationDenied(false)} className="error-dismiss">✕</button>
        </div>
      )}

      <div className="body">
        <Sidebar
          companies={filtered}
          selected={selected}
          onSelect={setSelected}
          loading={loading}
          filters={filters}
          onFilterChange={setFilters}
          bookmarkCount={bookmarks.size}
          showSaved={showSaved}
          onToggleSaved={() => setShowSaved((v) => !v)}
          isBookmarked={isBookmarked}
          onToggleBookmark={toggleBookmark}
          availableRoles={availableRoles}
          availableSources={availableSources}
        />
        <MapView
          companies={filtered}
          selected={selected}
          onSelect={setSelected}
          onLocationDenied={() => setLocationDenied(true)}
          isBookmarked={isBookmarked}
        />
      </div>

      <div className="disclaimer">
        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>info</span>
        Pin locations are approximate and do not represent exact company addresses. Jobs data is scraped from public listings.
      </div>
    </div>
  );
}

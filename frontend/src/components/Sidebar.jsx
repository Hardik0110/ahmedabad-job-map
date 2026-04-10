import { useState } from "react";
import axios from "axios";
import "./Sidebar.css";
import FilterBar from "./FilterBar";

const MARKER_COLORS = [
  "#ff4757", "#ff6b35", "#ffd32a", "#0be881", "#05c46b",
  "#0fbcf9", "#575fcf", "#ff5e57", "#00d8d6", "#ff4d4d",
  "#ffdd59", "#34e7e4", "#ef5777", "#f53b57", "#3c40c4",
  "#0652dd", "#1289a7", "#c4e538", "#ffc312", "#ed4c67",
];

function colorForName(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return MARKER_COLORS[Math.abs(hash) % MARKER_COLORS.length];
}

const SOURCE_COLORS = {
  linkedin:    { bg: "#e8f0fe", color: "#1a56db" },
  internshala: { bg: "#fff3e0", color: "#e65100" },
  timesjobs:   { bg: "#f3e8ff", color: "#7c3aed" },
  shine:       { bg: "#e8f5e9", color: "#2e7d32" },
  seed:        { bg: "#f1f3f4", color: "#5f6368" },
};

function SourceBadge({ source }) {
  const s = SOURCE_COLORS[source] || { bg: "#f1f3f4", color: "#5f6368" };
  return (
    <span className="source-badge" style={{ background: s.bg, color: s.color }}>
      {source}
    </span>
  );
}

function CompanyCard({ c, isActive, onSelect, isBookmarked, onToggleBookmark }) {
  const [jobs, setJobs] = useState(null);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const color = colorForName(c.name);

  async function handleClick() {
    onSelect(isActive ? null : c); // fly map to pin
    if (!isActive) {
      if (jobs === null) {
        setLoadingJobs(true);
        try {
          const { data } = await axios.get(`/api/companies/${c.id}/jobs`);
          setJobs(data.jobs || []);
        } catch {
          setJobs([]);
        } finally {
          setLoadingJobs(false);
        }
      }
    }
  }

  return (
    <div className={`company-card ${isActive ? "active" : ""}`} onClick={handleClick}>
      {/* Card header row */}
      <div className="card-header-row">
        <div className="company-avatar" style={{ background: color + "18" }}>
          {c.domain ? (
            <>
              <img
                src={`https://www.google.com/s2/favicons?sz=128&domain=${c.domain}`}
                alt={c.name}
                onError={(e) => {
                  e.target.style.display = "none";
                  if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex";
                }}
              />
              <span style={{ display: "none", width: "100%", height: "100%", alignItems: "center", justifyContent: "center", color, fontWeight: 800, fontSize: "18px", fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
                {c.name.charAt(0).toUpperCase()}
              </span>
            </>
          ) : (
            <span style={{ color, fontWeight: 800, fontSize: "18px", fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
              {c.name.charAt(0).toUpperCase()}
            </span>
          )}
        </div>

        <div className="company-info">
          <p className="company-name">{c.name}</p>
          <p className="company-location">
            <span className="material-symbols-outlined" style={{ fontSize: 13, flexShrink: 0 }}>location_on</span>
            <span className="loc-text">{c.location_text}</span>
          </p>
          <div className="company-meta">
            <span className="job-count">{c.job_count} openings</span>
          </div>
        </div>

        <button
          className={`bookmark-btn ${isBookmarked(c.id) ? "bookmarked" : ""}`}
          onClick={(e) => { e.stopPropagation(); onToggleBookmark(c.id); }}
          title={isBookmarked(c.id) ? "Remove bookmark" : "Bookmark"}
        >
          {isBookmarked(c.id) ? "★" : "☆"}
        </button>
        <div className="company-arrow">
          <span className="material-symbols-outlined">
            {isActive ? "expand_less" : "expand_more"}
          </span>
        </div>
      </div>

      {/* Inline job list — shown when card is active */}
      {isActive && (
        <div className="card-jobs" onClick={(e) => e.stopPropagation()}>
          {loadingJobs && <p className="jobs-loading">Loading jobs…</p>}
          {!loadingJobs && jobs && jobs.length === 0 && (
            <p className="jobs-empty">No job details available.</p>
          )}
          {!loadingJobs && jobs && jobs.map((job) => (
            <a
              key={job.id}
              href={job.url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="job-row"
            >
              <div className="job-row-left">
                <span className="job-title">{job.title}</span>
                {job.experience && (
                  <span className="job-exp">
                    <span className="material-symbols-outlined" style={{ fontSize: 11 }}>schedule</span>
                    {job.experience}
                  </span>
                )}
              </div>
              <div className="job-row-right">
                <SourceBadge source={job.source} />
                {job.url && (
                  <span className="material-symbols-outlined job-link-icon">open_in_new</span>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ companies, selected, onSelect, loading, filters, onFilterChange, bookmarkCount, showSaved, onToggleSaved, isBookmarked, onToggleBookmark, availableRoles, availableSources }) {
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  const activeFilterCount = [
    filters.role !== "All" ? 1 : 0,
    filters.expIndex !== 0 ? 1 : 0,
    filters.sources.length,
  ].reduce((a, b) => a + b, 0);

  if (loading) {
    return (
      <aside className="sidebar sheet-collapsed">
        <p className="sidebar-empty">Loading...</p>
      </aside>
    );
  }

  const mobileHandle = (
    <div className="sheet-handle" onClick={() => setSheetExpanded(v => !v)}>
      <div className="sheet-pill" />
      <div className="sheet-handle-row">
        <span className="sidebar-title" style={{ fontSize: 18 }}>Active Hiring</span>
        <span className="sidebar-badge">{companies.length}</span>
        <button
          className={`mobile-filter-btn ${activeFilterCount > 0 ? "has-filters" : ""}`}
          onClick={(e) => { e.stopPropagation(); setShowMobileFilters(v => !v); }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>tune</span>
          Filter {activeFilterCount > 0 ? `(${activeFilterCount})` : ""}
        </button>
      </div>
    </div>
  );

  const mobileFilterModal = showMobileFilters && (
    <div className="mobile-filter-modal">
      <FilterBar filters={filters} onChange={onFilterChange} bookmarkCount={bookmarkCount || 0} showSaved={showSaved} onToggleSaved={onToggleSaved} />
      <button className="mobile-filter-close" onClick={() => setShowMobileFilters(false)}>Done</button>
    </div>
  );

  if (companies.length === 0) {
    return (
      <aside className={`sidebar ${sheetExpanded ? "sheet-expanded" : "sheet-collapsed"}`}>
        {mobileHandle}
        {mobileFilterModal}
        <div className="desktop-only">
          <div className="sidebar-header">
            <div className="sidebar-title-row">
              <div>
                <h2 className="sidebar-title">Active Hiring</h2>
                <p className="sidebar-subtitle">Top companies in Ahmedabad</p>
              </div>
            </div>
          </div>
          <FilterBar
            filters={filters}
            onChange={onFilterChange}
            bookmarkCount={bookmarkCount || 0}
            showSaved={showSaved}
            onToggleSaved={onToggleSaved}
            availableRoles={availableRoles}
            availableSources={availableSources}
          />
        </div>
        <div className="empty-state">
          <span className="material-symbols-outlined empty-state-icon">search_off</span>
          <p className="empty-state-msg">No companies match your filters.</p>
          {activeFilterCount > 0 && (
            <button
              className="empty-state-reset"
              onClick={() => onFilterChange({ role: "All", expIndex: 0, sources: [] })}
            >
              ✕ Clear all filters
            </button>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className={`sidebar ${sheetExpanded ? "sheet-expanded" : "sheet-collapsed"}`}>
      {mobileHandle}
      {mobileFilterModal}

      <div className="desktop-only">
        <div className="sidebar-header">
          <div className="sidebar-title-row">
            <div>
              <h2 className="sidebar-title">Active Hiring</h2>
              <p className="sidebar-subtitle">Top companies in Ahmedabad today</p>
            </div>
            <span className="sidebar-badge">{companies.length} Companies</span>
          </div>
        </div>

        <FilterBar
          filters={filters}
          onChange={onFilterChange}
          bookmarkCount={bookmarkCount || 0}
          showSaved={showSaved}
          onToggleSaved={onToggleSaved}
          availableRoles={availableRoles}
          availableSources={availableSources}
        />
      </div>

      <div className="sidebar-list">
        {companies.map((c) => (
          <CompanyCard
            key={c.id}
            c={c}
            isActive={selected?.id === c.id}
            onSelect={onSelect}
            isBookmarked={isBookmarked}
            onToggleBookmark={onToggleBookmark}
          />
        ))}
      </div>
    </aside>
  );
}

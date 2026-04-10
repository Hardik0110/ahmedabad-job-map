// frontend/src/components/FilterBar.jsx
import "./FilterBar.css";

const ROLE_KEYWORDS = {
  Frontend: ["react", "vue", "angular", "frontend", "ui", "next", "svelte"],
  Backend: ["node", "python", "django", "fastapi", "java", "backend", "golang", "ruby", "php", "spring"],
  "Full Stack": ["full stack", "fullstack", "mern", "mean"],
  Mobile: ["android", "ios", "flutter", "react native", "mobile"],
  DevOps: ["devops", "cloud", "aws", "docker", "kubernetes", "ci/cd", "sre"],
  Data: ["data", "ml", "machine learning", "ai", "analyst", "spark", "tableau"],
  Design: ["figma", "ux", "ui design", "product design", "designer"],
};

const SOURCES = ["linkedin", "internshala", "timesjobs", "shine"];

const EXP_RANGES = [
  { label: "Any", min: -1, max: 999 },
  { label: "Fresher (0–1yr)", min: 0, max: 1 },
  { label: "Junior (1–3yr)", min: 1, max: 3 },
  { label: "Mid (3–6yr)", min: 3, max: 6 },
  { label: "Senior (6yr+)", min: 6, max: 999 },
];

export { ROLE_KEYWORDS, SOURCES, EXP_RANGES };

export default function FilterBar({
  filters,
  onChange,
  bookmarkCount,
  showSaved,
  onToggleSaved,
  availableRoles,   // Set<string> | undefined — roles with actual data
  availableSources, // Set<string> | undefined — sources with actual data
}) {
  const { role, expIndex, sources } = filters;

  function toggleSource(src) {
    const next = sources.includes(src)
      ? sources.filter((s) => s !== src)
      : [...sources, src];
    onChange({ ...filters, sources: next });
  }

  const hasActiveFilters = role !== "All" || expIndex !== 0 || sources.length > 0;

  // Only show role chips that have matching data (or all if data not yet loaded)
  const visibleRoles = ["All", ...Object.keys(ROLE_KEYWORDS)].filter(
    (r) => !availableRoles || availableRoles.size === 0 || availableRoles.has(r)
  );

  // Only show source chips that have matching data
  const visibleSources = SOURCES.filter(
    (s) => !availableSources || availableSources.size === 0 || availableSources.has(s)
  );

  return (
    <div className="filter-bar">
      {/* Role chips — only show roles with actual jobs */}
      <div className="filter-row">
        <div className="filter-chips scrollable">
          {visibleRoles.map((r) => (
            <button
              key={r}
              className={`chip ${role === r ? "chip-active" : ""}`}
              onClick={() => onChange({ ...filters, role: r })}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Experience + Source row */}
      <div className="filter-row filter-row-bottom">
        <select
          className="exp-select"
          value={expIndex}
          onChange={(e) => onChange({ ...filters, expIndex: Number(e.target.value) })}
        >
          {EXP_RANGES.map((r, i) => (
            <option key={r.label} value={i}>{r.label}</option>
          ))}
        </select>

        <div className="filter-chips">
          {bookmarkCount > 0 && (
            <button
              className={`chip chip-source ${showSaved ? "chip-active chip-saved" : ""}`}
              onClick={onToggleSaved}
              style={showSaved ? { background: "#f59e0b", borderColor: "#f59e0b" } : { borderColor: "#f59e0b", color: "#92400e" }}
            >
              ★ Saved ({bookmarkCount})
            </button>
          )}
          {visibleSources.map((src) => (
            <button
              key={src}
              className={`chip chip-source ${sources.includes(src) ? "chip-active" : ""}`}
              onClick={() => toggleSource(src)}
            >
              {src}
            </button>
          ))}
        </div>

        {hasActiveFilters && (
          <button
            className="chip chip-reset"
            onClick={() => onChange({ role: "All", expIndex: 0, sources: [] })}
          >
            ✕ Reset
          </button>
        )}
      </div>
    </div>
  );
}

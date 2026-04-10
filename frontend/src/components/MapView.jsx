import { useState, useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import axios from "axios";
import "./MapView.css";

// Prevent Leaflet from trying to load default marker images (breaks with Vite)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({ iconUrl: "", shadowUrl: "", iconRetinaUrl: "" });

// Ahmedabad center
const CENTER = [23.0225, 72.5714];
const ZOOM = 12;

// CartoDB Voyager — warm beige base, colored roads, parks, water. Clean product look.
const TILE_URL =
  "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const TILE_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>';

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

function makeIcon(letter, name = "", active = false, domain = "", bookmarked = false) {
  const color = colorForName(name);
  const isMobile = window.innerWidth <= 768;
  const w = active ? 42 : (isMobile ? 40 : 34);
  const h = active ? 54 : (isMobile ? 52 : 44);
  const inner = active ? 28 : 22;
  const logoUrl = domain ? `https://www.google.com/s2/favicons?sz=64&domain=${domain}` : "";
  const scale = active ? `transform:scale(1.15);` : "";

  const html = `
    <div style="position:relative;width:${w}px;height:${h}px;${scale}filter:drop-shadow(0 3px 6px rgba(0,0,0,0.25));">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 130" width="${w}" height="${h}">
        <path d="M50 0 C22.4 0 0 22.4 0 50 C0 77.6 50 130 50 130 C50 130 100 77.6 100 50 C100 22.4 77.6 0 50 0Z" fill="${color}" ${bookmarked ? 'stroke="#f59e0b" stroke-width="6"' : ''}/>
        <circle cx="50" cy="47" r="26" fill="rgba(255,255,255,0.2)"/>
        <circle cx="50" cy="47" r="22" fill="white"/>
      </svg>
      <div style="
        position:absolute;
        top:${Math.round(h * 0.16)}px;
        left:50%;
        transform:translateX(-50%);
        width:${inner}px;
        height:${inner}px;
        display:flex;align-items:center;justify-content:center;
        overflow:hidden;border-radius:50%;
      ">
        ${logoUrl
          ? `<img src="${logoUrl}" style="width:100%;height:100%;object-fit:contain;padding:1px;"
               onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex'"/>
             <span style="display:none;width:100%;height:100%;align-items:center;justify-content:center;font-family:-apple-system,sans-serif;font-size:${Math.round(inner * 0.55)}px;font-weight:800;color:${color};">${letter}</span>`
          : `<span style="display:flex;width:100%;height:100%;align-items:center;justify-content:center;font-family:-apple-system,sans-serif;font-size:${Math.round(inner * 0.55)}px;font-weight:800;color:${color};">${letter}</span>`
        }
      </div>
    </div>`;

  return L.divIcon({
    html,
    className: "",
    iconSize: [w, h],
    iconAnchor: [w / 2, h],
    popupAnchor: [0, -h],
  });
}

// Force Leaflet to recalculate tile grid after mount (fixes mobile blank tiles)
function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    // First pass: immediate, catches most cases
    map.invalidateSize({ animate: false });
    // Second pass: after CSS transitions finish (bottom sheet, etc.)
    const t1 = setTimeout(() => map.invalidateSize({ animate: false }), 150);
    const t2 = setTimeout(() => map.invalidateSize({ animate: false }), 400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);
  return null;
}

// Get user's location on first load, fly there and show radius
function UserLocation({ onLocated, onLocationDenied }) {
  const map = useMap();
  const located = useRef(false);

  useEffect(() => {
    if (located.current) return;
    located.current = true;

    if (!navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        onLocated([latitude, longitude]);
        map.flyTo([latitude, longitude], 15, { duration: 1.2 });
      },
      () => {
        if (onLocationDenied) onLocationDenied();
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, []);

  return null;
}

// Fly to selected company
function FlyTo({ selected }) {
  const map = useMap();
  useEffect(() => {
    if (selected?.latitude && selected?.longitude) {
      map.flyTo([selected.latitude, selected.longitude], 15, { duration: 0.8 });
    }
  }, [selected]);
  return null;
}

// Fetch jobs inline in popup
function CompanyMarkerWithJobs({ company, isSelected, onSelect, isBookmarked }) {
  const icon = makeIcon(company.name.charAt(0).toUpperCase(), company.name, isSelected, company.domain, isBookmarked);
  const jobsRef = useRef([]);
  const markerRef = useRef(null);

  async function loadJobs() {
    if (jobsRef.current.length > 0) return;
    try {
      const { data } = await axios.get(`/api/companies/${company.id}/jobs`);
      jobsRef.current = data.jobs;
    } catch {}
  }

  // When selected from sidebar: open popup + trigger bounce on the icon element
  useEffect(() => {
    if (isSelected && markerRef.current) {
      markerRef.current.openPopup();
      loadJobs();
      // Bounce the icon element
      const el = markerRef.current.getElement();
      if (el) {
        el.classList.remove("pin-bounce");
        void el.offsetWidth; // reflow to restart animation
        el.classList.add("pin-bounce");
      }
    }
  }, [isSelected]);

  return (
    <Marker
      ref={markerRef}
      position={[company.latitude, company.longitude]}
      icon={icon}
      eventHandlers={{
        click: () => {
          onSelect(isSelected ? null : company);
          loadJobs();
        },
        popupopen: () => loadJobs(),
      }}
    >
      <Popup maxWidth={290} className="company-popup">
        <PopupContent company={company} jobsRef={jobsRef} />
      </Popup>
    </Marker>
  );
}

function PopupContent({ company, jobsRef }) {
  const jobs = jobsRef.current;
  return (
    <div>
      <div className="popup-header">
        <div className="popup-avatar">
          {company.domain ? (
            <>
              <img
                src={`https://www.google.com/s2/favicons?sz=128&domain=${company.domain}`}
                alt={company.name}
                onError={(e) => { e.target.style.display = "none"; if (e.target.nextElementSibling) e.target.nextElementSibling.style.display = "flex"; }}
                style={{ width: "100%", height: "100%", objectFit: "contain", padding: "3px", borderRadius: "8px" }}
              />
              <span style={{ display: "none", width: "100%", height: "100%", alignItems: "center", justifyContent: "center", color: colorForName(company.name), fontWeight: 800, fontSize: "14px" }}>
                {company.name.charAt(0).toUpperCase()}
              </span>
            </>
          ) : <span style={{ color: colorForName(company.name), fontWeight: 800, fontSize: "14px" }}>{company.name.charAt(0).toUpperCase()}</span>}
        </div>
        <div>
          <p className="popup-name">{company.name}</p>
          <p className="popup-location">{company.location_text}</p>
        </div>
      </div>
      <p className="popup-count">{company.job_count} open positions</p>
      {jobs.length > 0 && (
        <ul className="popup-jobs">
          {jobs.map((j) => (
            <li key={j.id}>
              {j.url ? (
                <a href={j.url} target="_blank" rel="noreferrer">
                  {j.title}
                </a>
              ) : (
                <span>{j.title}</span>
              )}
              {j.experience && <span className="exp"> · {j.experience}</span>}
              <span
                className="source-tag"
                style={{
                  background:
                    j.source === "naukri"
                      ? "#fff3e0"
                      : j.source === "linkedin"
                      ? "#e3f2fd"
                      : "#e8f5e9",
                  color:
                    j.source === "naukri"
                      ? "#e65100"
                      : j.source === "linkedin"
                      ? "#0d47a1"
                      : "#1b5e20",
                }}
              >
                {j.source}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function userDotIcon() {
  return L.divIcon({
    html: `<div style="
      width: 18px; height: 18px;
      background: #2e5bff;
      border: 3px solid #fff;
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(46,91,255,0.3), 0 2px 8px rgba(0,0,0,0.2);
    "></div>`,
    className: "",
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

export default function MapView({ companies, selected, onSelect, onLocationDenied, isBookmarked }) {
  const [userPos, setUserPos] = useState(null);

  return (
    <div className="map-wrapper">
      <MapContainer
        center={CENTER}
        zoom={ZOOM}
        className="map"
        zoomControl={true}
        preferCanvas={false}
      >
        <TileLayer
          url={TILE_URL}
          attribution={TILE_ATTR}
          updateWhenIdle={false}
          updateWhenZooming={false}
          keepBuffer={4}
          detectRetina={true}
        />
        <InvalidateSize />
        <UserLocation onLocated={setUserPos} onLocationDenied={onLocationDenied} />
        <FlyTo selected={selected} />

        {/* User location radius + dot */}
        {userPos && (
          <>
            <Circle
              center={userPos}
              radius={2500}
              pathOptions={{
                color: "#2e5bff",
                weight: 1.5,
                fillColor: "#2e5bff",
                fillOpacity: 0.06,
                dashArray: "6 4",
              }}
            />
            <Marker position={userPos} icon={userDotIcon()} zIndexOffset={1000} />
          </>
        )}

        {companies
          .filter((c) => c.latitude && c.longitude)
          .map((c) => (
            <CompanyMarkerWithJobs
              key={c.id}
              company={c}
              isSelected={selected?.id === c.id}
              onSelect={onSelect}
              isBookmarked={isBookmarked ? isBookmarked(c.id) : false}
            />
          ))}
      </MapContainer>
    </div>
  );
}

# JOB INTEL — GCC Job Intelligence Platform
## Source Code & Frontend Specification

### Overview
Automated job aggregation platform for Saudi Arabia / GCC.
- **351 Saudi government entities** (from uploaded spreadsheet) + 3 job boards
- Scraper runs **daily at 9am GST** via GitHub Actions (free)
- Frontend is a single `index.html` that loads `jobs.json`

---

## FOR THE AI BUILDING THE FRONTEND

### Task
Build `index.html` — a single-file web dashboard that:
1. On page load, fetches `jobs.json` from the same directory
2. Displays jobs in a filterable, searchable dashboard
3. Saves user actions (Save/Apply/Dismiss) to localStorage
4. Dark theme, mobile responsive

### jobs.json Schema
```json
{
  "updated": "2026-04-08T09:00:00",
  "count": 150,
  "jobs": [
    {
      "id": "a1b2c3d4e5f6",
      "src": "bayt | linkedin | careerjet | gov | pif",
      "t": "Senior Manager, Innovation",
      "co": "ALJ Enterprises",
      "cy": "Jeddah",
      "ct": "SA",
      "ca": "Strategy & Consulting | Technology & Product | Operations & Execution | Finance & Investment",
      "tg": ["innovation", "culture-change", "intrapreneurship"],
      "sg": ["new-team-building", "expansion", "giga-project", "government-mandate", "high-growth", "digital-native", "leadership-change", "restructuring"],
      "sn": "executive | director | senior | mid | junior",
      "sc": 0.86,
      "sm": "One-sentence summary of the role...",
      "st": "new | interested | applied | interview | offer | rejected",
      "dt": "2026-04-07",
      "u": "https://www.bayt.com/en/..."
    }
  ]
}
```

### Required Views (8 total)
| View | Sidebar Label | Filter Logic |
|------|--------------|--------------|
| Inbox | 📥 Inbox | `st === "new"` |
| Watchlist | ⭐ Saved | `st === "interested"` |
| Applied | 📝 Applied | `st === "applied"` |
| Interview | 🎤 Interview | `st === "interview"` |
| Gov & PIF | 🏛 Gov & PIF | `src === "gov" or src === "pif"` |
| All Jobs | 📊 All | no filter |
| Signals | 📡 Signals | `sg.length > 0` |
| Analytics | 📈 Analytics | Charts: by category, status, company, score distribution |

### Required UI Features

**Header:** Logo "JOB INTEL" + badges (LIVE, GCC, 351 ENTITIES) + search bar + sort dropdown

**Stats Bar:** Counts for New, Saved, Applied, Interview, High Match (score≥0.85), Gov & PIF

**Sidebar:** Navigation buttons (8 views with counts) + filter checkboxes for Category (4 options) and Seniority (4 options)

**Job Card:** Shows title, status badge, source icon, company (bold), city, days ago, up to 3 tags, signal count badge, score bar (colored: green≥0.85, yellow≥0.7, gray below), action buttons (Save/Apply/Dismiss for new jobs)

**Detail Panel:** Opens on click. Shows: title, company, city, employment type, posted date, source. Score bar with large number. AI Summary box (purple tint). Classification (category + seniority badges, all tags, all signals with emoji labels). Status selector (6 buttons). "Open Source" link to original posting.

**Analytics View:** Bar charts for: jobs by category, jobs by status, score distribution (0.9+, 0.8-0.9, 0.7-0.8, <0.7), top 10 companies. Use pure CSS bars (no chart library needed).

### Data Flow on Page Load
```javascript
// 1. Try to load fresh jobs.json
fetch("jobs.json?" + Date.now())
  .then(r => r.json())
  .then(data => {
    // 2. Merge with localStorage statuses
    const saved = JSON.parse(localStorage.getItem("ji") || "[]");
    const statusMap = {};
    saved.forEach(j => { if (j.st !== "new") statusMap[j.id] = j.st; });
    data.jobs.forEach(j => { if (statusMap[j.id]) j.st = statusMap[j.id]; });
    // 3. Render
    jobs = data.jobs;
    localStorage.setItem("ji", JSON.stringify(jobs));
    render();
  })
  .catch(() => {
    // Fallback to localStorage
    jobs = JSON.parse(localStorage.getItem("ji") || "[]");
    render();
  });
```

### On Status Change
```javascript
function setStatus(jobId, newStatus) {
  jobs = jobs.map(j => j.id === jobId ? {...j, st: newStatus} : j);
  localStorage.setItem("ji", JSON.stringify(jobs));
  render();
}
```

### Design Tokens
```
Background:     #0b0f19 (app), #0c1120 (sidebar/detail), #111827 (cards)
Border:         rgba(148,163,184,0.07)
Text primary:   #e2e8f0
Text secondary: #94a3b8
Text muted:     #64748b
Purple accent:  #a78bfa (active nav, status badges)
Blue:           #60a5fa (tags, links)
Green:          #34d399 (high score, signals)
Yellow:         #eab308 (medium score)
Red:            #ef4444 (dismiss, rejected)

Status colors:
  new: #3b82f6, interested: #eab308, applied: #8b5cf6
  interview: #10b981, offer: #22c55e, rejected: #6b7280

Font: system-ui or 'DM Sans'
Monospace: monospace or 'JetBrains Mono' (for scores, counts)
```

### Source Icons
```
bayt → "B"  |  linkedin → "in"  |  careerjet → "CJ"
gov → "🏛"  |  pif → "PIF"
```

### Signal Labels
```
giga-project → 🏗 Giga-Project
expansion → 🟡 Expansion
new-team-building → 🟢 New Team
leadership-change → 🔴 Leadership
government-mandate → 🏛 Gov Mandate
high-growth → 🚀 Growth
digital-native → 💻 Digital
restructuring → 🔄 Restructure
```

---

## DEPLOYMENT

### GitHub Setup
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/YOU/job-intel.git
git push -u origin main
```

### Enable GitHub Pages
Settings → Pages → Branch: main → Save

### Enable Daily Scraper
Actions → "Daily Job Scrape" → Enable → Run workflow

**Cost: $0/month** (GitHub free tier)

---

## FILES
```
├── SPEC.md                     ← This file (give to AI to build index.html)
├── index.html                  ← Frontend (AI builds this from spec above)
├── jobs.json                   ← Job data (auto-updated daily by scraper)
├── scraper/
│   ├── scrape.py               ← Python scraper (Bayt + Careerjet + LinkedIn + 351 entities)
│   ├── entities.json           ← All 351 Saudi government entities (from spreadsheet)
│   └── requirements.txt        ← Python deps: requests, beautifulsoup4, lxml
└── .github/workflows/
    └── daily-scrape.yml        ← GitHub Actions cron: 9am GST daily
```

## SCRAPER SOURCES
- **Bayt.com** — 10 keyword searches × 2 pages
- **Careerjet.com.sa** — 6 keyword searches
- **LinkedIn Public API** — 4 keyword searches (no login)
- **351 Government Entities** — Searches Bayt per entity, scrapes career pages, falls back to LinkedIn job links

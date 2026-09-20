# BEACON Frontend Dashboard

Production-grade accessibility dashboard and real-time scanning interface built with Next.js 16, React 19, TypeScript, and Tailwind CSS.

---

## 🚀 Overview

The BEACON frontend delivers an interactive compliance workstation for accessibility engineers and product teams:
- **Instant Auditing**: Submit single URLs or entire domains for multi-engine accessibility evaluation.
- **Dynamic Scorecards**: Visualize WCAG 2.2 Level A, AA, and AAA compliance ratings, category breakdowns, and critical blockers.
- **Fix Remediation Workspace**: View AI-generated, standards-grounded remediation patches with before-and-after diffs.
- **Projects & History**: Manage ongoing domain audits, track compliance trends over time, and inspect historical audit snapshots via Supabase.

---

## 🛠️ Tech Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router, Server & Client Components)
- **Library**: React 19
- **Styling**: Tailwind CSS with custom dark mode & glassmorphic tokens
- **Icons**: Lucide React
- **Backend Connection**: FastAPI via REST & Server-Sent Events (SSE)
- **Database & Auth**: Supabase JS Client (`@supabase/supabase-js`, `@supabase/ssr`)
- **End-to-End Testing**: Playwright

---

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                # Root layout with ThemeProvider
│   │   ├── page.tsx                  # Landing page with audit scanner trigger
│   │   ├── globals.css               # Design system tokens and styles
│   │   └── dashboard/
│   │       ├── page.tsx              # Main dashboard overview
│   │       ├── [projectId]/page.tsx  # Project audit analysis & issues drilldown
│   │       ├── projects/page.tsx     # Project creation & portfolio list
│   │       └── help/page.tsx         # Help center & WCAG reference docs
│   ├── components/
│   │   ├── ThemeProvider.tsx         # Dark/light theme management
│   │   ├── ThemeToggle.tsx           # Quick theme switch control
│   │   ├── timeline-section.tsx      # Multi-phase audit progress visualization
│   │   └── ui/                       # Reusable UI primitives
│   └── lib/
│       ├── api.ts                    # Backend API client
│       └── supabase.ts               # Supabase browser/server client initialization
└── e2e/                              # Playwright test specs
```

---

## ⚙️ Environment Variables

Create a `.env.local` file inside the `frontend/` directory:

```env
# Backend API URL (FastAPI)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase Credentials (Optional for local mocked testing)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

---

## 🏃 Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) with your browser.

### 3. Build for Production
```bash
npm run build
npm run start
```

### 4. Run Linting
```bash
npm run lint
```

---

## 🎭 Running E2E Tests

Playwright browser tests are configured for the dashboard:

```bash
# Run headless tests
npm run test:e2e

# Run with visible browser
npm run test:e2e:headed

# Open interactive Playwright UI
npm run test:e2e:ui
```

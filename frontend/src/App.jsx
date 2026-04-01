import { Routes, Route, NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { supabase } from './lib/supabase'
import OpenRoles from './pages/OpenRoles'
import OnRadar from './pages/OnRadar'
import Pipeline from './pages/Pipeline'
import ReachedOut from './pages/ReachedOut'
import Applied from './pages/Applied'
import Sources from './pages/Sources'

function NavTab({ to, children, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
          isActive
            ? 'bg-brand-500 text-white'
            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
        }`
      }
    >
      {children}
    </NavLink>
  )
}

const HOW_CARDS = [
  {
    icon: '🔍',
    title: 'Discovers companies automatically',
    body: 'Every Monday, I pull open roles from Ashby, Greenhouse, Lever, and Workable across 100+ tracked companies. The agent also scans funding news, LinkedIn hiring posts, and newsletters to surface new AI-native companies.',
  },
  {
    icon: '📊',
    title: 'Scores every role with Claude',
    body: 'A keyword pre-filter drops non-fits. The rest are scored against my resume (cached for cost efficiency) on 5 dimensions with Claude Sonnet: role fit, company fit, end-user layer, growth signal, and location. Scoring learns from my actions: applied roles become positive benchmarks, skipped roles become negative signals.',
  },
  {
    icon: '🗂️',
    title: 'Routes to Open Roles or On Radar',
    body: 'Roles scoring 55+ go to Open Roles, ranked by fit score. Companies with no open PM roles go to On Radar. Every radar company gets a drafted outreach in my voice.',
  },
  {
    icon: '✅',
    title: 'Tracks everything, drafts everything',
    body: 'Tracks application status, outreach, and follow-ups across all stages. Nothing is sent automatically. The agent drafts, I review, I send.',
  },
]

function HowItWorks() {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span className="text-base">🤖</span>
          How this agent works
        </span>
        <span className="text-gray-400 text-xs">{open ? '▲ Hide' : '▼ Show'}</span>
      </button>
      {open && (
        <div className="border-t border-gray-100 p-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {HOW_CARDS.map(({ icon, title, body }) => (
              <div key={title}>
                <div className="text-xl mb-2">{icon}</div>
                <div className="font-semibold text-gray-800 text-sm mb-1">{title}</div>
                <div className="text-xs text-gray-500 leading-relaxed">{body}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatPill({ label, value, color }) {
  return (
    <div className={`px-3 py-1.5 rounded-full text-xs font-medium ${color}`}>
      <span className="font-bold">{value}</span> {label}
    </div>
  )
}

function getLastMonday() {
  const now = new Date()
  const diff = now.getDay() === 0 ? 6 : now.getDay() - 1
  const m = new Date(now)
  m.setDate(now.getDate() - diff)
  m.setHours(0, 0, 0, 0)
  return m
}

export default function App() {
  const [counts, setCounts] = useState({})
  const [thisWeek, setThisWeek] = useState({ jobs: 0, companies: 0 })

  useEffect(() => {
    const fetchCounts = async () => {
      const lastMonday = getLastMonday().toISOString()

      const [jobResp, radarResp, roRadarResp, weekJobResp, weekCoResp] = await Promise.all([
        supabase.from('jobs').select('id, status, score_breakdown'),
        supabase.from('companies').select('attention_score, feedback, radar_status').gte('attention_score', 40),
        supabase.from('companies').select('id').eq('radar_status', 'reached_out'),
        supabase.from('jobs').select('id', { count: 'exact' }).gte('created_at', lastMonday),
        supabase.from('companies').select('id', { count: 'exact' }).gte('created_at', lastMonday).not('attention_score', 'is', null).or('feedback.is.null,feedback.neq.not_for_me'),
      ])

      const jobs = jobResp.data || []
      const c = {}
      jobs.forEach(j => { c[j.status] = (c[j.status] || 0) + 1 })

      const radarCount = (radarResp.data || []).filter(r =>
        r.feedback !== 'not_for_me' && !['reached_out', 'applied'].includes(r.radar_status)
      ).length

      // Count jobs reached out: new system (score_breakdown.reached_out_at) OR legacy (status='reached_out')
      const roJobCount = jobs.filter(j =>
        (j.score_breakdown || {}).reached_out_at || j.status === 'reached_out'
      ).length
      const roCount = roJobCount + (roRadarResp.data?.length || 0)

      setCounts({
        open: (c['prep_ready'] || 0) + (c['borderline'] || 0) + (c['new'] || 0),
        radar: radarCount,
        pipeline: c['pipeline'] || 0,
        reachedOut: roCount,
        applied: c['applied'] || 0,
      })
      setThisWeek({ jobs: weekJobResp.count || 0, companies: weekCoResp.count || 0 })
    }
    fetchCounts()
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-lg leading-none">⚡</span>
            <span className="font-bold text-gray-900">Job Assist</span>
          </div>

          <nav className="flex items-center gap-1 overflow-x-auto flex-1 justify-center">
            <NavTab to="/" end>Open Roles</NavTab>
            <NavTab to="/on-radar">On Radar</NavTab>
            <NavTab to="/pipeline">Pipeline</NavTab>
            <NavTab to="/reached-out">Outreach</NavTab>
            <NavTab to="/applied">Applied</NavTab>
            <NavTab to="/sources">Sources</NavTab>
          </nav>

          <div className="shrink-0" />
        </div>
        {(thisWeek.jobs > 0 || thisWeek.companies > 0) && (
          <div className="max-w-7xl mx-auto px-4 pb-2">
            <div className="text-xs text-gray-400">
              This week: <span className="text-emerald-600 font-medium">{thisWeek.jobs} new roles</span>
              {thisWeek.companies > 0 && <span> · <span className="text-purple-600 font-medium">{thisWeek.companies} new companies on radar</span></span>}
            </div>
          </div>
        )}
      </header>

      {/* Main */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6 space-y-5">
        <HowItWorks />

        <Routes>
          <Route path="/" element={<OpenRoles />} />
          <Route path="/on-radar" element={<OnRadar />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/reached-out" element={<ReachedOut />} />
          <Route path="/applied" element={<Applied />} />
          <Route path="/sources" element={<Sources />} />
        </Routes>
      </main>
    </div>
  )
}

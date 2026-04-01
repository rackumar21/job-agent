import { useState, useEffect, useMemo } from 'react'
import { supabase } from '../lib/supabase'
import { deriveSector, deriveStage } from '../lib/utils'
import JobCard from '../components/JobCard'

function getLastMonday() {
  const now = new Date()
  const day = now.getDay() // 0=Sun, 1=Mon ...
  const diff = day === 0 ? 6 : day - 1 // days since last Monday
  const monday = new Date(now)
  monday.setDate(now.getDate() - diff)
  monday.setHours(0, 0, 0, 0)
  return monday
}

export default function OpenRoles() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('All')
  const [sectorFilter, setSectorFilter] = useState('All sectors')
  const [stageFilter, setStageFilter] = useState('All stages')
  const [scoreFilter, setScoreFilter] = useState('All scores')
  const [weekFilter, setWeekFilter] = useState('All time')

  const fetchJobs = async () => {
    setLoading(true)
    const { data } = await supabase
      .from('jobs')
      .select('*, companies(sector, stage, what_they_do)')
      .in('status', ['prep_ready', 'borderline', 'new'])
      .order('attractiveness_score', { ascending: false, nullsFirst: false })
    if (data) {
      const lastMonday = getLastMonday()
      const enriched = data.map(job => ({
        ...job,
        _sector: job.companies?.sector || deriveSector(job),
        _stage: job.companies?.stage || deriveStage(job),
        _isNew: new Date(job.created_at) >= lastMonday,
      }))
      setJobs(enriched)
    }
    setLoading(false)
  }

  useEffect(() => { fetchJobs() }, [])

  const handleStatusChange = (jobId, newStatus) => {
    if (['skip', 'pipeline', 'applied'].includes(newStatus)) {
      setJobs(prev => prev.filter(j => j.id !== jobId))
    }
  }

  // Derived filter options from current jobs
  const allSectors = useMemo(() =>
    ['All sectors', ...Array.from(new Set(jobs.map(j => j._sector).filter(s => s && s !== 'Cybersecurity AI'))).sort()],
  [jobs])

  const allStages = useMemo(() =>
    ['All stages', ...Array.from(new Set(jobs.map(j => j._stage).filter(Boolean))).sort()],
  [jobs])

  const filtered = useMemo(() => {
    let result = jobs
    if (weekFilter === 'This week') result = result.filter(j => j._isNew)
    if (roleFilter === 'PM') result = result.filter(j => (j.score_breakdown || {}).role_type === 'pm')
    if (roleFilter === 'Generalist / Ops') result = result.filter(j => (j.score_breakdown || {}).role_type === 'operator')
    if (sectorFilter !== 'All sectors') result = result.filter(j => j._sector === sectorFilter)
    if (stageFilter !== 'All stages') result = result.filter(j => j._stage === stageFilter)
    const score = j => j.attractiveness_score ?? 0
    if (scoreFilter === 'High (75+)') result = result.filter(j => score(j) >= 75)
    if (scoreFilter === 'Medium (55-74)') result = result.filter(j => score(j) >= 55 && score(j) < 75)
    if (scoreFilter === 'Low (<55)') result = result.filter(j => score(j) > 0 && score(j) < 55)
    if (scoreFilter === 'Unscored') result = result.filter(j => !j.attractiveness_score)
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(j =>
        j.title?.toLowerCase().includes(q) || j.company_name?.toLowerCase().includes(q)
      )
    }
    // Sort: pinned first, then new this week, then by score descending
    return [...result].sort((a, b) => {
      const aPinned = !!(a.score_breakdown?.pinned)
      const bPinned = !!(b.score_breakdown?.pinned)
      if (aPinned !== bPinned) return aPinned ? -1 : 1
      if (a._isNew !== b._isNew) return a._isNew ? -1 : 1
      return (b.attractiveness_score ?? 0) - (a.attractiveness_score ?? 0)
    })
  }, [jobs, weekFilter, roleFilter, sectorFilter, stageFilter, scoreFilter, search])

  const newCount = jobs.filter(j => j._isNew).length

  return (
    <div className="space-y-4">
      {/* Filters row */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          placeholder="Search title or company..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-48 bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
        <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option>All</option>
          <option>PM</option>
          <option>Generalist / Ops</option>
        </select>
        <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          {allSectors.map(s => <option key={s}>{s}</option>)}
        </select>
        <select value={stageFilter} onChange={e => setStageFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          {allStages.map(s => <option key={s}>{s}</option>)}
        </select>
        <select value={scoreFilter} onChange={e => setScoreFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option>All scores</option>
          <option>High (75+)</option>
          <option>Medium (55-74)</option>
          <option>Low (&lt;55)</option>
          <option>Unscored</option>
        </select>
        <select value={weekFilter} onChange={e => setWeekFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option>All time</option>
          <option>This week</option>
        </select>
        <button onClick={fetchJobs} className="btn-secondary">Refresh</button>
      </div>

      {/* Count line */}
      <div className="text-sm text-gray-400">
        {filtered.length} role{filtered.length !== 1 ? 's' : ''}
        {newCount > 0 && <span className="ml-2 text-emerald-600 font-medium">· {newCount} new this week</span>}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400 text-sm">Loading jobs...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">No roles matching this filter.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(job => (
            <JobCard key={job.id} job={job} onStatusChange={handleStatusChange} />
          ))}
        </div>
      )}
    </div>
  )
}

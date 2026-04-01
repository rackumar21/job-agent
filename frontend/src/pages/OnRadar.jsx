import { useState, useEffect, useMemo } from 'react'
import { supabase } from '../lib/supabase'
import ScoreBadge from '../components/ScoreBadge'

const NOT_FOR_ME_REASONS = [
  'Wrong sector', 'Wrong stage', 'Not AI enough',
  'Too early / no product yet', 'Too late / too big',
  'Wrong geography', 'Other',
]

function RadarCard({ item, onHide }) {
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState(item.relationship_message || '')
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showNotForMe, setShowNotForMe] = useState(false)
  const [nfmReason, setNfmReason] = useState(NOT_FOR_ME_REASONS[0])

  const score = item.attention_score
  const status = item.radar_status
  const isReachedOut = status === 'reached_out'
  const hasDraft = !!draft.trim()

  const statusPrefix = status === 'reached_out' ? '✉️ ' : status === 'applied' ? '✅ ' : ''

  const saveDraft = async () => {
    await supabase.from('companies').update({ relationship_message: draft }).eq('id', item.id)
  }

  const generateDraft = async () => {
    setGenerating(true)
    try {
      const resp = await fetch('/api/radar/generate-draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: item.id, company: item.name, what_they_do: item.what_they_do }),
      })
      const data = await resp.json()
      if (data.message) {
        setDraft(data.message)
        setExpanded(true)
      }
    } catch (e) {
      console.error('Draft generation failed:', e)
    }
    setGenerating(false)
  }

  const markReachedOut = async () => {
    setLoading(true)
    await supabase.from('companies').update({ radar_status: 'reached_out' }).eq('id', item.id)
    setLoading(false)
    onHide(item.id)
  }

  const markApplied = async () => {
    setLoading(true)
    await supabase.from('companies').update({ radar_status: 'applied' }).eq('id', item.id)
    setLoading(false)
    onHide(item.id)
  }

  const confirmNotForMe = async () => {
    setLoading(true)
    await supabase.from('companies').update({ feedback: 'not_for_me', feedback_reason: nfmReason }).eq('id', item.id)
    await supabase.from('jobs')
      .update({ status: 'skip' })
      .eq('company_name', item.name)
      .in('status', ['new', 'borderline', 'prep_ready'])
    setLoading(false)
    onHide(item.id)
  }

  return (
    <div className="card overflow-hidden">
      {/* Header row — always visible */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-gray-50/60 transition-colors"
      >
        <ScoreBadge score={score} label="attn" size="sm" />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-gray-900 text-sm">
            {statusPrefix}{item.name}
            {item._isNew && <span className="ml-2 badge bg-emerald-50 text-emerald-700 font-bold uppercase tracking-wide text-[0.65rem]">new</span>}
          </div>
          {item.what_they_do && (
            <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{item.what_they_do}</div>
          )}
          <div className="flex flex-wrap gap-1 mt-1">
            {item.sector && <span className="badge bg-gray-100 text-gray-600">{item.sector}</span>}
            {item.stage && <span className="badge bg-gray-100 text-gray-600">{item.stage}</span>}
            {item.funding_info && <span className="badge bg-gray-100 text-gray-600">{item.funding_info}</span>}
            {item.investors && <span className="text-xs text-gray-400">backed by {item.investors}</span>}
          </div>
        </div>
        <span className="text-gray-400 text-xs mt-0.5 shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 p-3 space-y-3">
          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              className={isReachedOut ? 'btn bg-amber-100 text-amber-700 border border-amber-200' : 'btn-warning'}
              onClick={markReachedOut}
              disabled={loading || isReachedOut}
            >
              {isReachedOut ? '✉️ Sent ✓' : '✉️ Reached Out'}
            </button>
            <button className="btn-primary" onClick={markApplied} disabled={loading}>✅ Applied</button>
            {!showNotForMe && (
              <button className="btn-danger" onClick={() => setShowNotForMe(true)} disabled={loading}>
                Not for me
              </button>
            )}
            {item.source_url && (
              <a href={item.source_url} target="_blank" rel="noreferrer" className="btn-secondary ml-auto">↗</a>
            )}
          </div>

          {/* Not for me form */}
          {showNotForMe && (
            <div className="bg-red-50 rounded-lg p-2.5 space-y-2">
              <div className="text-xs font-medium text-red-700">Why is {item.name} not a fit?</div>
              <select
                value={nfmReason}
                onChange={e => setNfmReason(e.target.value)}
                className="border border-red-200 rounded px-2 py-1 text-xs w-full bg-white"
              >
                {NOT_FOR_ME_REASONS.map(r => <option key={r}>{r}</option>)}
              </select>
              <div className="flex gap-2">
                <button onClick={confirmNotForMe} disabled={loading} className="btn-danger text-xs">Confirm</button>
                <button onClick={() => setShowNotForMe(false)} className="btn-secondary text-xs">Cancel</button>
              </div>
            </div>
          )}

          {/* Outreach draft */}
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1.5">Outreach draft</div>
            {hasDraft ? (
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onBlur={saveDraft}
                rows={5}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-200 resize-none"
              />
            ) : (
              <div className="space-y-2">
                <div className="text-xs text-gray-400 italic">No draft yet.</div>
                <button
                  className="btn-primary text-xs"
                  onClick={generateDraft}
                  disabled={generating}
                >
                  {generating ? 'Generating...' : '✦ Generate draft'}
                </button>
              </div>
            )}
            {hasDraft && (
              <div className="flex gap-2 mt-1.5">
                <button
                  className="btn-ghost text-xs"
                  onClick={generateDraft}
                  disabled={generating}
                >
                  {generating ? 'Regenerating...' : '↻ Regenerate'}
                </button>
                <span className="text-xs text-gray-400 self-center">{draft.length} chars</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function OnRadar() {
  const [companies, setCompanies] = useState([])
  const [loading, setLoading] = useState(true)
  const [hiddenIds, setHiddenIds] = useState(new Set())
  const [statusFilter, setStatusFilter] = useState('Not yet contacted')
  const [sectorFilter, setSectorFilter] = useState('All sectors')
  const [stageFilter, setStageFilter] = useState('All stages')
  const [scoreFilter, setScoreFilter] = useState('All scores')
  const [search, setSearch] = useState('')

  useEffect(() => {
    const fetchAll = async () => {
      const [coResp, jobResp] = await Promise.all([
        supabase.from('companies').select('*').gte('attention_score', 40).order('attention_score', { ascending: false, nullsFirst: false }),
        supabase.from('jobs').select('company_name').in('status', ['prep_ready', 'borderline', 'new']),
      ])

      const openNames = new Set((jobResp.data || []).map(j => j.company_name))

      const monday = (() => {
        const now = new Date()
        const diff = now.getDay() === 0 ? 6 : now.getDay() - 1
        const m = new Date(now); m.setDate(now.getDate() - diff); m.setHours(0, 0, 0, 0)
        return m
      })()

      const enriched = (coResp.data || [])
        .filter(c => c.feedback !== 'not_for_me' && c.sector !== 'Cybersecurity AI' && !openNames.has(c.name))
        .map(c => ({ ...c, _isNew: new Date(c.created_at) >= monday }))

      setCompanies(enriched)
      setLoading(false)
    }
    fetchAll()
  }, [])

  const hideItem = (id) => setHiddenIds(prev => new Set([...prev, id]))

  const allSectors = useMemo(() =>
    ['All sectors', ...Array.from(new Set(companies.map(c => c.sector).filter(Boolean))).sort()],
  [companies])

  const allStages = useMemo(() =>
    ['All stages', ...Array.from(new Set(companies.map(c => c.stage).filter(Boolean))).sort()],
  [companies])

  const filtered = useMemo(() => {
    let result = companies.filter(c => !hiddenIds.has(c.id))

    if (statusFilter === 'Not yet contacted')
      result = result.filter(c => !['reached_out', 'applied'].includes(c.radar_status))
    else if (statusFilter === 'Has draft')
      result = result.filter(c => (c.relationship_message || '').trim() && !['reached_out', 'applied'].includes(c.radar_status))
    else if (statusFilter === 'Reached out')
      result = result.filter(c => c.radar_status === 'reached_out')
    else if (statusFilter === 'Applied')
      result = result.filter(c => c.radar_status === 'applied')

    if (sectorFilter !== 'All sectors') result = result.filter(c => c.sector === sectorFilter)
    if (stageFilter !== 'All stages') result = result.filter(c => c.stage === stageFilter)
    const sc = c => c.attention_score || 0
    if (scoreFilter === 'High (80+)') result = result.filter(c => sc(c) >= 80)
    if (scoreFilter === 'Medium (60-79)') result = result.filter(c => sc(c) >= 60 && sc(c) < 80)
    if (scoreFilter === 'Low (<60)') result = result.filter(c => sc(c) > 0 && sc(c) < 60)

    if (search) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.name?.toLowerCase().includes(q) || c.sector?.toLowerCase().includes(q)
      )
    }

    return [...result].sort((a, b) => {
      if (a._isNew !== b._isNew) return a._isNew ? -1 : 1
      return (b.attention_score || 0) - (a.attention_score || 0)
    })
  }, [companies, hiddenIds, statusFilter, sectorFilter, stageFilter, scoreFilter, search])

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          placeholder="Search company or sector..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-48 bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
        />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white">
          <option>Not yet contacted</option>
          <option>Has draft</option>
          <option>All</option>
          <option>Reached out</option>
          <option>Applied</option>
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
          <option>High (80+)</option>
          <option>Medium (60-79)</option>
          <option>Low (&lt;60)</option>
        </select>
        <span className="text-sm text-gray-400">{filtered.length} companies</span>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400 text-sm">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">No companies matching this filter.</div>
      ) : (
        <div className="space-y-2">
          {filtered.map(item => (
            <RadarCard key={item.id} item={item} onHide={hideItem} />
          ))}
        </div>
      )}
    </div>
  )
}

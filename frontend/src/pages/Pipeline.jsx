import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { daysSince, fmtDateMDY } from '../lib/utils'
import ScoreBadge from '../components/ScoreBadge'

function PipelineCard({ job, onUpdate }) {
  const [expanded, setExpanded] = useState(false)
  const [localJob, setLocalJob] = useState(job)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [notes, setNotes] = useState(job.score_breakdown?.notes || '')

  const sb = localJob.score_breakdown || {}
  const prep = localJob.prep_materials || {}
  const reachedOutAt = sb.reached_out_at
  const hasPrepMsg = !!(prep.outreach_message || '').trim()
  const daysReachedOut = daysSince(reachedOutAt)
  const followUpNudge = reachedOutAt && daysReachedOut >= 3 ? ` · ⏰ Follow up (${daysReachedOut}d)` : ''


  const markReachedOut = async () => {
    setLoading(true)
    const newSb = { ...sb, reached_out_at: new Date().toISOString() }
    await supabase.from('jobs').update({ score_breakdown: newSb }).eq('id', localJob.id)
    setLocalJob(prev => ({ ...prev, score_breakdown: newSb }))
    setLoading(false)
  }

  const markApplied = async () => {
    setLoading(true)
    const newSb = { ...sb, applied_at: new Date().toISOString() }
    await supabase.from('jobs').update({ status: 'applied', score_breakdown: newSb }).eq('id', localJob.id)
    setLoading(false)
    onUpdate(localJob.id)
  }

  const generatePrep = async () => {
    setGenerating(true)
    try {
      const resp = await fetch('/api/pipeline/generate-prep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: localJob.id,
          company_name: localJob.company_name,
          title: localJob.title,
          jd_text: localJob.jd_text,
          score_breakdown: localJob.score_breakdown,
        }),
      })
      const data = await resp.json()
      if (data.outreach_message) {
        const newPrep = { outreach_message: data.outreach_message, generated_at: data.generated_at }
        setLocalJob(prev => ({ ...prev, prep_materials: newPrep }))
        setExpanded(true)
      }
    } catch (e) {
      console.error('Prep generation failed:', e)
    }
    setGenerating(false)
  }

  const saveNotes = async () => {
    const newSb = { ...sb, notes }
    await supabase.from('jobs').update({ score_breakdown: newSb }).eq('id', localJob.id)
    setLocalJob(prev => ({ ...prev, score_breakdown: newSb }))
  }

  const outreachMsg = prep.outreach_message || ''

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50/60 transition-colors"
      >
        <ScoreBadge score={localJob.attractiveness_score} size="sm" />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-gray-900 text-sm">
            {localJob.company_name}
          </div>
          <div className="text-xs text-gray-500 truncate">
            {localJob.title}
            <span className="text-gray-400">{followUpNudge}</span>
          </div>
        </div>
        <div className="text-xs text-gray-400 shrink-0">
          {fmtDateMDY(localJob.created_at)}
        </div>
        <span className="text-gray-400 text-xs shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-gray-100 p-4 space-y-4">
          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              className={reachedOutAt ? 'btn bg-amber-100 text-amber-700 border border-amber-200' : 'btn-warning'}
              onClick={markReachedOut}
              disabled={loading || !!reachedOutAt}
            >
              {reachedOutAt ? '📧 Sent ✓' : '📧 Reached Out'}
            </button>
            <button className="btn-primary" onClick={markApplied} disabled={loading}>✅ Applied</button>
            {localJob.url && (
              <a href={localJob.url} target="_blank" rel="noreferrer" className="btn-secondary">↗ View job</a>
            )}
          </div>

          {/* Outreach message */}
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1.5">Outreach Message</div>
            <div className="text-xs text-gray-400 mb-2">Find the right person on LinkedIn. Swap [Name] and send.</div>
            {outreachMsg ? (
              <>
                <textarea
                  value={outreachMsg}
                  readOnly
                  rows={6}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 bg-gray-50 resize-none"
                />
                <div className="flex items-center gap-3 mt-1.5">
                  <button
                    className="btn-ghost text-xs"
                    onClick={generatePrep}
                    disabled={generating}
                  >
                    {generating ? 'Regenerating...' : '↻ Regenerate'}
                  </button>
                  <span className="text-xs text-gray-400">
                    {outreachMsg.length} chars
                    {prep.generated_at && ` · generated ${prep.generated_at.slice(0, 10)}`}
                  </span>
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <div className="text-xs text-gray-400 italic">No outreach message yet.</div>
                <button
                  className="btn-primary text-xs"
                  onClick={generatePrep}
                  disabled={generating}
                >
                  {generating ? 'Generating...' : '⚡ Generate now'}
                </button>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">Notes</div>
            <input
              type="text"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              onBlur={saveNotes}
              placeholder="Interview status, recruiter name, next step..."
              className="border border-gray-200 rounded-lg px-3 py-2 text-xs w-full focus:outline-none focus:ring-1 focus:ring-brand-200"
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default function Pipeline() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [generatingAll, setGeneratingAll] = useState(false)

  const fetchJobs = async () => {
    setLoading(true)
    const { data } = await supabase
      .from('jobs')
      .select('*')
      .eq('status', 'pipeline')
      .order('created_at', { ascending: false })
    setJobs(data || [])
    setLoading(false)
  }

  useEffect(() => { fetchJobs() }, [])

  const handleUpdate = (jobId) => setJobs(prev => prev.filter(j => j.id !== jobId))

  const needsPrep = jobs.filter(j => !(j.prep_materials?.outreach_message || '').trim())

  const generateAllPrep = async () => {
    setGeneratingAll(true)
    for (const job of needsPrep) {
      try {
        await fetch('/api/pipeline/generate-prep', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: job.id,
            company_name: job.company_name,
            title: job.title,
            jd_text: job.jd_text,
            score_breakdown: job.score_breakdown,
          }),
        })
      } catch (e) {
        console.error('Failed prep for', job.id, e)
      }
    }
    setGeneratingAll(false)
    fetchJobs()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="text-sm text-gray-500">
          {jobs.length} jobs in pipeline
          {needsPrep.length > 0 && (
            <span className="ml-2 text-amber-600">· {needsPrep.length} need prep</span>
          )}
        </div>
        {needsPrep.length > 0 && (
          <button
            className="btn-primary text-xs"
            onClick={generateAllPrep}
            disabled={generatingAll}
          >
            {generatingAll ? 'Generating...' : `⚡ Generate prep for all (${needsPrep.length})`}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400 text-sm">Loading...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No jobs in pipeline yet. Hit Pipeline on any Open Role card.
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map(job => (
            <PipelineCard key={job.id} job={job} onUpdate={handleUpdate} />
          ))}
        </div>
      )}
    </div>
  )
}

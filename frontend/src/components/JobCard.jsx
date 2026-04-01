import { useState } from 'react'
import { supabase } from '../lib/supabase'
import { fmtDateMDY } from '../lib/utils'
import ScoreBadge from './ScoreBadge'

export default function JobCard({ job, onStatusChange }) {
  const [localJob, setLocalJob] = useState(job)
  const [loading, setLoading] = useState(false)
  const [showSkip, setShowSkip] = useState(false)
  const [skipReason, setSkipReason] = useState('')
  const [notes, setNotes] = useState(job.score_breakdown?.notes || '')

  const sb = localJob.score_breakdown || {}
  const sector = localJob._sector || localJob.companies?.sector || null
  const stage = localJob._stage || localJob.companies?.stage || null
  const reachedOut = !!sb.reached_out_at
  const whatTheyDo = localJob.companies?.what_they_do || ''
  const isNew = localJob._isNew || false
  const score = localJob.attractiveness_score

  const updateStatus = async (newStatus) => {
    setLoading(true)
    try {
      const updates = { status: newStatus, updated_at: new Date().toISOString() }
      if (newStatus === 'reached_out') {
        const newSb = { ...sb, reached_out_at: new Date().toISOString() }
        updates.score_breakdown = newSb
        updates.status = 'prep_ready'
        await supabase.from('jobs').update(updates).eq('id', localJob.id)
        setLocalJob(prev => ({ ...prev, score_breakdown: newSb }))
      } else if (newStatus === 'applied') {
        const newSb = { ...sb, applied_at: new Date().toISOString() }
        updates.score_breakdown = newSb
        await supabase.from('jobs').update(updates).eq('id', localJob.id)
        onStatusChange?.(localJob.id, newStatus)
      } else {
        await supabase.from('jobs').update(updates).eq('id', localJob.id)
        onStatusChange?.(localJob.id, newStatus)
      }
    } finally {
      setLoading(false)
    }
  }

  const confirmSkip = async () => {
    setLoading(true)
    const updates = { status: 'skip', updated_at: new Date().toISOString() }
    if (skipReason.trim()) updates.score_breakdown = { ...sb, skip_reason: skipReason.trim() }
    await supabase.from('jobs').update(updates).eq('id', localJob.id)
    setLoading(false)
    onStatusChange?.(localJob.id, 'skip')
  }

  const saveNotes = async () => {
    const newSb = { ...sb, notes }
    await supabase.from('jobs').update({ score_breakdown: newSb }).eq('id', localJob.id)
    setLocalJob(prev => ({ ...prev, score_breakdown: newSb }))
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all flex flex-col overflow-hidden">

      {/* Body */}
      <div className="p-4 flex flex-col gap-3 flex-1">

        {/* Title + score */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-900 text-sm leading-snug">
              {localJob.url
                ? <a href={localJob.url} target="_blank" rel="noreferrer" className="hover:text-indigo-600 transition-colors">{localJob.title}</a>
                : localJob.title}
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-sm text-gray-600 font-medium truncate">{localJob.company_name}</span>
              {isNew && <span className="shrink-0 px-1.5 py-0.5 rounded text-[0.6rem] font-bold uppercase tracking-wide bg-emerald-50 text-emerald-600 border border-emerald-100">new</span>}
            </div>
          </div>
          <ScoreBadge score={score} label="fit" />
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5">
          {sector && <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600">{sector}</span>}
          {stage && <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600">{stage}</span>}
          {reachedOut
            ? <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700">✉ {fmtDateMDY(sb.reached_out_at)}</span>
            : localJob.created_at && <span className="text-xs text-gray-400">{fmtDateMDY(localJob.created_at)}</span>
          }
        </div>

        {/* Description */}
        {whatTheyDo && (
          <p className="text-xs text-gray-500 leading-relaxed">{whatTheyDo}</p>
        )}

        {/* Notes */}
        <input
          type="text"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="Add a note..."
          className="text-xs w-full rounded-lg px-3 py-2 bg-gray-50 text-gray-700 placeholder-gray-300 border border-transparent focus:border-gray-200 focus:bg-white focus:outline-none transition-all"
        />

        {/* Skip form */}
        {showSkip && (
          <div className="bg-gray-50 rounded-lg p-3 space-y-2 border border-gray-200">
            <p className="text-xs font-medium text-gray-500">Why skip?</p>
            <input
              type="text"
              value={skipReason}
              onChange={e => setSkipReason(e.target.value)}
              placeholder="e.g. too infra-heavy"
              className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs w-full bg-white focus:outline-none focus:ring-1 focus:ring-gray-300"
              autoFocus
            />
            <div className="flex gap-2">
              <button onClick={confirmSkip} disabled={loading}
                className="text-xs px-3 py-1.5 rounded-lg bg-gray-600 text-white hover:bg-gray-700 font-medium transition-colors disabled:opacity-40">
                Skip
              </button>
              <button onClick={() => { setShowSkip(false); setSkipReason('') }}
                className="text-xs px-3 py-1.5 rounded-lg bg-white text-gray-600 border border-gray-200 hover:bg-gray-50 font-medium transition-colors">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Action footer */}
      <div className="border-t border-gray-100 px-3 pt-2.5 pb-2 space-y-2">
        {/* Row 1: action buttons */}
        <div className="flex items-center gap-1.5 w-full">
          <ActionBtn className="flex-1" onClick={() => updateStatus('pipeline')} disabled={loading}>Pipeline</ActionBtn>
          <ActionBtn className="flex-1" onClick={() => updateStatus('reached_out')} disabled={loading || reachedOut} dimmed={reachedOut}>
            {reachedOut ? 'Sent ✓' : 'Outreach'}
          </ActionBtn>
          <ActionBtn className="flex-1" onClick={() => updateStatus('applied')} disabled={loading}>Applied</ActionBtn>
        </div>
        {/* Row 2: secondary links */}
        <div className="flex items-center justify-between">
          {!showSkip
            ? <button onClick={() => setShowSkip(true)} disabled={loading}
                className="text-[11px] text-gray-300 hover:text-gray-500 transition-colors">
                Not a fit? Skip
              </button>
            : <span />
          }
          {localJob.url
            ? <a href={localJob.url} target="_blank" rel="noreferrer"
                className="text-[11px] text-gray-400 hover:text-gray-700 transition-colors font-medium">
                View ↗
              </a>
            : <span />
          }
        </div>
      </div>
    </div>
  )
}

function ActionBtn({ children, onClick, disabled, dimmed, className = '', ...props }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-2.5 py-1 rounded-md text-[11px] font-medium border transition-colors text-center
        ${dimmed
          ? 'text-gray-300 border-gray-100 cursor-default'
          : 'text-gray-600 border-gray-200 bg-white hover:bg-gray-50 hover:border-gray-300 cursor-pointer'}
        disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

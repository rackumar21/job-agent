import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { fmtDateMDY, daysSince } from '../lib/utils'

function JobRow({ job, onApplied }) {
  const [notes, setNotes] = useState(job.score_breakdown?.reached_out_notes || '')
  const sb = job.score_breakdown || {}
  // Support both new (reached_out_at in score_breakdown) and legacy (status='reached_out', use updated_at)
  const roTimestamp = sb.reached_out_at || (job.status === 'reached_out' ? job.updated_at : null)
  const roDate = fmtDateMDY(roTimestamp)
  const days = daysSince(roTimestamp)
  const nudge = days != null && days >= 3 ? ` ⏰ ${days}d` : ''

  const saveNotes = async () => {
    const newSb = { ...sb, reached_out_notes: notes }
    await supabase.from('jobs').update({ score_breakdown: newSb }).eq('id', job.id)
  }

  const markApplied = async () => {
    const newSb = { ...sb, applied_at: new Date().toISOString() }
    await supabase.from('jobs').update({ status: 'applied', score_breakdown: newSb }).eq('id', job.id)
    onApplied(job.id)
  }

  return (
    <tr className="hover:bg-gray-50/50">
      <td className="px-4 py-3 font-medium text-gray-900">{job.company_name}</td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {job.url ? <a href={job.url} target="_blank" rel="noreferrer" className="hover:text-brand-600">{job.title}</a> : job.title}
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
        {roDate}<span className="text-amber-600 font-medium text-xs ml-1">{nudge}</span>
      </td>
      <td className="px-4 py-3 text-center">
        <button
          onClick={markApplied}
          className="text-xs text-gray-400 hover:text-emerald-600 font-medium transition-colors"
          title="Mark as applied"
        >
          Applied ✓
        </button>
      </td>
      <td className="px-4 py-3">
        <input
          type="text"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="e.g. Recruiter replied, follow up Fri"
          className="border border-gray-200 rounded px-2 py-1 text-xs w-full min-w-48 focus:outline-none focus:ring-1 focus:ring-brand-200"
        />
      </td>
    </tr>
  )
}

function RadarRow({ item, onApplied }) {
  const [notes, setNotes] = useState('')

  const saveNotes = async () => {
    // notes stored locally only for radar rows (no dedicated column)
  }

  const markApplied = async () => {
    await supabase.from('companies').update({ radar_status: 'applied' }).eq('id', item.id)
    onApplied(item.id)
  }

  return (
    <tr className="hover:bg-gray-50/50">
      <td className="px-4 py-3 font-medium text-gray-900">{item.name}</td>
      <td className="px-4 py-3 text-xs text-gray-400">—</td>
      <td className="px-4 py-3 text-sm text-gray-500"></td>
      <td className="px-4 py-3 text-center">
        <button
          onClick={markApplied}
          className="text-xs text-gray-400 hover:text-emerald-600 font-medium transition-colors"
          title="Mark as applied"
        >
          Applied ✓
        </button>
      </td>
      <td className="px-4 py-3">
        <input
          type="text"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="e.g. Recruiter replied, follow up Fri"
          className="border border-gray-200 rounded px-2 py-1 text-xs w-full min-w-48 focus:outline-none focus:ring-1 focus:ring-brand-200"
        />
      </td>
    </tr>
  )
}

export default function ReachedOut() {
  const [jobs, setJobs] = useState([])
  const [radarItems, setRadarItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAll = async () => {
      const [jobResp, radarResp] = await Promise.all([
        supabase.from('jobs').select('*').order('updated_at', { ascending: false }),
        supabase.from('companies').select('id, name, radar_status, relationship_message').eq('radar_status', 'reached_out'),
      ])
      const allJobs = jobResp.data || []
      // Catch both: new system (reached_out_at in score_breakdown) and legacy (status='reached_out')
      const reachedOut = allJobs.filter(j =>
        (j.score_breakdown || {}).reached_out_at || j.status === 'reached_out'
      )
      setJobs(reachedOut)
      setRadarItems(radarResp.data || [])
      setLoading(false)
    }
    fetchAll()
  }, [])

  const removeJob = (id) => setJobs(prev => prev.filter(j => j.id !== id))
  const removeRadar = (id) => setRadarItems(prev => prev.filter(r => r.id !== id))

  const total = jobs.length + radarItems.length

  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-400">
        {total} {total === 1 ? 'company' : 'companies'} reached out to
        {radarItems.length > 0 && <span className="ml-2 text-gray-300">· {radarItems.length} from On Radar</span>}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400 text-sm">Loading...</div>
      ) : total === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No outreach tracked yet. Hit "Reached Out" on any job in Open Roles or Pipeline, or on a company in On Radar.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Company</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Role</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
                <th className="px-4 py-3 font-medium text-gray-500">Action</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {jobs.map(job => (
                <JobRow key={job.id} job={job} onApplied={removeJob} />
              ))}
              {radarItems.map(item => (
                <RadarRow key={item.id} item={item} onApplied={removeRadar} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

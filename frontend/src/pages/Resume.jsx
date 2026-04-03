import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import ScoreBadge from '../components/ScoreBadge'

function AutoTextarea({ value, onChange }) {
  const resize = (el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }
  return (
    <textarea
      ref={el => resize(el)}
      className="w-full text-xs border border-gray-300 rounded-lg p-2 bg-white resize-none overflow-hidden focus:outline-none focus:ring-1 focus:ring-brand-200"
      value={value}
      onInput={e => resize(e.target)}
      onChange={onChange}
    />
  )
}

function ATSReport({ report }) {
  if (!report) return null

  return (
    <div className="space-y-5">
      {/* Summary */}
      <p className="text-sm text-gray-700 leading-relaxed">{report.summary}</p>

      {/* Strong matches */}
      {report.strong_matches?.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Strong Matches</h3>
          <ul className="space-y-1">
            {report.strong_matches.map((s, i) => (
              <li key={i} className="text-sm text-green-700 flex gap-2">
                <span className="shrink-0">+</span><span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Gaps */}
      {report.gaps?.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Gaps to Address</h3>
          <div className="space-y-2">
            {report.gaps.map((g, i) => (
              <div key={i} className={`rounded-lg p-3 border-l-4 ${
                g.severity === 'high' ? 'border-red-400 bg-red-50' :
                g.severity === 'medium' ? 'border-yellow-400 bg-yellow-50' :
                'border-gray-300 bg-gray-50'
              }`}>
                <div className="text-sm font-medium text-gray-800">{g.gap}</div>
                <div className="text-xs text-gray-600 mt-1">{g.recommendation}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing keywords */}
      {report.missing_keywords?.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Missing Keywords</h3>
          <div className="flex flex-wrap gap-2">
            {report.missing_keywords.map((kw, i) => (
              <span key={i} className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">{kw}</span>
            ))}
          </div>
        </div>
      )}

      {/* Cover letter angles */}
      {report.cover_letter_angles?.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Cover Letter Angles</h3>
          <ul className="space-y-1">
            {report.cover_letter_angles.map((a, i) => (
              <li key={i} className="text-sm text-gray-600">{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ResumeUpdateSection({ report, company }) {
  const suggestions = (report?.rewrite_suggestions || []).map(s => ({
    ...s, edited: s.rewritten, selected: true,
  }))

  const [items, setItems] = useState(suggestions)
  const [approved, setApproved] = useState(false)

  // Reset when report changes
  useEffect(() => {
    const fresh = (report?.rewrite_suggestions || []).map(s => ({
      ...s, edited: s.rewritten, selected: true,
    }))
    setItems(fresh)
    setApproved(false)
  }, [report])

  if (!items.length) return null

  const selectedItems = items.filter(i => i.selected)
  const toggle = (i, val) => setItems(prev => prev.map((x, j) => j === i ? { ...x, selected: val } : x))
  const edit = (i, val) => setItems(prev => prev.map((x, j) => j === i ? { ...x, edited: val } : x))
  const [copied, setCopied] = useState(null)

  const copyText = (text, idx) => {
    navigator.clipboard.writeText(text)
    setCopied(idx)
    setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">Resume Tailoring</h2>

      {!approved ? (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Review each suggested rewrite. Uncheck any you want to skip, edit the text as needed, then approve.
          </p>
          {items.map((item, i) => (
            <div key={i} className={`border rounded-lg p-3 space-y-2 transition-all ${
              item.selected ? 'border-blue-200 bg-blue-50/40' : 'border-gray-200 bg-gray-50 opacity-60'
            }`}>
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" className="mt-0.5 shrink-0 accent-brand-500"
                  checked={item.selected} onChange={e => toggle(i, e.target.checked)} />
                <span className="text-xs text-gray-500 italic">{item.reason}</span>
              </label>
              {item.selected && (
                <>
                  <div className="text-xs text-gray-400 font-medium">Original:</div>
                  <div className="text-xs text-gray-500 bg-red-50 border border-red-100 rounded-lg p-2 line-through">{item.original}</div>
                  <div className="text-xs text-gray-500 font-medium">Rewrite (edit as needed):</div>
                  <AutoTextarea value={item.edited} onChange={e => edit(i, e.target.value)} />
                </>
              )}
            </div>
          ))}
          <button
            className="px-4 py-2 rounded-lg text-sm font-medium bg-brand-500 text-white hover:bg-brand-600 transition-colors disabled:opacity-40"
            disabled={!selectedItems.length}
            onClick={() => setApproved(true)}
          >
            Approve {selectedItems.length} Change{selectedItems.length !== 1 ? 's' : ''}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Copy each rewrite and paste into your Google Doc, replacing the original bullet.
          </p>
          {selectedItems.map((item, i) => (
            <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-red-50 px-3 py-2 text-xs text-gray-500 line-through">{item.original}</div>
              <div className="bg-green-50 px-3 py-2 text-xs text-gray-800 flex items-start gap-2">
                <span className="flex-1">{item.edited}</span>
                <button
                  onClick={() => copyText(item.edited, i)}
                  className="shrink-0 px-2 py-1 rounded text-[10px] font-medium border border-green-300 bg-white text-green-700 hover:bg-green-100 transition-colors"
                >
                  {copied === i ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
          ))}
          <button
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 border border-gray-200 bg-white hover:bg-gray-50 transition-colors"
            onClick={() => setApproved(false)}
          >
            Edit Again
          </button>
        </div>
      )}
    </div>
  )
}

export default function Resume() {
  const [searchParams] = useSearchParams()
  const jobIdParam = searchParams.get('jobId')

  const [mode, setMode] = useState('url') // 'url' or 'text'
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [jdText, setJdText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  // If jobId is in the URL, load that job's data
  useEffect(() => {
    if (!jobIdParam) return
    const loadJob = async () => {
      const { data } = await supabase
        .from('jobs')
        .select('title, company_name, jd_text, url, score_breakdown')
        .eq('id', jobIdParam)
        .single()
      if (data) {
        setTitle(data.title || '')
        setCompany(data.company_name || '')
        setJdText(data.jd_text || '')
        if (data.url) setUrl(data.url)
        // If ATS report already exists, show it
        const existing = data.score_breakdown?.ats_report
        if (existing) setReport(existing)
        // Switch to text mode if we have JD text but no URL
        if (data.jd_text && !data.url) setMode('text')
      }
    }
    loadJob()
  }, [jobIdParam])

  const runAnalysis = async () => {
    setAnalyzing(true)
    setError('')
    setReport(null)

    try {
      const body = mode === 'url'
        ? { url: url.trim(), title: title.trim() || undefined, company: company.trim() || undefined }
        : { jd_text: jdText.trim(), title: title.trim(), company: company.trim() }

      const resp = await fetch('/api/ats/analyze-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!resp.ok) {
        const err = await resp.json()
        setError(err.detail || 'Analysis failed')
        return
      }

      const data = await resp.json()
      // Update title/company from extracted metadata if we didn't have them
      if (data._title && !title) setTitle(data._title)
      if (data._company && !company) setCompany(data._company)
      setReport(data)

      // If this came from a tracked job, save ATS report back
      if (jobIdParam) {
        try {
          const { data: jobRow } = await supabase
            .from('jobs')
            .select('score_breakdown')
            .eq('id', jobIdParam)
            .single()
          const existing = jobRow?.score_breakdown || {}
          await supabase.from('jobs').update({
            score_breakdown: { ...existing, ats_report: data },
          }).eq('id', jobIdParam)
        } catch (e) {
          console.error('Could not save ATS report:', e)
        }
      }
    } catch (e) {
      setError('Network error: ' + e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const displayCompany = report?._company || company
  const displayTitle = report?._title || title

  return (
    <div className="max-w-3xl mx-auto space-y-5">

      {/* Input section */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <h2 className="font-semibold text-gray-800">Analyze a Job & Tailor Resume</h2>

        {/* Mode toggle */}
        <div className="flex gap-2">
          <button
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === 'url' ? 'bg-brand-500 text-white' : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
            }`}
            onClick={() => setMode('url')}
          >
            Paste URL
          </button>
          <button
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === 'text' ? 'bg-brand-500 text-white' : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
            }`}
            onClick={() => setMode('text')}
          >
            Paste JD Text
          </button>
        </div>

        {mode === 'url' ? (
          <input
            type="text"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="Paste job URL (Ashby, Greenhouse, Lever, Workable, or any career page)..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200"
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text" value={title} onChange={e => setTitle(e.target.value)}
                placeholder="Job title"
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-200"
              />
              <input
                type="text" value={company} onChange={e => setCompany(e.target.value)}
                placeholder="Company name"
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-200"
              />
            </div>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              placeholder="Paste the full job description here..."
              rows={8}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-200 resize-y"
            />
          </>
        )}

        <button
          onClick={runAnalysis}
          disabled={analyzing || (mode === 'url' ? !url.trim() : !jdText.trim())}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-brand-500 text-white hover:bg-brand-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {analyzing ? 'Analyzing...' : 'Run ATS Analysis'}
        </button>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>
        )}
      </div>

      {/* ATS Report */}
      {report && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-4">
            <ScoreBadge score={report.ats_score} label="ATS" size="lg" />
            <div>
              <h2 className="font-semibold text-gray-800">
                {displayTitle}{displayCompany ? ` at ${displayCompany}` : ''}
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">ATS Score: {report.ats_score}/100</p>
            </div>
          </div>
          <ATSReport report={report} />
        </div>
      )}

      {/* Resume Tailoring */}
      {report?.rewrite_suggestions?.length > 0 && (
        <ResumeUpdateSection report={report} company={displayCompany} />
      )}
    </div>
  )
}

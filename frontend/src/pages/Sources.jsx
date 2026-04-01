import { useState } from 'react'

function ResultSummary({ result, onRunWorkflow, workflowRunning, workflowResult }) {
  if (!result) return null
  if (result.error) return (
    <div className="mt-3 text-xs text-red-600 bg-red-50 rounded-lg p-3">Error: {result.error}</div>
  )

  // Extract-from-post result
  const added = result.added || []
  const alreadyKnown = result.already_known || []
  const companiesFound = result.companies_found || []

  if ('companies_found' in result) {
    return (
      <div className="mt-3 space-y-2">
        <div className="text-sm text-gray-700">
          Found <strong>{companiesFound.length}</strong> {companiesFound.length === 1 ? 'company' : 'companies'}.
          {added.length > 0 && <> Added <strong>{added.length}</strong> new: {added.join(', ')}.</>}
          {alreadyKnown.length > 0 && <> Already tracking: {alreadyKnown.join(', ')}.</>}
        </div>
        {added.length > 0 && !workflowResult && (
          <button
            className="btn-primary text-xs"
            onClick={() => onRunWorkflow(added)}
            disabled={workflowRunning}
          >
            {workflowRunning ? 'Running...' : `Run workflow for ${added.length} ${added.length === 1 ? 'company' : 'companies'}`}
          </button>
        )}
        {workflowResult && <WorkflowResult result={workflowResult} />}
      </div>
    )
  }

  // Funding scan result
  if ('companies' in result) {
    const companies = result.companies || []
    return (
      <div className="mt-3 space-y-2">
        <div className="text-sm text-gray-700">
          Found <strong>{companies.length}</strong> {companies.length === 1 ? 'company' : 'companies'} from TechCrunch and Next Play.
        </div>
        {companies.length > 0 && (
          <div className="text-xs text-gray-500">{companies.join(', ')}</div>
        )}
        {companies.length > 0 && !workflowResult && (
          <button
            className="btn-primary text-xs"
            onClick={() => onRunWorkflow(companies)}
            disabled={workflowRunning}
          >
            {workflowRunning ? 'Running...' : `Run workflow for ${companies.length} companies`}
          </button>
        )}
        {workflowResult && <WorkflowResult result={workflowResult} />}
      </div>
    )
  }

  return null
}

function AddResult({ result }) {
  if (!result) return null
  if (result.error) return (
    <div className="mt-3 text-xs text-red-600 bg-red-50 rounded-lg p-3">Error: {result.error}</div>
  )

  const jobsAdded = result.jobs_added || []
  const jobsFailed = result.jobs_failed || []
  const companiesAdded = result.companies_added || []
  const companiesExisting = result.companies_existing || []
  const workflow = result.workflow

  return (
    <div className="mt-3 space-y-2">
      {/* URL jobs added directly */}
      {jobsAdded.length > 0 && (
        <div className="text-sm text-gray-700">Added {jobsAdded.length} {jobsAdded.length === 1 ? 'job' : 'jobs'} to Open Roles: {jobsAdded.join(', ')}.</div>
      )}
      {jobsFailed.length > 0 && (
        <div className="text-sm text-red-500">Failed: {jobsFailed.join(', ')}.</div>
      )}
      {/* Pipeline result for company names */}
      {workflow && <WorkflowResult result={workflow} />}
      {/* If no workflow ran and only company tracking happened */}
      {!workflow && companiesAdded.length === 0 && companiesExisting.length === 0 && jobsAdded.length === 0 && (
        <div className="text-sm text-gray-400">Nothing new to add.</div>
      )}
    </div>
  )
}

function WorkflowResult({ result }) {
  if (!result) return null
  if (result.error) return (
    <div className="text-xs text-red-600 bg-red-50 rounded-lg p-3">Error: {result.error}</div>
  )

  const openRoles = result.open_roles || result.jobs_found || []
  const addedToRadar = result.added_to_radar || []
  const skipped = result.skipped || []

  return (
    <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 space-y-1">
      {openRoles.length > 0 && <div>Found <strong>{openRoles.length}</strong> open {openRoles.length === 1 ? 'role' : 'roles'} — added to Open Roles.</div>}
      {addedToRadar.length > 0 && <div>Added <strong>{addedToRadar.length}</strong> to On Radar.</div>}
      {skipped.length > 0 && <div className="text-gray-400">Skipped {skipped.length} (low relevance score, added to Radar).</div>}
      {openRoles.length === 0 && addedToRadar.length === 0 && skipped.length === 0 && (
        <div className="text-gray-500">Workflow complete. {JSON.stringify(result)}</div>
      )}
    </div>
  )
}

export default function Sources() {
  const [running, setRunning] = useState(false)
  const [runLog, setRunLog] = useState(null)

  const [postText, setPostText] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractResult, setExtractResult] = useState(null)
  const [extractWorkflowRunning, setExtractWorkflowRunning] = useState(false)
  const [extractWorkflowResult, setExtractWorkflowResult] = useState(null)

  const [addInput, setAddInput] = useState('')
  const [adding, setAdding] = useState(false)
  const [addResult, setAddResult] = useState(null)

  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [scanWorkflowRunning, setScanWorkflowRunning] = useState(false)
  const [scanWorkflowResult, setScanWorkflowResult] = useState(null)

  const runPipeline = async () => {
    setRunning(true)
    setRunLog(null)
    try {
      const resp = await fetch('/api/pipeline/run', { method: 'POST' })
      const data = await resp.json()
      setRunLog(data)
    } catch (e) {
      setRunLog({ error: e.message })
    }
    setRunning(false)
  }

  const extractFromPost = async () => {
    if (!postText.trim()) return
    setExtracting(true)
    setExtractResult(null)
    setExtractWorkflowResult(null)
    try {
      const resp = await fetch('/api/sources/extract-post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: postText }),
      })
      setExtractResult(await resp.json())
    } catch (e) {
      setExtractResult({ error: e.message })
    }
    setExtracting(false)
  }

  const pollForResult = async (jobId, setResult, setRunning) => {
    const poll = async () => {
      try {
        const resp = await fetch(`/api/pipeline/status/${jobId}`)
        const data = await resp.json()
        if (data.status === 'done') {
          setResult(data.result)
          setRunning(false)
        } else if (data.status === 'error') {
          setResult(data.result)
          setRunning(false)
        } else {
          setTimeout(poll, 3000)
        }
      } catch {
        setTimeout(poll, 3000)
      }
    }
    setTimeout(poll, 3000)
  }

  const runWorkflowForExtracted = async (companies) => {
    setExtractWorkflowRunning(true)
    setExtractWorkflowResult(null)
    try {
      const resp = await fetch('/api/pipeline/run-for-companies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ companies }),
      })
      const data = await resp.json()
      if (data.job_id) {
        pollForResult(data.job_id, setExtractWorkflowResult, setExtractWorkflowRunning)
      } else {
        setExtractWorkflowResult(data)
        setExtractWorkflowRunning(false)
      }
    } catch (e) {
      setExtractWorkflowResult({ error: e.message })
      setExtractWorkflowRunning(false)
    }
  }

  const runFundingScan = async () => {
    setScanning(true)
    setScanResult(null)
    setScanWorkflowResult(null)
    try {
      const resp = await fetch('/api/sources/funding-scan', { method: 'POST' })
      const data = await resp.json()
      if (data.job_id) {
        const poll = async () => {
          try {
            const r = await fetch(`/api/sources/funding-scan/status/${data.job_id}`)
            const status = await r.json()
            if (status.status === 'done') {
              setScanResult(status.result)
              setScanning(false)
            } else if (status.status === 'error') {
              setScanResult(status.result)
              setScanning(false)
            } else {
              setTimeout(poll, 3000)
            }
          } catch { setTimeout(poll, 3000) }
        }
        setTimeout(poll, 3000)
      } else {
        setScanResult(data)
        setScanning(false)
      }
    } catch (e) {
      setScanResult({ error: e.message })
      setScanning(false)
    }
  }

  const runWorkflowForScan = async (companies) => {
    setScanWorkflowRunning(true)
    setScanWorkflowResult(null)
    try {
      const resp = await fetch('/api/pipeline/run-for-companies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ companies }),
      })
      const data = await resp.json()
      if (data.job_id) {
        pollForResult(data.job_id, setScanWorkflowResult, setScanWorkflowRunning)
      } else {
        setScanWorkflowResult(data)
        setScanWorkflowRunning(false)
      }
    } catch (e) {
      setScanWorkflowResult({ error: e.message })
      setScanWorkflowRunning(false)
    }
  }

  const addCompanies = async () => {
    if (!addInput.trim()) return
    setAdding(true)
    setAddResult(null)
    try {
      const resp = await fetch('/api/sources/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: addInput }),
      })
      setAddResult(await resp.json())
    } catch (e) {
      setAddResult({ error: e.message })
    }
    setAdding(false)
  }

  return (
    <div className="space-y-6">

      {/* Run pipeline */}
      <div className="card p-4 flex items-center gap-4">
        <div className="flex-1">
          <div className="text-sm font-semibold text-gray-900">Run Full Pipeline</div>
          <div className="text-xs text-gray-400 mt-0.5">Manually trigger the weekly agent run. Polls all 100+ tracked companies on Ashby and Greenhouse, scores new jobs with Claude, and updates Open Roles and On Radar. Normally runs automatically every Monday.</div>
        </div>
        <button className="btn-primary" onClick={runPipeline} disabled={running}>
          {running ? 'Running...' : 'Run Pipeline'}
        </button>
      </div>
      {runLog && (
        <div className="card p-4 text-xs font-mono text-gray-600 bg-gray-50 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {runLog.stdout || JSON.stringify(runLog, null, 2)}
        </div>
      )}

      <hr className="border-gray-100" />

      {/* Add from post text */}
      <div className="card p-4">
        <div className="text-sm font-semibold text-gray-900 mb-1">Add from post text</div>
        <div className="text-xs text-gray-400 mb-3">Paste a LinkedIn post listing companies</div>
        <textarea
          value={postText}
          onChange={e => setPostText(e.target.value)}
          rows={4}
          placeholder={'Back with another list of startups hiring...\n\n• Acme AI — $50M Series B\n• Notion — hiring PM'}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-200 resize-none"
        />
        <button className="btn-primary mt-2" onClick={extractFromPost} disabled={extracting || !postText.trim()}>
          {extracting ? 'Extracting...' : '✦ Extract and add companies'}
        </button>
        <ResultSummary
          result={extractResult}
          onRunWorkflow={runWorkflowForExtracted}
          workflowRunning={extractWorkflowRunning}
          workflowResult={extractWorkflowResult}
        />
      </div>

      {/* Auto-scan funding news */}
      <div className="card p-4">
        <div className="text-sm font-semibold text-gray-900 mb-1">Auto-scan funding news</div>
        <div className="text-xs text-gray-400 mb-3">
          Pulls from Next Play newsletter and TechCrunch. Extracts companies, then lets you run the workflow.
        </div>
        <button className="btn-primary" onClick={runFundingScan} disabled={scanning}>
          {scanning ? 'Scanning...' : '✦ Run funding scan'}
        </button>
        <ResultSummary
          result={scanResult}
          onRunWorkflow={runWorkflowForScan}
          workflowRunning={scanWorkflowRunning}
          workflowResult={scanWorkflowResult}
        />
      </div>

      {/* Add anything */}
      <div className="card p-4">
        <div className="text-sm font-semibold text-gray-900 mb-1">Add anything</div>
        <div className="text-xs text-gray-400 mb-3">
          Company names or job links. Mix and match.
        </div>
        <textarea
          value={addInput}
          onChange={e => setAddInput(e.target.value)}
          rows={4}
          placeholder={'Granola\nNotion AI\nhttps://jobs.ashby.com/somecompany/senior-pm'}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-brand-200 resize-none"
        />
        <button className="btn-primary mt-2" onClick={addCompanies} disabled={adding || !addInput.trim()}>
          {adding ? 'Adding...' : '✦ Add to dashboard'}
        </button>
        <AddResult result={addResult} />
      </div>

      <hr className="border-gray-100" />

      {/* Connected systems */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Connected systems</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Job boards</div>
            <div><span className="text-sm font-medium text-gray-800">Ashby</span> <span className="text-gray-400 text-xs">· 50+ verified company slugs</span></div>
            <div><span className="text-sm font-medium text-gray-800">Greenhouse</span> <span className="text-gray-400 text-xs">· 10+ verified company slugs</span></div>
            <div><span className="text-sm font-medium text-gray-800">Work at a Startup</span> <span className="text-gray-400 text-xs">· YC company list via Apify</span></div>
            <div className="text-xs text-gray-400 pt-1">Polled every Monday 9am PT</div>
          </div>

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Funding signals</div>
            <div><span className="text-sm font-medium text-gray-800">TechCrunch</span> <span className="text-gray-400 text-xs">· RSS feed</span></div>
            <div><span className="text-sm font-medium text-gray-800">Next Play newsletter</span> <span className="text-gray-400 text-xs">· RSS feed</span></div>
            <div className="text-xs text-gray-400 pt-1">Scanned every Monday 9:05am PT</div>
          </div>

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">AI systems</div>
            <div><span className="text-sm font-medium text-gray-800">Claude Haiku</span> <span className="text-gray-400 text-xs">· role scoring</span></div>
            <div><span className="text-sm font-medium text-gray-800">Claude Sonnet</span> <span className="text-gray-400 text-xs">· company scoring + outreach drafts</span></div>
          </div>

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">LinkedIn</div>
            <div><span className="text-sm font-medium text-gray-800">Job board</span> <span className="text-gray-400 text-xs">· open roles via Apify</span></div>
            <div><span className="text-sm font-medium text-gray-800">Curator monitor</span> <span className="text-gray-400 text-xs">· accounts posting funded startup lists</span></div>
            <div className="text-xs text-gray-400 pt-1">Monday + Thursday 9:10am PT</div>
          </div>

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Database</div>
            <div><span className="text-sm font-medium text-gray-800">Supabase (Postgres)</span></div>
            <div className="text-xs text-gray-400">Tables: jobs · companies · signals</div>
            <div className="text-xs text-gray-400">Stores: scores, drafts, behavioral signals, application history</div>
          </div>

          <div className="card p-4 space-y-1">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Scheduler</div>
            <div><span className="text-sm font-medium text-gray-800">APScheduler via launchd</span></div>
            <div className="text-xs text-gray-400">Mon 9:00am · Job board polling</div>
            <div className="text-xs text-gray-400">Mon 9:05am · RSS scan</div>
            <div className="text-xs text-gray-400">Mon+Thu 9:10am · LinkedIn monitor</div>
            <div className="text-xs text-gray-400">Mon 10:00am · Monday brief</div>
          </div>

        </div>
      </div>

    </div>
  )
}

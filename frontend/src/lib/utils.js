// Sector taxonomy (mirrors dashboard.py _SECTOR_MAP)
const SECTOR_MAP = [
  ['AI employees', ['ai workforce', 'ai worker', 'ai employee', 'ai superhuman', 'ai sales rep', 'digital worker', 'agentic workforce', 'ai teammate']],
  ['Voice AI', ['voice ai', 'voice agent', 'voice interview', 'speech ai', 'conversational voice', 'voice-based', 'audio ai']],
  ['Video AI', ['video generation', 'text-to-video', 'avatar', 'video ai', 'synthetic video', 'ai video', 'talking head']],
  ['Vibe coding', ['ai coding', 'code generation', 'ai-powered ide', 'no-code', 'low-code', 'app builder', 'replit', 'cursor', 'copilot', 'text-to-app', 'text-to-code']],
  ['Fintech', ['fintech', 'payments', 'payment platform', 'banking', 'lending', 'credit rating', 'cross-border', 'fx ', 'stablecoin', 'embedded finance', 'checkout', 'neobank', 'financial institution', 'aml', 'kyc', 'kyb']],
  ['Legal AI', ['legal', 'law firm', 'contract', 'legal tech', 'litigation', 'legal compliance', 'law ', 'attorney', 'counsel']],
  ['Health AI', ['health', 'medical', 'clinical', 'pharma', 'biotech', 'patient', 'ehr', 'healthcare', 'wellness', 'mental health']],
  ['Cybersecurity AI', ['cybersecurity', 'incident response', 'threat detection', 'vulnerability scanner', 'soc platform']],
  ['Developer tools', ['developer platform', 'devtools', 'api platform', 'background jobs', 'model context protocol', 'sdk ', 'deployment platform']],
  ['Industrial AI', ['manufacturing', 'mep ', 'mechanical electrical', 'construction', 'industrial', 'supply chain', 'factory', 'robotics']],
  ['Enterprise AI', ['enterprise ai', 'enterprise software', 'b2b ai', 'ai workspace', 'ai platform', 'business automation', 'workflow automation', 'productivity']],
  ['HR / Recruiting', ['recruiting', 'talent acquisition', 'hr platform', 'hiring platform', 'people ops']],
  ['Data / Analytics', ['data platform', 'analytics', 'business intelligence', 'data pipeline']],
]

export function deriveSector(job) {
  const bd = job.score_breakdown || {}
  if (bd.sector) return bd.sector
  const text = ((job.score_reasoning || '') + ' ' + (bd.key_angle || '')).toLowerCase()
  for (const [label, keywords] of SECTOR_MAP) {
    if (keywords.some(k => text.includes(k))) return label
  }
  return 'Other'
}

export function deriveStage(job) {
  const bd = job.score_breakdown || {}
  if (bd.stage) return bd.stage
  const text = ((job.score_reasoning || '') + ' ' + (job.jd_text || '').slice(0, 300)).toLowerCase()
  const PATTERNS = [
    ['Pre-Seed', ['pre-seed', 'pre seed']],
    ['Seed', ['seed round', 'seed funding', 'seed stage', 'seed-stage', 'seed-backed']],
    ['Series A', ['series a']],
    ['Series B', ['series b']],
    ['Series C', ['series c']],
    ['Series D', ['series d']],
    ['Series E', ['series e']],
    ['Public', ['publicly traded', 'nasdaq:', 'nyse:', 'went public', 'ipo completed']],
  ]
  for (const [stage, patterns] of PATTERNS) {
    if (patterns.some(p => text.includes(p))) return stage
  }
  return ''
}

export function fmtDateMDY(isoStr) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return `${d.getMonth() + 1}/${d.getDate()}/${String(d.getFullYear()).slice(2)}`
  } catch {
    return isoStr.slice(0, 10)
  }
}

export function daysSince(isoStr) {
  if (!isoStr) return null
  try {
    return Math.floor((Date.now() - new Date(isoStr).getTime()) / 86400000)
  } catch {
    return null
  }
}

export function relativeDate(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now - d) / 86400000)
  if (diffDays <= 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return `${Math.floor(diffDays / 30)}mo ago`
}

export function scoreColor(score) {
  if (score == null) return { bg: 'bg-gray-100', text: 'text-gray-400', border: 'border-gray-200' }
  if (score >= 75) return { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-300' }
  if (score >= 55) return { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-300' }
  return { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-200' }
}

export function sectorColor(sector) {
  const map = {
    'Voice AI': 'bg-purple-50 text-purple-700',
    'Enterprise AI': 'bg-blue-50 text-blue-700',
    'AI agents': 'bg-indigo-50 text-indigo-700',
    'Fintech': 'bg-green-50 text-green-700',
    'Legal AI': 'bg-slate-50 text-slate-700',
    'HR / Recruiting AI': 'bg-pink-50 text-pink-700',
    'Commerce AI': 'bg-orange-50 text-orange-700',
    'Video AI': 'bg-rose-50 text-rose-700',
    'Revenue intelligence': 'bg-teal-50 text-teal-700',
    'B2B automation': 'bg-cyan-50 text-cyan-700',
  }
  return map[sector] || 'bg-gray-100 text-gray-600'
}

export function stageColor(stage) {
  if (!stage) return 'bg-gray-100 text-gray-500'
  if (stage.toLowerCase().includes('seed')) return 'bg-yellow-50 text-yellow-700'
  if (stage.toLowerCase().includes('series a')) return 'bg-green-50 text-green-700'
  if (stage.toLowerCase().includes('series b')) return 'bg-blue-50 text-blue-700'
  if (stage.toLowerCase().includes('series c') || stage.toLowerCase().includes('series d')) return 'bg-purple-50 text-purple-700'
  if (stage.toLowerCase().includes('growth') || stage.toLowerCase().includes('late')) return 'bg-orange-50 text-orange-700'
  return 'bg-gray-100 text-gray-600'
}

export function truncate(str, n) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n) + '…' : str
}

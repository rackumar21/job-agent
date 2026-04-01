import { scoreColor } from '../lib/utils'

export default function ScoreBadge({ score, label = 'fit', size = 'md' }) {
  const { bg, text, border } = scoreColor(score)
  const sz = size === 'lg' ? 'w-14 h-14 text-lg' : size === 'sm' ? 'w-9 h-9 text-xs' : 'w-12 h-12 text-sm'

  if (score == null) {
    return (
      <div className={`${sz} rounded-full border ${border} ${bg} flex flex-col items-center justify-center shrink-0`}>
        <span className={`font-bold leading-none ${text}`}>—</span>
      </div>
    )
  }

  return (
    <div className={`${sz} rounded-full border-2 ${border} ${bg} flex flex-col items-center justify-center shrink-0`}>
      <span className={`font-bold leading-none ${text}`}>{score}</span>
      <span className={`text-[9px] leading-none mt-0.5 ${text} opacity-70`}>{label}</span>
    </div>
  )
}

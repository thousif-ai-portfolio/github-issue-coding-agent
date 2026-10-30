// A unified diff with added, removed and hunk lines coloured.
export function Diff({ diff }: { diff: string }) {
  const lines = diff.replace(/\n$/, '').split('\n')
  return (
    <pre className="code diff">
      {lines.map((line, i) => {
        let kind = ''
        if (line.startsWith('+++') || line.startsWith('---')) kind = 'file'
        else if (line.startsWith('@@')) kind = 'hunk'
        else if (line.startsWith('+')) kind = 'add'
        else if (line.startsWith('-')) kind = 'del'
        return (
          <span key={i} className={`line ${kind}`}>
            {line || ' '}
            {'\n'}
          </span>
        )
      })}
    </pre>
  )
}

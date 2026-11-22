const TYPES = new Set([
  'void',
  'char',
  'short',
  'int',
  'long',
  'float',
  'double',
  'signed',
  'unsigned',
  '_Bool',
  '_Complex',
  '_Imaginary',
  'size_t',
  'ssize_t',
  'ptrdiff_t',
  'wchar_t',
  'int8_t',
  'int16_t',
  'int32_t',
  'int64_t',
  'uint8_t',
  'uint16_t',
  'uint32_t',
  'uint64_t',
  'FILE',
  'struct',
  'union',
  'enum',
  'const',
  'volatile',
  'restrict',
])

const KEYWORDS = new Set([
  'auto',
  'break',
  'case',
  'continue',
  'default',
  'do',
  'else',
  'extern',
  'for',
  'goto',
  'if',
  'inline',
  'register',
  'return',
  'sizeof',
  'static',
  'switch',
  'typedef',
  'while',
  'true',
  'false',
  'NULL',
  '_Alignas',
  '_Alignof',
  '_Atomic',
  '_Generic',
  '_Noreturn',
  '_Static_assert',
  '_Thread_local',
])

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function span(className: string, value: string): string {
  return `<span class="${className}">${escapeHtml(value)}</span>`
}

export function highlightC(source: string): string {
  let index = 0
  let depth = 0
  let result = ''

  while (index < source.length) {
    const char = source[index]
    const next = source[index + 1]

    if (char === '/' && next === '/') {
      let end = source.indexOf('\n', index)
      if (end === -1) {
        end = source.length
      }
      result += span('tok-comment', source.slice(index, end))
      index = end
      continue
    }

    if (char === '/' && next === '*') {
      let end = source.indexOf('*/', index + 2)
      end = end === -1 ? source.length : end + 2
      result += span('tok-comment', source.slice(index, end))
      index = end
      continue
    }

    if (char === '"' || char === "'") {
      const quote = char
      let cursor = index + 1
      while (cursor < source.length) {
        if (source[cursor] === '\\') {
          cursor += 2
          continue
        }
        if (source[cursor] === quote) {
          cursor += 1
          break
        }
        if (source[cursor] === '\n') {
          break
        }
        cursor += 1
      }
      result += span('tok-string', source.slice(index, cursor))
      index = cursor
      continue
    }

    if (char === '#') {
      const lineStart = source.lastIndexOf('\n', index - 1) + 1
      if (/^[ \t]*$/.test(source.slice(lineStart, index))) {
        let end = source.indexOf('\n', index)
        if (end === -1) {
          end = source.length
        }
        result += span('tok-preproc', source.slice(index, end))
        index = end
        continue
      }
    }

    const numberMatch = source
      .slice(index)
      .match(
        /^(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+)[uUlLfF]*/,
      )
    if (numberMatch) {
      result += span('tok-number', numberMatch[0])
      index += numberMatch[0].length
      continue
    }

    const identifierMatch = source.slice(index).match(/^[A-Za-z_]\w*/)
    if (identifierMatch) {
      const word = identifierMatch[0]
      let cursor = index + word.length
      while (cursor < source.length && /[ \t]/.test(source[cursor])) {
        cursor += 1
      }
      let className = 'tok-ident'
      if (TYPES.has(word)) {
        className = 'tok-type'
      } else if (KEYWORDS.has(word)) {
        className = 'tok-keyword'
      } else if (source[cursor] === '(') {
        className = 'tok-function'
      }
      result += span(className, word)
      index += word.length
      continue
    }

    if ('([{'.includes(char)) {
      depth += 1
      result += span(`tok-bracket br-${Math.min(6, depth)}`, char)
      index += 1
      continue
    }
    if (')]}'.includes(char)) {
      const level = Math.max(1, Math.min(6, depth))
      result += span(`tok-bracket br-${level}`, char)
      depth = Math.max(0, depth - 1)
      index += 1
      continue
    }

    result += escapeHtml(char)
    index += 1
  }

  return result
}

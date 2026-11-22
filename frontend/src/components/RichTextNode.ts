import {
  Fragment,
  defineComponent,
  h,
  type PropType,
  type VNodeChild,
} from 'vue'
import FormulaView from './FormulaView.vue'

export interface RichNode {
  type?: string
  text?: string
  attrs?: Record<string, unknown>
  marks?: Array<{ type?: string; attrs?: Record<string, unknown> }>
  content?: RichNode[]
}

const HIGHLIGHT_ALIASES: Record<string, string> = {
  yellow: 'yellow',
  amber: 'yellow',
  purple: 'purple',
  violet: 'purple',
  mint: 'mint',
  green: 'mint',
  pink: 'pink',
  rose: 'pink',
  blue: 'purple',
}

function safeHref(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const trimmed = value.trim()
  if (!trimmed || /[\u0000-\u001f]/.test(trimmed)) {
    return null
  }
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)) {
    return trimmed
  }
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
    return trimmed
  }
  return null
}

function safeImageSrc(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const trimmed = value.trim()
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return null
  }
  return /(?:\/assets\/\d+\/file|\/public\/documents\/[A-Za-z0-9_-]+\/assets\/\d+)$/.test(
    trimmed,
  )
    ? trimmed
    : null
}

function highlightTone(value: unknown): string {
  const tone = String(value || 'yellow')
  return HIGHLIGHT_ALIASES[tone] || 'yellow'
}

function textNode(
  text: string,
  marks: Array<{ type?: string; attrs?: Record<string, unknown> }>,
): RichNode {
  return marks.length
    ? { type: 'text', text, marks }
    : { type: 'text', text }
}

interface InlinePattern {
  regex: RegExp
  parse: (
    match: RegExpExecArray,
    marks: Array<{ type?: string; attrs?: Record<string, unknown> }>,
    recurse: (
      value: string,
      marks: Array<{ type?: string; attrs?: Record<string, unknown> }>,
    ) => RichNode[],
  ) => RichNode[]
}

const INLINE_PATTERNS: InlinePattern[] = [
  {
    regex: /`([^`\n]+)`/,
    parse: (match, marks) => [
      textNode(match[1], [...marks, { type: 'code' }]),
    ],
  },
  {
    regex: /\$([^$\n]+)\$/,
    parse: (match, marks) => [
      {
        type: 'inlineFormula',
        attrs: { latex: match[1].trim() },
      },
    ],
  },
  {
    regex:
      /<mark data-tone="([A-Za-z]+)">([\s\S]*?)<\/mark>/,
    parse: (match, marks, recurse) =>
      recurse(match[2], [
        ...marks,
        { type: 'highlight', attrs: { tone: match[1] } },
      ]),
  },
  {
    regex: /==([^=\n]+)==/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [
        ...marks,
        { type: 'highlight', attrs: { tone: 'yellow' } },
      ]),
  },
  {
    regex: /<u>([\s\S]*?)<\/u>/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'underline' }]),
  },
  {
    regex:
      /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/,
    parse: (match, marks) => {
      const alt = match[1] || ''
      const src = safeImageSrc(match[2])
      if (!src) {
        return [textNode(alt ? `[图片：${alt}]` : '[图片]', marks)]
      }
      return [
        {
          type: 'image',
          attrs: { src, alt, caption: match[3] || '' },
        },
      ]
    },
  },
  {
    regex:
      /\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/,
    parse: (match, marks, recurse) => {
      const label = match[1] || match[2]
      const href = safeHref(match[2])
      if (!href) {
        return recurse(label, marks)
      }
      return recurse(label, [
        ...marks,
        { type: 'link', attrs: { href, title: match[3] || '' } },
      ])
    },
  },
  {
    regex: /\*\*([^*\n]+)\*\*/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'bold' }]),
  },
  {
    regex: /__([^_\n]+)__/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'bold' }]),
  },
  {
    regex: /~~([^~\n]+)~~/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'strike' }]),
  },
  {
    regex: /\*([^*\n]+)\*/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'italic' }]),
  },
  {
    regex: /_([^_\n]+)_/,
    parse: (match, marks, recurse) =>
      recurse(match[1], [...marks, { type: 'italic' }]),
  },
]

export function parseInlineMarkdown(
  source: string,
  marks: Array<{ type?: string; attrs?: Record<string, unknown> }> = [],
): RichNode[] {
  if (!source) {
    return []
  }
  const result: RichNode[] = []
  let position = 0
  while (position < source.length) {
    const remaining = source.slice(position)
    let best:
      | {
          index: number
          match: RegExpExecArray
          pattern: InlinePattern
        }
      | null = null
    for (const pattern of INLINE_PATTERNS) {
      const match = pattern.regex.exec(remaining)
      if (!match) {
        continue
      }
      if (best === null || match.index < best.index) {
        best = { index: match.index, match, pattern }
      }
    }
    if (best === null) {
      result.push(textNode(source.slice(position), marks))
      break
    }
    if (best.index > 0) {
      result.push(textNode(remaining.slice(0, best.index), marks))
    }
    result.push(
      ...best.pattern.parse(best.match, marks, parseInlineMarkdown),
    )
    position += best.index + best.match[0].length
  }
  return result
}

function renderText(node: RichNode): VNodeChild {
  let child: VNodeChild = node.text || ''
  const marks = Array.isArray(node.marks) ? node.marks : []
  for (const mark of marks) {
    if (mark.type === 'bold') {
      child = h('strong', child)
    } else if (mark.type === 'italic') {
      child = h('em', child)
    } else if (mark.type === 'underline') {
      child = h('u', child)
    } else if (mark.type === 'strike') {
      child = h('s', child)
    } else if (mark.type === 'code') {
      child = h('code', child)
    } else if (mark.type === 'link') {
      const href = safeHref(mark.attrs?.href)
      if (href) {
        child = h(
          'a',
          {
            href,
            title:
              typeof mark.attrs?.title === 'string'
                ? mark.attrs.title
                : undefined,
            target: href.startsWith('http') ? '_blank' : undefined,
            rel: href.startsWith('http')
              ? 'noopener noreferrer'
              : undefined,
          },
          [child],
        )
      }
    } else if (mark.type === 'highlight') {
      const tone = highlightTone(mark.attrs?.tone || mark.attrs?.color)
      child = h('mark', { class: `hl-${tone}` }, [child])
    }
  }
  return child
}

export function renderRichNode(node: RichNode): VNodeChild {
  if (!node || typeof node !== 'object') {
    return null
  }
  if (node.type === 'text') {
    return renderText(node)
  }
  if (node.type === 'hardBreak') {
    return h('br')
  }
  if (node.type === 'inlineFormula') {
    return h(FormulaView, {
      latex: String(node.attrs?.latex || ''),
      display: 'inline',
    })
  }
  if (node.type === 'horizontalRule') {
    return h('hr', { class: 'rich-rule' })
  }
  if (node.type === 'image') {
    const src = safeImageSrc(node.attrs?.src)
    const alt = String(node.attrs?.alt || '')
    const caption = String(node.attrs?.caption || '')
    if (!src) {
      return h(
        'span',
        { class: 'blocked-inline-image' },
        alt ? `[图片：${alt}]` : '[图片]',
      )
    }
    return h('span', { class: 'inline-image' }, [
      h('img', { src, alt, loading: 'lazy', decoding: 'async' }),
      caption ? h('small', caption) : null,
    ])
  }

  const children = (node.content || [])
    .map(renderRichNode)
    .filter((child) => child !== null && child !== undefined)
  const hasVisibleText = (node.content || []).some(
    (child) =>
      child.type !== 'paragraph' ||
      (child.content || []).some((leaf) => leaf.text?.trim()),
  )

  if (node.type === 'doc') {
    return h('div', { class: 'rich-doc' }, children)
  }
  if (node.type === 'paragraph') {
    return h(
      'p',
      { class: hasVisibleText ? undefined : 'rich-empty-line' },
      children.length ? children : [h('br')],
    )
  }
  if (node.type === 'heading') {
    const level = Math.min(
      4,
      Math.max(1, Number(node.attrs?.level) || 1),
    )
    return h(`h${level}`, children)
  }
  if (node.type === 'bulletList') {
    return h('ul', { class: 'rich-list' }, children)
  }
  if (node.type === 'orderedList') {
    return h('ol', { class: 'rich-list ordered' }, children)
  }
  if (node.type === 'listItem') {
    return h('li', children)
  }
  if (node.type === 'taskList') {
    return h('ul', { class: 'rich-task-list' }, children)
  }
  if (node.type === 'taskItem') {
    return h(
      'li',
      { class: node.attrs?.checked ? 'checked' : undefined },
      [
        h(
          'span',
          {
            class: 'task-box',
            'aria-hidden': 'true',
          },
          node.attrs?.checked ? '✓' : '',
        ),
        ...children,
      ],
    )
  }
  if (node.type === 'blockquote') {
    return h('blockquote', children)
  }
  if (node.type === 'codeBlock') {
    return h('pre', { class: 'rich-code' }, [
      h(
        'code',
        node.content?.map((child) => child.text || '').join('') || '',
      ),
    ])
  }
  if (node.type === 'table') {
    return h('div', { class: 'rich-table-wrap' }, [
      h('table', { class: 'rich-table' }, [h('tbody', children)]),
    ])
  }
  if (node.type === 'tableRow') {
    return h('tr', children)
  }
  if (node.type === 'tableHeader') {
    return h('th', children)
  }
  if (node.type === 'tableCell') {
    return h('td', children)
  }

  return h('span', children)
}

export const InlineMarkdown = defineComponent({
  name: 'InlineMarkdown',
  props: {
    text: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    return () =>
      h(
        'span',
        { class: 'inline-markdown' },
        parseInlineMarkdown(props.text).map(renderRichNode),
      )
  },
})

export default defineComponent({
  name: 'RichTextNode',
  props: {
    node: {
      type: Object as PropType<RichNode>,
      required: true,
    },
  },
  setup(props) {
    return () => renderRichNode(props.node)
  },
})

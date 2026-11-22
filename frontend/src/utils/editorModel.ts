import type {
  BlockInput,
  DocumentBlock,
  DocumentDetail,
  SourceLanguage,
} from '../api/types'
import type { RichNode } from '../components/RichTextNode'

export type TextModuleType =
  | 'paragraph'
  | 'heading1'
  | 'heading2'
  | 'heading3'
  | 'quote'
  | 'divider'
  | 'bullet_list'
  | 'ordered_list'
  | 'todo_list'

export type EditorModuleType =
  | TextModuleType
  | 'table'
  | 'code'
  | 'image'
  | 'formula'
  | 'remark'
  | 'result'

export interface EditorModule {
  key: string
  id: number | null
  type: EditorModuleType
  markdown: string
  remarkModule: TextModuleType
  headers: string[]
  rows: string[][]
  text: string
  language: SourceLanguage | 'text'
  assetId: number | null
  assetName: string
  alt: string
  caption: string
  latex: string
}

export const TEXT_MODULE_TYPES = new Set<TextModuleType>([
  'paragraph',
  'heading1',
  'heading2',
  'heading3',
  'quote',
  'divider',
  'bullet_list',
  'ordered_list',
  'todo_list',
])

let keyCounter = 0

export function moduleKey(): string {
  keyCounter += 1
  return `module-${Date.now().toString(36)}-${keyCounter}`
}

export function makeModule(
  type: EditorModuleType,
  overrides: Partial<Omit<EditorModule, 'key' | 'type'>> = {},
): EditorModule {
  return {
    key: moduleKey(),
    id: null,
    type,
    markdown: '',
    remarkModule: 'paragraph',
    headers: [],
    rows: [],
    text: '',
    language: 'c',
    assetId: null,
    assetName: '',
    alt: '',
    caption: '',
    latex: '',
    ...overrides,
  }
}

export function createEditorModule(type: EditorModuleType): EditorModule {
  if (type === 'table') {
    return makeModule(type, {
      headers: ['列 1', '列 2'],
      rows: [['', '']],
    })
  }
  if (type === 'formula') {
    return makeModule(type, { latex: 'E = mc^2' })
  }
  return makeModule(type)
}

function plainNodeText(nodes: RichNode[] | undefined): string {
  return (nodes || [])
    .map((node) => {
      if (node.type === 'text') {
        return node.text || ''
      }
      if (node.type === 'inlineFormula') {
        return `$${String(node.attrs?.latex || '')}$`
      }
      if (node.type === 'hardBreak') {
        return '\n'
      }
      return plainNodeText(node.content)
    })
    .join('')
}

function applyMarks(text: string, node: RichNode): string {
  const marks = node.marks || []
  let value = text
  for (const mark of marks) {
    if (mark.type === 'bold') {
      value = `**${value}**`
    } else if (mark.type === 'italic') {
      value = `*${value}*`
    } else if (mark.type === 'underline') {
      value = `<u>${value}</u>`
    } else if (mark.type === 'strike') {
      value = `~~${value}~~`
    } else if (mark.type === 'code') {
      value = `\`${value}\``
    } else if (mark.type === 'link') {
      const href = String(mark.attrs?.href || '')
      if (
        /^(https?:\/\/|mailto:)/i.test(href) ||
        (href.startsWith('/') && !href.startsWith('//'))
      ) {
        value = `[${value}](${href})`
      }
    } else if (mark.type === 'highlight') {
      const tone = String(mark.attrs?.tone || mark.attrs?.color || 'yellow')
      if (tone === 'yellow') {
        value = `==${value}==`
      } else {
        const normalized =
          {
            amber: 'yellow',
            violet: 'purple',
            rose: 'pink',
            green: 'mint',
            blue: 'purple',
          }[tone] || tone
        value = `<mark data-tone="${normalized}">${value}</mark>`
      }
    }
  }
  return value
}

export function nodesToMarkdown(nodes: RichNode[] | undefined): string {
  return (nodes || [])
    .map((node) => {
      if (node.type === 'text') {
        return applyMarks(node.text || '', node)
      }
      if (node.type === 'inlineFormula') {
        return `$${String(node.attrs?.latex || '')}$`
      }
      if (node.type === 'hardBreak') {
        return '\n'
      }
      if (node.type === 'image') {
        const src = String(node.attrs?.src || '')
        if (!/\/assets\/\d+\/file$/.test(src)) {
          return String(node.attrs?.alt || '')
        }
        return `![${String(node.attrs?.alt || '')}](${src} "${
          node.attrs?.caption || ''
        }")`
      }
      return nodesToMarkdown(node.content)
    })
    .join('')
}

function listToMarkdown(node: RichNode, ordered: boolean): string {
  return (node.content || [])
    .map((item, index) => {
      const prefix = ordered ? `${index + 1}. ` : '- '
      return `${prefix}${nodesToMarkdown(item.content).trim()}`
    })
    .join('\n')
}

function todoToMarkdown(node: RichNode): string {
  return (node.content || [])
    .map((item) => {
      const checked = Boolean(item.attrs?.checked)
      const mark = checked ? '[x]' : '[ ]'
      return `- ${mark} ${nodesToMarkdown(item.content).trim()}`
    })
    .join('\n')
}

function tableCellText(node: RichNode | undefined): string {
  if (!node) {
    return ''
  }
  return nodesToMarkdown(node.content).trim()
}

function legacyNodeToModule(
  node: RichNode,
  blockId: number | null,
): EditorModule {
  if (node.type === 'heading') {
    const level = Math.min(3, Math.max(1, Number(node.attrs?.level) || 1))
    return makeModule(`heading${level}` as TextModuleType, {
      id: blockId,
      markdown: nodesToMarkdown(node.content),
    })
  }
  if (node.type === 'bulletList') {
    return makeModule('bullet_list', {
      id: blockId,
      markdown: listToMarkdown(node, false),
    })
  }
  if (node.type === 'orderedList') {
    return makeModule('ordered_list', {
      id: blockId,
      markdown: listToMarkdown(node, true),
    })
  }
  if (node.type === 'taskList') {
    return makeModule('todo_list', {
      id: blockId,
      markdown: todoToMarkdown(node),
    })
  }
  if (node.type === 'blockquote') {
    const paragraphs = (node.content || []).map((child) =>
      nodesToMarkdown(child.content).trim(),
    )
    return makeModule('quote', {
      id: blockId,
      markdown: paragraphs.join('\n\n'),
    })
  }
  if (node.type === 'horizontalRule') {
    return makeModule('divider', { id: blockId })
  }
  if (node.type === 'codeBlock') {
    return makeModule('code', {
      id: blockId,
      text: (node.content || []).map((child) => child.text || '').join(''),
      language: 'text',
    })
  }
  if (node.type === 'table') {
    const rows = node.content || []
    const headers = (rows[0]?.content || []).map((cell) =>
      tableCellText(cell.content?.[0]),
    )
    const body = rows.slice(1).map((row) =>
      (row.content || []).map((cell) =>
        tableCellText(cell.content?.[0]),
      ),
    )
    return makeModule('table', {
      id: blockId,
      headers: headers.length ? headers : ['列 1'],
      rows: body.length ? body : [headers.map(() => '')],
    })
  }
  if (node.type === 'doc' || node.type === 'paragraph') {
    return makeModule('paragraph', {
      id: blockId,
      markdown: nodesToMarkdown(node.content),
    })
  }
  return makeModule('paragraph', {
    id: blockId,
    markdown: plainNodeText([node]),
  })
}

function legacyRemarkMarkdown(nodes: RichNode[]): string {
  return nodes
    .map((node) => {
      if (node.type === 'heading') {
        return `**${nodesToMarkdown(node.content).trim()}**`
      }
      if (node.type === 'paragraph' || node.type === 'doc') {
        return nodesToMarkdown(node.content).trim()
      }
      if (node.type === 'bulletList') {
        return listToMarkdown(node, false)
      }
      if (node.type === 'orderedList') {
        return listToMarkdown(node, true)
      }
      if (node.type === 'taskList') {
        return todoToMarkdown(node)
      }
      if (node.type === 'blockquote') {
        return (node.content || [])
          .map((child) => nodesToMarkdown(child.content).trim())
          .join('\n\n')
      }
      if (node.type === 'horizontalRule') {
        return '---'
      }
      if (node.type === 'codeBlock') {
        return (node.content || []).map((child) => child.text || '').join('')
      }
      return nodesToMarkdown(node.content).trim()
    })
    .filter(Boolean)
    .join('\n\n')
}

function legacyContentToModules(
  content: Record<string, unknown>,
  blockId: number | null,
): EditorModule[] {
  const nodes = Array.isArray(content.content)
    ? (content.content as RichNode[])
    : []
  if (!nodes.length) {
    return [makeModule('paragraph', { id: blockId })]
  }
  return nodes.map((node, index) =>
    legacyNodeToModule(node, index === 0 ? blockId : null),
  )
}

export function blockToModules(block: DocumentBlock): EditorModule[] {
  if (block.block_type === 'code') {
    const language = block.content.language
    return [
      makeModule('code', {
        id: block.id,
        text: typeof block.content.text === 'string' ? block.content.text : '',
        language:
          language === 'c' || language === 'h' ? language : 'text',
      }),
    ]
  }
  if (block.block_type === 'image') {
    return [
      makeModule('image', {
        id: block.id,
        assetId: block.asset_id,
        alt: typeof block.content.alt === 'string' ? block.content.alt : '',
        caption:
          typeof block.content.caption === 'string' ? block.content.caption : '',
      }),
    ]
  }
  if (block.block_type === 'formula') {
    return [
      makeModule('formula', {
        id: block.id,
        latex:
          typeof block.content.latex === 'string'
            ? block.content.latex
            : '',
      }),
    ]
  }
  if (block.block_type === 'remark') {
    const moduleName = block.content.module
    if (
      typeof moduleName === 'string' &&
      TEXT_MODULE_TYPES.has(moduleName as TextModuleType) &&
      moduleName !== 'divider' &&
      moduleName !== 'table'
    ) {
      return [
        makeModule('remark', {
          id: block.id,
          remarkModule: moduleName as TextModuleType,
          markdown:
            typeof block.content.markdown === 'string'
              ? block.content.markdown
              : '',
        }),
      ]
    }
    return [
      makeModule('remark', {
        id: block.id,
        markdown: legacyRemarkMarkdown(
          Array.isArray(block.content.content)
            ? (block.content.content as RichNode[])
            : [],
        ),
      }),
    ]
  }
  if (block.block_type === 'result') {
    return [
      makeModule('result', {
        id: block.id,
        text: typeof block.content.text === 'string' ? block.content.text : '',
      }),
    ]
  }
  if (block.block_type === 'rich_text') {
    const moduleName = block.content.module
    if (moduleName === 'table') {
      const headers = Array.isArray(block.content.headers)
        ? block.content.headers.map((cell) => String(cell ?? ''))
        : ['列 1', '列 2']
      const rows = Array.isArray(block.content.rows)
        ? block.content.rows.map((row) =>
            Array.isArray(row)
              ? row.map((cell) => String(cell ?? ''))
              : [],
          )
        : [headers.map(() => '')]
      return [
        makeModule('table', {
          id: block.id,
          headers,
          rows,
        }),
      ]
    }
    if (moduleName === 'divider') {
      return [makeModule('divider', { id: block.id })]
    }
    if (
      typeof moduleName === 'string' &&
      TEXT_MODULE_TYPES.has(moduleName as TextModuleType)
    ) {
      return [
        makeModule(moduleName as TextModuleType, {
          id: block.id,
          markdown:
            typeof block.content.markdown === 'string'
              ? block.content.markdown
              : '',
        }),
      ]
    }
    return legacyContentToModules(block.content, block.id)
  }
  return []
}

export function documentToModules(document: DocumentDetail): EditorModule[] {
  return document.blocks.flatMap(blockToModules)
}

export function moduleToBlockInput(module: EditorModule): BlockInput {
  if (module.type === 'code') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'code',
      content: {
        text: module.text || '',
        language: module.language || 'text',
      },
      asset_id: null,
    }
  }
  if (module.type === 'image') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'image',
      content: {
        alt: module.alt || '',
        caption: module.caption || '',
      },
      asset_id: module.assetId ?? null,
    }
  }
  if (module.type === 'formula') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'formula',
      content: { latex: module.latex || '' },
      asset_id: null,
    }
  }
  if (module.type === 'remark') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'remark',
      content: {
        module: module.remarkModule || 'paragraph',
        markdown: module.markdown || '',
      },
      asset_id: null,
    }
  }
  if (module.type === 'result') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'result',
      content: { text: module.text || '' },
      asset_id: null,
    }
  }
  if (module.type === 'table') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'rich_text',
      content: {
        module: 'table',
        headers: module.headers || [],
        rows: module.rows || [],
      },
      asset_id: null,
    }
  }
  if (module.type === 'divider') {
    return {
      ...(module.id !== null ? { id: module.id } : {}),
      block_type: 'rich_text',
      content: { module: 'divider' },
      asset_id: null,
    }
  }
  return {
    ...(module.id !== null ? { id: module.id } : {}),
    block_type: 'rich_text',
    content: {
      module: module.type,
      markdown: module.markdown || '',
    },
    asset_id: null,
  }
}

export function modulesToBlockInputs(modules: EditorModule[]): BlockInput[] {
  return modules.map(moduleToBlockInput)
}

export function modulesToPreviewBlocks(
  modules: EditorModule[],
): DocumentBlock[] {
  return modules.map((module, index) => {
    const block = moduleToBlockInput(module)
    return {
      id: module.id ?? -(index + 1),
      block_type: block.block_type,
      content: block.content,
      asset_id: block.asset_id,
      sort_order: index,
    }
  })
}

export function moduleLabel(type: EditorModuleType): string {
  const labels: Record<EditorModuleType, string> = {
    paragraph: '段落',
    heading1: '大标题',
    heading2: '中标题',
    heading3: '小标题',
    quote: '引用',
    divider: '分隔线',
    bullet_list: '圆点列表',
    ordered_list: '编号列表',
    todo_list: '待办列表',
    table: '表格',
    code: '代码',
    image: '图片',
    formula: '公式',
    remark: '备注',
    result: '运行结果',
  }
  return labels[type]
}

export function isTextModule(module: EditorModule): boolean {
  return (
    module.type === 'remark' ||
    (module.type !== 'divider' &&
      module.type !== 'table' &&
      TEXT_MODULE_TYPES.has(module.type as TextModuleType))
  )
}

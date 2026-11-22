import type { DocumentBlock } from '../api/types'
import type { EditorModule } from './editorModel'

export function joinSourceCode(parts: string[]): string {
  let result = ''
  for (const code of parts) {
    if (code === '') {
      continue
    }
    if (result && !result.endsWith('\n') && !result.endsWith('\r')) {
      result += '\n'
    }
    result += code
  }
  return result
}

export function sourceFromBlocks(blocks: DocumentBlock[]): string {
  return joinSourceCode(
    blocks
      .filter((block) => block.block_type === 'code')
      .sort((left, right) => left.sort_order - right.sort_order)
      .map((block) =>
        typeof block.content.text === 'string' ? block.content.text : '',
      ),
  )
}

export function sourceFromModules(modules: EditorModule[]): string {
  return joinSourceCode(
    modules
      .filter((module) => module.type === 'code')
      .map((module) => module.text),
  )
}

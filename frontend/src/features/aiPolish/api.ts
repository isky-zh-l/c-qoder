import { apiRequest } from '../../api/client'

export interface AiPolishDoc {
  id: number
  title: string
  summary: string
  block_count: number
  version: number
}

export interface AiPolishResult {
  mode: string
  original: AiPolishDoc
  polished: AiPolishDoc
}

export function polishDocument(documentId: number): Promise<AiPolishResult> {
  return apiRequest<AiPolishResult>(`/documents/${documentId}/ai-polish`, {
    method: 'POST',
    body: {},
  })
}

export function choosePolishVersion(
  keepId: number,
  discardId: number,
): Promise<{ kept: { id: number; title: string } }> {
  return apiRequest(`/documents/${keepId}/ai-polish/choose`, {
    method: 'POST',
    body: { keep_id: keepId, discard_id: discardId },
  })
}
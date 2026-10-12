export type Source = { id: string; page: number; text: string; source: string; score: number; url: string }
export type Question = { id: string; number: number; text: string; focus: string; rationale: string; citation_ids: string[]; sources: Source[]; answer: string | null; plan: { query: string; anchor: string; difficulty: string }; model: string | null }
export type Profile = { skills: string[]; domains: string[]; difficulty: string; difficulty_basis: string; background: string[] }
export type Session = { id: string; role: string; status: string; mode: string; profile: Profile; questions: Question[]; summary: null | { answered: number; total_words: number; topics: string[]; response_lengths: number[]; short_responses: number[]; note: string; next_step: string } }
export type Health = { status: string; mode: string; model: string | null; chunks: number; error: string | null }
export type Role = { id: string; name: string; topics: string[] }

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : 'Check the input and try again.'
    } catch { /* Preserve the HTTP error when the body is not JSON. */ }
    throw new Error(message)
  }
  return response.status === 204 ? undefined as T : response.json()
}

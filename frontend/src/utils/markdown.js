import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({
  gfm: true,
  breaks: true
})

/**
 * Render Markdown to sanitized HTML for safe v-html display.
 */
export function renderMarkdown(source) {
  if (!source) return ''
  const html = marked.parse(String(source), { async: false })
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true }
  })
}

export function isMarkdownFile(name = '') {
  return /\.(md|markdown|mdown|mkd)$/i.test(name)
}

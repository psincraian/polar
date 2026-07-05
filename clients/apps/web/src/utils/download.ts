/**
 * Trigger a browser download for the given URL.
 *
 * Unlike `window.open(url, '_blank')`, this does not open a popup and is
 * therefore not suppressed by popup blockers when it's called outside of a
 * user gesture (e.g. from an SSE event handler after an invoice is generated).
 *
 * The URLs we download here (presigned S3 URLs) are served with a
 * `Content-Disposition: attachment` header, so navigating to them downloads
 * the file without leaving the current page.
 */
export const triggerFileDownload = (url: string, filename?: string): void => {
  const link = document.createElement('a')
  link.href = url
  link.rel = 'noopener'
  if (filename) {
    link.download = filename
  }
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

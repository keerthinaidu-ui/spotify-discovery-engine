export const env = {
  get apiBaseUrl() {
    if (process.env.NEXT_PUBLIC_API_URL) {
      return process.env.NEXT_PUBLIC_API_URL
    }
    // Dynamic client-side resolution for local development
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname
      const port = window.location.port
      if (port === '3000' || ((hostname === 'localhost' || hostname === '127.0.0.1') && port !== '8000')) {
        return `http://${hostname}:8000`
      }
    }
    if (process.env.NODE_ENV === 'development') {
      return 'http://localhost:8000'
    }
    return ''
  }
}


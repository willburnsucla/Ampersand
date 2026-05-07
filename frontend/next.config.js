/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy /api/backend/* → backend :8000 so the browser never hits CORS issues in dev
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

/** @type {import('next').NextConfig} */
const nextConfig = {
  typedRoutes: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL || 'http://127.0.0.1:8000'}/:path*`
      }
    ];
  }
};

export default nextConfig;

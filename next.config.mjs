/** @type {import('next').NextConfig} */
const nextConfig = {
  typedRoutes: true,
  async rewrites() {
    if (process.env.API_URL) {
      return [
        {
          source: '/api/:path*',
          destination: `${process.env.API_URL}/api/:path*`
        }
      ];
    }
    return [];
  }
};

export default nextConfig;

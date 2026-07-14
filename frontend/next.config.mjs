/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // React Three Fiber ships ESM; transpile three ecosystem packages.
  transpilePackages: ["three"],
  experimental: {
    // Tree-shake large icon / animation libraries by default.
    optimizePackageImports: ["lucide-react", "framer-motion"],
  },
  images: {
    formats: ["image/avif", "image/webp"],
  },
};

export default nextConfig;

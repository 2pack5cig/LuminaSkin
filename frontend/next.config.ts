import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Phone -> (ngrok) -> Next.js -> /api/* forwarded to the FastAPI backend on this laptop.
  // One public URL is enough; the backend never needs its own tunnel.
 async rewrites() {
  return {
    beforeFiles: [{ source: "/", destination: "/landing.html" }],
    afterFiles: [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/:path*" }],
  };
},
  allowedDevOrigins: ["*.ngrok-free.app", "*.ngrok-free.dev", "*.ngrok.app", "*.ngrok.io"],
};

export default nextConfig;

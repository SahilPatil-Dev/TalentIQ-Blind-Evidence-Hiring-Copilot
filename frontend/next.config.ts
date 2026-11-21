import type { NextConfig } from "next";

// "standalone" makes a small self-contained build, only needed for Docker.
// Vercel doesn't need it, so the Dockerfile turns it on with DOCKER_BUILD=1.
const nextConfig: NextConfig = {
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
};

export default nextConfig;

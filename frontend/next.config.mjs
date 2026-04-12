import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const PRIVATE_IPV4_PATTERNS = [/^10\./, /^192\.168\./, /^172\.(1[6-9]|2\d|3[0-1])\./];

const getAllowedDevOrigins = () => {
  const networkAddresses = Object.values(os.networkInterfaces())
    .flat()
    .filter((entry) => entry?.family === "IPv4" && !entry.internal)
    .map((entry) => entry.address)
    .filter((address) => PRIVATE_IPV4_PATTERNS.some((pattern) => pattern.test(address)));

  return Array.from(new Set(["localhost", "127.0.0.1", ...networkAddresses]));
};

/** @type {import('next').NextConfig} */
const baseConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: frontendRoot,
};

export default function nextConfig(phase) {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      ...baseConfig,
      allowedDevOrigins: getAllowedDevOrigins(),
      distDir: ".next-dev",
    };
  }

  return baseConfig;
}

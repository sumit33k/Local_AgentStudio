/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // When unset, the frontend auto-resolves to the same hostname on port 8000
    // at runtime, enabling cross-domain / LAN access without configuration.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
  },
};
module.exports = nextConfig;

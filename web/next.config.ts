import path from "node:path";
import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig = (phase: string): NextConfig => {
  const authMode = process.env.NEXT_PUBLIC_AUTH_MODE === "entra" ? "entra" : "dev";
  const providerImplPath =
    authMode === "entra"
      ? "./src/features/auth/provider-impl.entra.tsx"
      : "./src/features/auth/provider-impl.dev.tsx";
  const studioModeFragmentPath =
    authMode === "entra"
      ? "./src/features/studio/mode-fragment.entra.tsx"
      : "./src/features/studio/mode-fragment.dev.tsx";

  return {
    output: "export",
    assetPrefix: phase === PHASE_DEVELOPMENT_SERVER ? undefined : ".",
    experimental: {
      turbopackFileSystemCacheForBuild: false,
    },
    webpack(config) {
      config.resolve ??= {};
      config.resolve.alias ??= {};
      config.resolve.alias["@/features/auth/provider-impl"] = path.resolve(
        __dirname,
        providerImplPath,
      );
      config.resolve.alias["@/features/studio/mode-fragment"] = path.resolve(
        __dirname,
        studioModeFragmentPath,
      );
      return config;
    },
    turbopack: {
      resolveAlias: {
        "@/features/auth/provider-impl": providerImplPath,
        "@/features/studio/mode-fragment": studioModeFragmentPath,
      },
    },
  };
};

export default nextConfig;

function isTrustedStudioRoutePath(candidatePathname: string) {
  return candidatePathname === "/studio" || candidatePathname.startsWith("/studio/");
}

export function isAllowedExternalNavigation(candidateUrl: string, allowedOrigins: string[]) {
  let parsed: URL;
  try {
    parsed = new URL(candidateUrl);
  } catch {
    return false;
  }

  if (!["https:", "http:"].includes(parsed.protocol)) {
    return false;
  }

  return allowedOrigins.some((origin) => parsed.origin === origin);
}

export function isTrustedStudioFrameUrl(candidateUrl: string) {
  try {
    const parsed = new URL(candidateUrl);
    return (
      parsed.protocol === "app:" &&
      parsed.host === "studio" &&
      isTrustedStudioRoutePath(parsed.pathname)
    );
  } catch {
    return false;
  }
}

export { isTrustedStudioRoutePath };

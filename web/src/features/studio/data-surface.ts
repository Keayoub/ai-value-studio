import { ApiClientError } from "@/features/api/browser-api-client";

export function isPermissionDeniedError(error: unknown): boolean {
  return error instanceof ApiClientError && error.problem.status === 403;
}

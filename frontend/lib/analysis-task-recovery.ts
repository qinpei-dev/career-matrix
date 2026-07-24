import { ApiError, type AnalysisTask } from "./api.ts";

export const TASK_POLL_INTERVAL_MS = 2_000;
export const TASK_POLL_TIMEOUT_MS = 60_000;

export function shouldPollAnalysisTask(task: AnalysisTask): boolean {
  return task.is_running || [
    "FETCHING_JOB",
    "ANALYZING",
    "SAVING_RESULT",
  ].includes(task.status);
}

export function shouldDeleteCachedTask(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function hasTaskPollingTimedOut(
  startedAt: number,
  now: number,
): boolean {
  return now - startedAt >= TASK_POLL_TIMEOUT_MS;
}

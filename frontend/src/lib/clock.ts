// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
/** Milliseconds from a monotonic clock. Its own module so tests can move time without touching React's scheduler. */
export const now = () => performance.now();

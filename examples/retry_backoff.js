/**
 * Sample input in a language that is not Python.
 *
 * Forge sends text and reads a reply, so nothing about it is Python-specific.
 * This file exists to check that claim rather than assume it.
 *
 * Known problems, deliberately left in place:
 *
 * 1. `retry` makes one more attempt than its name promises. The loop runs
 *    while `attempt <= retries`, so `retry(fn, 3)` calls `fn` four times.
 * 2. The backoff doubles with no ceiling and no jitter. A caller passing a
 *    large retry count waits for hours, and every client retries in step.
 * 3. A failure on the last attempt is swallowed. The function returns
 *    `undefined`, which the caller cannot tell from a successful result of
 *    `undefined`, and the error that caused it is lost.
 * 4. It sleeps after the final attempt, delaying a return that has already
 *    been decided.
 *
 * This file is analysed, never executed.
 */

async function retry(fn, retries = 3, delayMs = 100) {
  let wait = delayMs;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      await new Promise((resolve) => setTimeout(resolve, wait));
      wait = wait * 2;
    }
  }
}

module.exports = { retry };

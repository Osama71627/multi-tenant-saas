import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library's own auto-cleanup registers via the global `afterEach`,
// which this project's vitest config doesn't expose (no `test.globals`,
// matching the explicit-import style used everywhere else) -- so it must
// be wired up explicitly here, or renders from earlier tests keep
// accumulating in the DOM across the whole file.
afterEach(() => {
  cleanup();
});

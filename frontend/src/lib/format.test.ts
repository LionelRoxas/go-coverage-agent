// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { describe, expect, it } from "vitest";
import { delta, duration, pct, tokens } from "./format";

describe("format", () => {
  it("formats numbers for humans", () => {
    expect(pct(81.234)).toBe("81.2%");
    expect(pct(undefined)).toBe("—");
    expect(delta(3.25)).toBe("+3.3 pp");
    expect(delta(-1)).toBe("−1.0 pp");
    expect(duration(42.4)).toBe("42s");
    expect(duration(1859.6)).toBe("30m 59s");
    expect(tokens(950)).toBe("950");
    expect(tokens(152_300)).toBe("152.3k");
  });
});

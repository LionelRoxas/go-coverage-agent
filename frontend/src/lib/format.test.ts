// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import { describe, expect, it } from "vitest";
import { ATTEMPT_LABEL, REJECTION_LABEL, delta, duration, pct, tokens } from "./format";

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

  it("labels attempts and rejections separately", () => {
    expect(ATTEMPT_LABEL.mechanical_repair).toBe("Auto-fixed (no LLM call)");
    expect(ATTEMPT_LABEL.llm_error).toBe("Model error");
    expect(REJECTION_LABEL.too_large).toBe("Too large for one request");
    expect(REJECTION_LABEL.mechanical_repair).toBeUndefined();
  });
});

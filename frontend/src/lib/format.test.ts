// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { describe, expect, it } from "vitest";
import { ATTEMPT_LABEL, REJECTION_LABEL, STOP_REASON_LABEL, checkLabel, circled, delta, duration, parseTestFailures, pct, tokenBreakdown, tokenLabel, tokens } from "./format";

describe("format", () => {
  it("labels a run's tokens with its summary calls broken out", () => {
    expect(tokenLabel(337_700)).toBe("337.7k tokens");
    expect(tokenLabel(337_700, 13_700)).toBe("351.4k tokens (337.7k run + 13.7k summary)");
    expect(tokenLabel(337_700, 27_400, 2)).toBe("365.1k tokens (337.7k run + 27.4k across 2 summaries)");
    expect(tokenBreakdown(337_700, 0)).toBeUndefined();
  });

  it("formats numbers for humans", () => {
    expect(pct(81.234)).toBe("81.2%");
    expect(pct(undefined)).toBe("—");
    expect(delta(3.25)).toBe("+3.3 pp");
    expect(delta(-1)).toBe("−1.0 pp");
    expect(duration(42.4)).toBe("42s");
    expect(duration(1859.6)).toBe("30m 59s");
    expect(tokens(950)).toBe("950");
    expect(tokens(152_300)).toBe("152.3k");
    expect(tokens(2_000_000)).toBe("2.0M");
    expect(tokens(1_500_000)).toBe("1.5M");
  });

  it("labels the llm_unavailable stop", () => {
    expect(STOP_REASON_LABEL.llm_unavailable).toBe("Groq unreachable");
  });

  it("labels attempts and rejections separately", () => {
    expect(ATTEMPT_LABEL.mechanical_repair).toBe("Auto-fixed (no LLM call)");
    expect(ATTEMPT_LABEL.llm_error).toBe("Model error");
    expect(ATTEMPT_LABEL.prompt_too_large).toBe("Prompt too large (no model call)");
    expect(REJECTION_LABEL.prompt_too_large).toBe("Prompt too large (no model call)");
    expect(REJECTION_LABEL.llm_error).toBe("Model error");
    expect(REJECTION_LABEL.too_large).toBe("Too large for one request");
    expect(REJECTION_LABEL.mechanical_repair).toBeUndefined();
  });

  it("labels checks, counting failed tests out of the tests in that version", () => {
    expect(checkLabel("accepted", 0)).toBe("Passed: compiles, go vet clean, every test asserts, tests pass twice, adds new coverage");
    expect(checkLabel("compile_error", 0)).toBe("Didn't compile");
    expect(checkLabel("vet_error", 0)).toBe("go vet failed");
    expect(checkLabel("no_gain", 0)).toBe("No new coverage");
    expect(checkLabel("guard_rejected", 0)).toBe("Rejected by the safety guard");
    expect(checkLabel("no_assertions", 0)).toBe("Tests without assertions (no t.Error or t.Fatal)");
    expect(checkLabel("test_failure", 0, 8)).toBe("Tests failed");
    expect(checkLabel("test_failure", 3, 8)).toBe("3 of 8 tests failed");
    expect(checkLabel("test_failure", 2)).toBe("2 tests failed");
    expect(checkLabel("test_failure", 1)).toBe("1 test failed");
    expect(checkLabel("something_new", 0)).toBe("something_new");
  });

  it("numbers steps with circled digits", () => {
    expect([1, 2, 3, 20].map(circled)).toEqual(["①", "②", "③", "⑳"]);
    expect(circled(21)).toBe("(21)");
  });

  it("parses unique failing tests and their first message from doubled go test output", () => {
    const run = [
      "--- FAIL: TestA (0.00s)",
      "    a_test.go:5: boom",
      "    a_test.go:6: second line",
      "--- FAIL: TestB (0.00s)",
      "    --- FAIL: TestB/sub (0.00s)",
      "        b_test.go:9: inner",
    ].join("\n");
    const out = `${run}\n${run}\nFAIL\ncoverage: 10.3% of statements\nFAIL\tm\t0.01s\nFAIL`;
    expect(parseTestFailures(out)).toEqual([
      { name: "TestA", message: "a_test.go:5: boom" },
      { name: "TestB", message: "b_test.go:9: inner" },
    ]);
    expect(parseTestFailures("--- FAIL: TestC (0.00s)\nFAIL")).toEqual([{ name: "TestC" }]);
    expect(parseTestFailures("")).toEqual([]);
  });
});

// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { describe, expect, it } from "vitest";
import {
  describeSkips, emptySkips, pathSkipReason, prepare, PrepareError, type Found, type FoundFile,
} from "./upload";

const found = (path: string, size = 10): FoundFile => ({ path, load: async () => new File(["x".repeat(size)], path.split("/").pop()!) });
const of = (...files: FoundFile[]): Found => ({ files, skippedFolders: emptySkips() });

describe("pathSkipReason", () => {
  it.each([
    ["p/.git/HEAD", "git"], ["p/vendor/x/y.go", "vendor"], ["p/a/node_modules/z.js", "node_modules"],
    ["p/.github/ci.yml", "hidden"], ["p/.env", "hidden"], ["p/a.go", null], ["p/testdata/in.txt", null], ["p/vendor.go", null],
  ])("%s -> %s", (path, want) => {
    expect(pathSkipReason(path)).toBe(want);
  });
});

describe("prepare", () => {
  it("keeps source files, counts skipped ones and never loads skipped paths", async () => {
    let loadedGit = false;
    const p = await prepare(of(
      found("proj/go.mod"), found("proj/a.go", 20), found("proj/big.bin", 1024 * 1024 + 1),
      { path: "proj/.git/HEAD", load: async () => { loadedGit = true; return new File([""], "HEAD"); } },
    ));
    expect(p.name).toBe("proj");
    expect(p.files.map((f) => f.path)).toEqual(["proj/go.mod", "proj/a.go"]);
    expect(p.bytes).toBe(30);
    expect(p.skipped).toEqual({ ...emptySkips(), git: 1, too_large: 1 });
    expect(loadedGit).toBe(false);
  });

  it("needs go.mod at the top of the folder", async () => {
    await expect(prepare(of(found("proj/a.go"), found("proj/sub/go.mod")))).rejects.toThrow(/No go.mod at the top/);
  });

  it("stops before uploading more than 3,000 files", async () => {
    const many = of(found("proj/go.mod"), ...Array.from({ length: 3000 }, (_, i) => found(`proj/f${i}.go`, 1)));
    await expect(prepare(many)).rejects.toThrow(/3,001 files .*limit is 3,000 files and 25 MB/);
  });

  it("stops before uploading more than 25 MB", async () => {
    const big = of(found("proj/go.mod"), ...Array.from({ length: 26 }, (_, i) => found(`proj/f${i}.txt`, 1024 * 1024)));
    await expect(prepare(big)).rejects.toBeInstanceOf(PrepareError);
  });

  it("uses the limits the backend reports", async () => {
    const limits = { max_files: 2, max_bytes: 50 * 1024 * 1024, max_file_bytes: 2 * 1024 * 1024 };
    const p = await prepare(of(found("proj/go.mod"), found("proj/big.go", 1024 * 1024 + 1)), limits);
    expect(p.files).toHaveLength(2); // 1.0 MB is under this backend's 2 MB per-file limit
    await expect(prepare(of(found("proj/go.mod"), found("proj/a.go"), found("proj/b.go")), limits))
      .rejects.toThrow(/3 files .*files over 2 MB\. The upload limit is 2 files and 50 MB/);
  });

  it("rejects an empty folder", async () => {
    await expect(prepare(of())).rejects.toThrow(/empty/);
  });
});

describe("describeSkips", () => {
  it("adds counts from both sides and names them in plain words", () => {
    expect(describeSkips([{ ...emptySkips(), git: 120 }, { ...emptySkips(), binary: 3 }])).toBe("120 files in .git, 3 binaries");
    expect(describeSkips([emptySkips()])).toBe("");
  });

  it("names folders a drop never read, and the configured size limit", () => {
    expect(describeSkips([{ ...emptySkips(), too_large: 2 }], { ...emptySkips(), git: 1, node_modules: 2, hidden: 1 }, 2 * 1024 * 1024))
      .toBe("2 files over 2 MB, the .git folder, 2 node_modules folders, 1 hidden folder");
  });
});

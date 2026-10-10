// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { RepoPicker, type PickerTab } from "./RepoPicker";
import { ApiError } from "@/lib/api";
import type { RepoInfo, Sample, UploadResult } from "@/lib/types";
import { emptySkips } from "@/lib/upload";

const sample = (id: string, downloaded: boolean): Sample => ({
  id, name: `o/${id}`, description: `${id} description`, license: "MIT", ref: "v1.0.0", path: id, downloaded,
});
const folder: RepoInfo = { path: "mine", module: "example.com/mine", go_files: 4, test_files: 2 };

function Harness(p: Partial<React.ComponentProps<typeof RepoPicker>> & { start?: PickerTab }) {
  const [tab, setTab] = useState<PickerTab>(p.start ?? "samples");
  const [value, setValue] = useState("");
  return (
    <>
      <RepoPicker tab={tab} onTabChange={setTab} samples={[sample("semver", true), sample("btree", false), sample("decimal", false)]}
                  folders={[]} value={value} onChange={setValue} onDownload={async () => {}} onRefresh={async () => {}}
                  onUpload={vi.fn()} hostDir={null} {...p} />
      <output data-testid="value">{value}</output>
    </>
  );
}

describe("RepoPicker", () => {
  it("shows sample cards with licence and Ready or Download badges, and selects a ready one", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const ready = screen.getByRole("button", { name: /o\/semver/ });
    expect(ready).toHaveTextContent("Ready");
    expect(ready).toHaveTextContent("MIT");
    expect(screen.getByRole("button", { name: /o\/btree/ })).toHaveTextContent("Download");
    await user.click(ready);
    expect(screen.getByTestId("value")).toHaveTextContent("semver");
    expect(ready).toHaveAttribute("aria-pressed", "true");
  });

  it("disables the other cards while downloading and shows the error on the failed card", async () => {
    const user = userEvent.setup();
    let reject!: (e: Error) => void;
    const onDownload = vi.fn(() => new Promise<void>((_, rej) => { reject = rej; }));
    render(<Harness onDownload={onDownload} />);
    await user.click(screen.getByRole("button", { name: /o\/btree/ }));
    expect(onDownload).toHaveBeenCalledWith("btree");
    expect(screen.getByRole("button", { name: /o\/btree/ })).toHaveTextContent("Downloading…");
    expect(screen.getByRole("button", { name: /o\/decimal/ })).toBeDisabled();
    reject(new Error("git clone failed: nope"));
    expect(await screen.findByRole("alert")).toHaveTextContent("git clone failed: nope");
    await waitFor(() => expect(screen.getByRole("button", { name: /o\/decimal/ })).toBeEnabled());
  });

  it("ignores a second click on the downloading card and keeps every card disabled", async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn(() => new Promise<void>(() => {}));
    render(<Harness onDownload={onDownload} />);
    const card = screen.getByRole("button", { name: /o\/btree/ });
    await user.dblClick(card);
    expect(onDownload).toHaveBeenCalledTimes(1);
    expect(card).toBeDisabled();
    expect(screen.getByRole("button", { name: /o\/semver/ })).toBeDisabled();
  });

  it("shows placeholder sample cards with a status message while loading", () => {
    render(<Harness loading samples={[]} />);
    expect(screen.getByText("Loading sample repositories…")).toHaveAttribute("role", "status");
    expect(screen.getByTestId("samples-loading").querySelectorAll("[data-skeleton]").length).toBeGreaterThan(0);
  });

  it("has no placeholders once loaded", () => {
    render(<Harness />);
    expect(screen.queryByTestId("samples-loading")).not.toBeInTheDocument();
  });

  it("only the active tab references a panel", () => {
    render(<Harness />);
    expect(screen.getByRole("tab", { name: "Sample repos" })).toHaveAttribute("aria-controls", "panel-samples");
    expect(screen.getByRole("tab", { name: "Your folders" })).not.toHaveAttribute("aria-controls");
  });

  it("has tablist semantics and moves between tabs with the arrow keys", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const samples = screen.getByRole("tab", { name: "Sample repos" });
    const folders = screen.getByRole("tab", { name: "Your folders" });
    expect(samples).toHaveAttribute("aria-selected", "true");
    expect(folders).toHaveAttribute("tabindex", "-1");
    samples.focus();
    await user.keyboard("{ArrowRight}");
    expect(folders).toHaveAttribute("aria-selected", "true");
    expect(folders).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "tab-folders");
    await user.keyboard("{ArrowRight}");
    expect(samples).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{End}");
    expect(folders).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Home}");
    expect(samples).toHaveFocus();
  });

  it("shows the empty state, mounted folder, upload action and the HOST_REPOS_DIR note on Your folders", async () => {
    const onRefresh = vi.fn(async () => {});
    const user = userEvent.setup();
    render(<Harness start="folders" hostDir="C:\Users\me\code" onRefresh={onRefresh} />);
    expect(screen.getByText(/No Go modules of your own yet/)).toBeInTheDocument();
    expect(screen.getByText("C:\\Users\\me\\code", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText("Choose a folder…")).toBeInTheDocument();
    expect(screen.getByText(/your original folder is never changed. Re-upload to refresh./)).toBeInTheDocument();
    expect(screen.getByText(/For large projects or to keep a folder in sync/)).toBeInTheDocument();
    expect(screen.getByText("HOST_REPOS_DIR=C:\\Users\\you\\code")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onRefresh).toHaveBeenCalled();
  });

  it("lists the user's own modules and selects one", async () => {
    const user = userEvent.setup();
    render(<Harness start="folders" folders={[folder]} />);
    await user.click(screen.getByRole("button", { name: /mine/ }));
    expect(screen.getByTestId("value")).toHaveTextContent("mine");
    expect(screen.queryByText(/No Go modules of your own/)).not.toBeInTheDocument();
  });

  it("has no free-text path input", () => {
    render(<Harness />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  describe("folder upload", () => {
    const result = (over: Partial<UploadResult> = {}): UploadResult =>
      ({ path: "uploads/myproj", module: "example.com/myproj", go_files: 30, test_files: 12, skipped: emptySkips(), ...over });
    const picked = (path: string, size = 10) => {
      const f = new File(["x".repeat(size)], path.split("/").pop()!);
      Object.defineProperty(f, "webkitRelativePath", { value: path });
      return f;
    };
    const project = () => [picked("myproj/go.mod"), picked("myproj/a.go"), picked("myproj/.git/HEAD"),
      picked("myproj/.git/config"), picked("myproj/vendor/x/y.go"), picked("myproj/big.go", 1024 * 1024 + 1)];
    type OnUpload = React.ComponentProps<typeof RepoPicker>["onUpload"];

    function UploadHarness({ onUpload }: { onUpload: OnUpload }) {
      const [value, setValue] = useState("");
      const upload: OnUpload = async (files, name, progress) => {
        const r = await onUpload(files, name, progress);
        setValue(r.path);
        return r;
      };
      return (
        <>
          <RepoPicker tab="folders" onTabChange={() => {}} samples={[]} folders={[]} value={value} onChange={setValue}
                      onDownload={async () => {}} onRefresh={async () => {}} onUpload={upload} hostDir={null} />
          <output data-testid="value">{value}</output>
        </>
      );
    }

    it("pre-filters the chosen folder, uploads relative paths and reports what was skipped", async () => {
      const onUpload = vi.fn<OnUpload>(async (_files, _name, progress) => {
        progress(0.5);
        return result({ skipped: { ...emptySkips(), binary: 3 } });
      });
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      const input = screen.getByTestId("folder-input") as HTMLInputElement;
      expect(input.webkitdirectory).toBe(true);
      await user.upload(input, project());
      await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1));
      const [files, name] = onUpload.mock.calls[0];
      expect(files.map((f) => f.path)).toEqual(["myproj/go.mod", "myproj/a.go"]);
      expect(name).toBeUndefined();
      expect(await screen.findByText("Uploaded myproj (42 Go files). Skipped: 2 files in .git, 1 in vendor, 1 file over 1 MB, 3 binaries."))
        .toBeInTheDocument();
      expect(screen.getByTestId("value")).toHaveTextContent("uploads/myproj");
    });

    it("shows upload progress while sending", async () => {
      let progress!: (x: number) => void;
      const onUpload = vi.fn<OnUpload>((_files, _name, p) => {
        progress = p;
        return new Promise<UploadResult>(() => {});
      });
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      await user.upload(screen.getByTestId("folder-input"), project());
      expect(await screen.findByText("Uploading 2 files (0.00 MB)…")).toBeInTheDocument();
      expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
      progress(0.4);
      await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40"));
    });

    it("offers a rename when the name is taken and retries with the new name", async () => {
      const onUpload = vi.fn<OnUpload>()
        .mockRejectedValueOnce(new ApiError(409, "name_taken", "repos/uploads/myproj already exists and was not created by an upload."))
        .mockResolvedValueOnce(result({ path: "uploads/myproj-new" }));
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      await user.upload(screen.getByTestId("folder-input"), project());
      expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
      const box = screen.getByLabelText("Upload as");
      expect(box).toHaveValue("myproj-2");
      await user.clear(box);
      await user.type(box, "myproj-new");
      await user.click(screen.getByRole("button", { name: "Rename and upload" }));
      await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(2));
      expect(onUpload.mock.calls[1][0]).toEqual(onUpload.mock.calls[0][0]);
      expect(onUpload.mock.calls[1][1]).toBe("myproj-new");
      expect(await screen.findByText(/Uploaded myproj-new/)).toBeInTheDocument();
      expect(screen.getByTestId("value")).toHaveTextContent("uploads/myproj-new");
    });

    it("stops a folder over the limit before uploading anything", async () => {
      const onUpload = vi.fn<OnUpload>();
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      const many = [picked("big/go.mod"), ...Array.from({ length: 3000 }, (_, i) => picked(`big/f${i}.go`, 1))];
      await user.upload(screen.getByTestId("folder-input"), many);
      expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent(/3,001 files .*HOST_REPOS_DIR/);
      expect(onUpload).not.toHaveBeenCalled();
    });

    it("shows the server's message for a rejected upload", async () => {
      const onUpload = vi.fn<OnUpload>().mockRejectedValue(new ApiError(413, "upload_too_large", "This folder is too large to upload."));
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      await user.upload(screen.getByTestId("folder-input"), project());
      expect(await screen.findByRole("alert")).toHaveTextContent("This folder is too large to upload.");
      expect(screen.queryByLabelText("Upload as")).not.toBeInTheDocument();
    });

    const fileEntry = (path: string, size = 10) => ({
      isFile: true, isDirectory: false, fullPath: `/${path}`, name: path.split("/").pop()!,
      file: (ok: (f: File) => void) => ok(new File(["x".repeat(size)], path.split("/").pop()!)),
    });
    /** A directory whose reader hands out `batches` one per readEntries call, then an empty batch. */
    const dirEntry = (path: string, ...batches: unknown[][]) => {
      let opened = false;
      return {
        isFile: false, isDirectory: true, fullPath: `/${path}`, name: path.split("/").pop()!,
        createReader: () => {
          opened = true;
          let i = 0;
          return { readEntries: (ok: (e: unknown[]) => void) => ok(batches[i++] ?? []) };
        },
        get opened() { return opened; },
      };
    };
    const drop = (...entries: unknown[]) => ({
      dataTransfer: { items: entries.map((e) => ({ kind: "file", webkitGetAsEntry: () => e })) },
    });

    it("reads a dropped folder recursively, never opening skipped folders, and uploads it", async () => {
      const onUpload = vi.fn<OnUpload>(async () => result());
      render(<UploadHarness onUpload={onUpload} />);
      const nodeModules = dirEntry("myproj/node_modules", [fileEntry("myproj/node_modules/z.js")]);
      const git = dirEntry("myproj/.git", [fileEntry("myproj/.git/HEAD")]);
      const tree = dirEntry("myproj", [
        fileEntry("myproj/go.mod"),
        dirEntry("myproj/pkg", [fileEntry("myproj/pkg/b.go")]),
        nodeModules, git,
      ]);
      const zone = screen.getByTestId("folder-drop");
      fireEvent.dragOver(zone);
      expect(zone).toHaveAttribute("data-over", "true");
      fireEvent.drop(zone, drop(tree));
      await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1));
      expect(onUpload.mock.calls[0][0].map((f) => f.path)).toEqual(["myproj/go.mod", "myproj/pkg/b.go"]);
      expect(nodeModules.opened).toBe(false);
      expect(git.opened).toBe(false);
      expect(await screen.findByText(/Skipped: the \.git folder, 1 node_modules folder\./)).toBeInTheDocument();
      expect(zone).not.toHaveAttribute("data-over");
    });

    it("keeps reading a folder until readEntries returns an empty batch", async () => {
      const onUpload = vi.fn<OnUpload>(async () => result());
      render(<UploadHarness onUpload={onUpload} />);
      const first = [fileEntry("myproj/go.mod"), ...Array.from({ length: 99 }, (_, i) => fileEntry(`myproj/a${i}.go`))];
      const second = Array.from({ length: 50 }, (_, i) => fileEntry(`myproj/b${i}.go`));
      fireEvent.drop(screen.getByTestId("folder-drop"), drop(dirEntry("myproj", first, second)));
      await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1));
      expect(onUpload.mock.calls[0][0]).toHaveLength(150);
    });

    it("keeps the drop highlight while the pointer moves over the zone's own children", () => {
      render(<UploadHarness onUpload={vi.fn<OnUpload>()} />);
      const zone = screen.getByTestId("folder-drop");
      fireEvent.dragOver(zone);
      // jsdom's fireEvent.dragLeave drops relatedTarget, so dispatch the native event React listens to.
      const leave = (to: Element) => fireEvent(zone, new MouseEvent("dragleave", { bubbles: true, relatedTarget: to }));
      leave(screen.getByText("or drag the project folder here"));
      expect(zone).toHaveAttribute("data-over", "true");
      leave(document.body);
      expect(zone).not.toHaveAttribute("data-over");
    });

    it("says it is saving once every byte is sent, in the same live region", async () => {
      let progress!: (x: number) => void;
      const onUpload = vi.fn<OnUpload>((_files, _name, p) => {
        progress = p;
        return new Promise<UploadResult>(() => {});
      });
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      const live = within(screen.getByTestId("folder-drop")).getByRole("status");
      await user.upload(screen.getByTestId("folder-input"), project());
      await waitFor(() => expect(live).toHaveTextContent("Uploading 2 files"));
      progress(1);
      await waitFor(() => expect(live).toHaveTextContent("Saving on the server…"));
      expect(within(screen.getByTestId("folder-drop")).getByRole("status")).toBe(live);
    });

    it("suggests a rename the backend won't cut back to the taken name, and focuses it", async () => {
      const long = "p".repeat(70);
      const onUpload = vi.fn<OnUpload>().mockRejectedValueOnce(new ApiError(409, "name_taken", "taken"));
      const user = userEvent.setup();
      render(<UploadHarness onUpload={onUpload} />);
      await user.upload(screen.getByTestId("folder-input"), [picked(`${long}/go.mod`)]);
      const box = await screen.findByLabelText("Upload as");
      expect(box).toHaveValue(`${"p".repeat(62)}-2`);
      expect((box as HTMLInputElement).value.length).toBeLessThanOrEqual(64);
      expect(box).toHaveFocus();
    });

    it("uses the upload limits the backend reports", async () => {
      const onUpload = vi.fn<OnUpload>();
      const user = userEvent.setup();
      render(<RepoPicker tab="folders" onTabChange={() => {}} samples={[]} folders={[]} value="" onChange={() => {}}
                         onDownload={async () => {}} onRefresh={async () => {}} onUpload={onUpload} hostDir={null}
                         uploadLimits={{ max_files: 1, max_bytes: 1024, max_file_bytes: 1024 }} />);
      await user.upload(screen.getByTestId("folder-input"), project());
      expect(await screen.findByRole("alert")).toHaveTextContent(/The upload limit is 1 files and 0 MB/);
      expect(onUpload).not.toHaveBeenCalled();
    });

    it("asks for one folder when files are dropped", async () => {
      const onUpload = vi.fn<OnUpload>();
      render(<UploadHarness onUpload={onUpload} />);
      fireEvent.drop(screen.getByTestId("folder-drop"), drop(fileEntry("a.go"), fileEntry("b.go")));
      expect(await screen.findByRole("alert")).toHaveTextContent("Drop one project folder");
      expect(onUpload).not.toHaveBeenCalled();
    });
  });
});

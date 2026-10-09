// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { RepoPicker, type PickerTab } from "./RepoPicker";
import type { RepoInfo, Sample } from "@/lib/types";

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
                  hostDir={null} {...p} />
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

  it("shows the empty state, mounted folder and the add-your-own note on Your folders", async () => {
    const onRefresh = vi.fn(async () => {});
    const user = userEvent.setup();
    render(<Harness start="folders" hostDir="C:\Users\me\code" onRefresh={onRefresh} />);
    expect(screen.getByText(/No Go modules of your own found yet/)).toBeInTheDocument();
    expect(screen.getByText("C:\\Users\\me\\code", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add your own repository" })).toBeInTheDocument();
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
});

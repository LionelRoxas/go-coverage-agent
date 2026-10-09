// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FolderUpload } from "./FolderUpload";

const input = () => screen.getByTestId("folder-input") as HTMLInputElement;

describe("FolderUpload feedback while the browser reads a folder", () => {
  it("says it is waiting for the browser as soon as the picker opens", () => {
    render(<FolderUpload onUpload={vi.fn()} />);
    fireEvent.click(input());
    expect(screen.getByRole("status")).toHaveTextContent(/Waiting for your browser to read the folder/);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("goes back to idle when the picker is closed without choosing", () => {
    render(<FolderUpload onUpload={vi.fn()} />);
    fireEvent.click(input());
    fireEvent(input(), new Event("cancel"));
    expect(screen.getByRole("status")).toHaveTextContent("");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("shows an error instead of doing nothing when no files come through", () => {
    const onUpload = vi.fn();
    render(<FolderUpload onUpload={onUpload} />);
    fireEvent.click(input());
    fireEvent.change(input(), { target: { files: [] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/No files came through from that folder/);
    expect(onUpload).not.toHaveBeenCalled();
  });
});

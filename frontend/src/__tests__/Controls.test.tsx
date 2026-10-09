import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Controls from "../viewer/Controls";

describe("Controls", () => {
  it("speed selection calls onSpeedChange with the chosen value", async () => {
    const onSpeedChange = vi.fn();
    const user = userEvent.setup();
    render(
      <Controls
        playing={false}
        onTogglePlay={vi.fn()}
        speed={1}
        onSpeedChange={onSpeedChange}
        frameIndex={0}
        frameCount={40}
        onSeek={vi.fn()}
        showFullPath={false}
        onToggleFullPath={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "0.25x" }));
    expect(onSpeedChange).toHaveBeenCalledWith(0.25);
  });

  it("scrubber updates the rendered frame index via onSeek", () => {
    const onSeek = vi.fn();
    render(
      <Controls
        playing={false}
        onTogglePlay={vi.fn()}
        speed={1}
        onSpeedChange={vi.fn()}
        frameIndex={0}
        frameCount={40}
        onSeek={onSeek}
        showFullPath={false}
        onToggleFullPath={vi.fn()}
      />,
    );
    const scrubber = screen.getByLabelText("Frame scrubber");
    fireEvent.change(scrubber, { target: { value: "15" } });
    expect(onSeek).toHaveBeenCalledWith(15);
  });
});

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Timeline from "../viewer/Timeline";
import type { Flag, Frame } from "../types";

function frame(frameId: number, event = "None"): Frame {
  return { frameId, event, objects: [] };
}

function flag(overrides: Partial<Flag>): Flag {
  return {
    flagId: "f1",
    gameId: 1,
    playId: 1,
    errorFrameId: 2,
    involvedNflIds: [1],
    team: "KC",
    errorType: "sack_allowed",
    confidenceLevel: "Confirmed",
    explanation: "x",
    epaCost: null,
    detail: {},
    ...overrides,
  };
}

describe("Timeline", () => {
  it("renders one flag marker per flag, colored by confidence level", () => {
    const frames = [frame(1, "ball_snap"), frame(2), frame(3), frame(4, "pass_forward")];
    const flags = [
      flag({ flagId: "a", errorFrameId: 1, confidenceLevel: "Confirmed" }),
      flag({ flagId: "b", errorFrameId: 3, confidenceLevel: "Likely" }),
      flag({ flagId: "c", errorFrameId: 4, confidenceLevel: "Possible" }),
    ];

    const { container } = render(<Timeline frames={frames} currentFrameIndex={0} flags={flags} onSeek={vi.fn()} />);
    const markers = container.querySelectorAll(".timeline__flag");
    expect(markers).toHaveLength(3);

    const styles = Array.from(markers).map((m) => (m as HTMLElement).style.background);
    expect(styles).toContain("var(--confirmed)");
    expect(styles).toContain("var(--likely)");
    expect(styles).toContain("var(--possible)");
  });

  it("renders event markers for recognized events only", () => {
    const frames = [frame(1, "ball_snap"), frame(2, "line_set"), frame(3, "pass_forward")];
    const { container } = render(<Timeline frames={frames} currentFrameIndex={0} flags={[]} onSeek={vi.fn()} />);
    // line_set has no label mapping and should not render a marker.
    expect(container.querySelectorAll(".timeline__event")).toHaveLength(2);
  });
});

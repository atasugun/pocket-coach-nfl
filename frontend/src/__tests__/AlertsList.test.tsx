import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AlertsList from "../pages/AlertsList";
import { api } from "../api";
import type { Flag } from "../types";

vi.mock("../api", () => ({
  api: { flags: vi.fn() },
}));

const sampleFlag: Flag = {
  flagId: "f1",
  gameId: 2021090900,
  playId: 97,
  errorFrameId: 22,
  involvedNflIds: [100],
  team: "KC",
  errorType: "sack_allowed",
  confidenceLevel: "Confirmed",
  explanation: "Blocker allowed a sack.",
  epaCost: -1.2,
  detail: {},
};

describe("AlertsList", () => {
  beforeEach(() => {
    vi.mocked(api.flags).mockResolvedValue([sampleFlag]);
  });

  it("row links to the play viewer at the flag's error frame", async () => {
    render(
      <MemoryRouter>
        <AlertsList scope={{ myTeam: "KC", opponent: "BUF", mode: "self" }} />
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByText("Blocker allowed a sack."));
    const link = screen.getByText("Blocker allowed a sack.").closest("a");
    expect(link).toHaveAttribute("href", expect.stringContaining("/plays/2021090900/97"));
    expect(link).toHaveAttribute("href", expect.stringContaining("frame=22"));
  });

  it("shows 'cost unavailable' when epaCost is null", async () => {
    vi.mocked(api.flags).mockResolvedValue([{ ...sampleFlag, epaCost: null }]);
    render(
      <MemoryRouter>
        <AlertsList scope={{ myTeam: "KC", opponent: "BUF", mode: "self" }} />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText("cost unavailable"));
  });
});

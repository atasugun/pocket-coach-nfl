import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import TeamSelector from "../components/TeamSelector";
import { api } from "../api";

vi.mock("../api", () => ({
  api: { teams: vi.fn() },
}));

describe("TeamSelector", () => {
  beforeEach(() => {
    vi.mocked(api.teams).mockResolvedValue(["KC", "BUF", "DAL"]);
  });

  it("calls onChange with the selected myTeam, opponent, and mode", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<TeamSelector scope={{ myTeam: null, opponent: null, mode: "self" }} onChange={onChange} />);

    await waitFor(() => expect(screen.getAllByRole("option", { name: "KC" }).length).toBeGreaterThan(0));

    await user.selectOptions(screen.getByLabelText("My team"), "KC");
    expect(onChange).toHaveBeenCalledWith({ myTeam: "KC" });

    await user.selectOptions(screen.getByLabelText("Opponent"), "BUF");
    expect(onChange).toHaveBeenCalledWith({ opponent: "BUF" });

    await user.click(screen.getByRole("tab", { name: "Opponent" }));
    expect(onChange).toHaveBeenCalledWith({ mode: "opponent" });
  });

  it("reflects the active mode as selected", async () => {
    render(<TeamSelector scope={{ myTeam: "KC", opponent: "BUF", mode: "opponent" }} onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "Opponent" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Self-scout" })).toHaveAttribute("aria-selected", "false");
    await waitFor(() => expect(screen.getAllByRole("option").length).toBeGreaterThan(0));
  });
});

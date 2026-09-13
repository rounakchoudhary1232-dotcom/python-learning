import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dashboard } from "./dashboard";

describe("Dashboard", () => {
  it("renders the ULTRON identity and command interface", () => {
    render(<Dashboard />);
    expect(screen.getByText("ULTRON")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Good evening, Sir." })).toBeInTheDocument();
    expect(screen.getByLabelText("Ask ULTRON anything")).toBeInTheDocument();
  });
});

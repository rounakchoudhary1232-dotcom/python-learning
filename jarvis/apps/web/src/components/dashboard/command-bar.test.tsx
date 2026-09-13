import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CommandBar } from "./command-bar";
describe("CommandBar", () => { it("discloses that messaging is not connected in Phase 1", () => { render(<CommandBar />); fireEvent.change(screen.getByLabelText(/ask jarvis anything/i), { target: { value: "Plan my day" } }); fireEvent.click(screen.getByLabelText(/send request/i)); expect(screen.getByRole("status")).toHaveTextContent(/Phase 3 AI service/i); }); });

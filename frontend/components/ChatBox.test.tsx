import React from "react";
import { render, screen } from "@testing-library/react";

import { ChatBox } from "./ChatBox";

describe("ChatBox", () => {
  it("renders the manager chat heading and prompt buttons", () => {
    render(<ChatBox authToken="test-token" />);
    expect(screen.getByText("Manager Chat")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ask" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Summarize today's customer complaints." })).toBeTruthy();
  });
});

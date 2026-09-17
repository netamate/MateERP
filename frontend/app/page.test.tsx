import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("MateERP Phase 2 home", () => {
  it("renders the engineering foundation heading", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "Engineering Foundation" })).toBeInTheDocument();
  });
});

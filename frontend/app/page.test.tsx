import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "./page";

describe("MateERP Phase 4 home", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: "Authentication credentials were not provided." }),
      }),
    );
  });

  it("renders the secure sign-in gate for an anonymous browser", async () => {
    render(<Home />);
    expect(await screen.findByRole("heading", { name: /MateERP/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});

export type User = {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
};

export type Membership = {
  id: string;
  organization_id: string;
  user: User;
  role: string;
  status: string;
  all_legal_entities: boolean;
  legal_entity_ids: string[];
  permissions: string[];
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  status: string;
  timezone: string;
};

export type LegalEntity = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  status: string;
  base_currency: string;
  timezone: string;
  fiscal_year_start_month: number;
  fiscal_year_start_day: number;
};

export type SessionPayload = {
  user: User;
  memberships: Membership[];
  organizations: Organization[];
  active_organization_id: string | null;
  active_legal_entity_id: string | null;
  active_legal_entities: LegalEntity[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function ensureCsrfToken(): Promise<string> {
  const response = await fetch("/api/v1/auth/csrf/", {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiError("Unable to initialize secure request token.", response.status);
  }
  const data = (await response.json()) as { csrf_token: string };
  return data.csrf_token;
}

async function request<T>(
  url: string,
  init: RequestInit = {},
  csrfProtected = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfProtected) {
    headers.set("X-CSRFToken", await ensureCsrfToken());
  }

  const response = await fetch(url, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    let message = "Request failed.";
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // Keep the safe generic message for non-JSON error responses.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getSession(): Promise<SessionPayload> {
  return request<SessionPayload>("/api/v1/session/");
}

export function login(email: string, password: string): Promise<SessionPayload> {
  return request<SessionPayload>(
    "/api/v1/auth/login/",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    true,
  );
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout/", { method: "POST" }, true);
}

export function setContext(
  organizationId: string,
  legalEntityId: string | null,
): Promise<SessionPayload> {
  return request<SessionPayload>(
    "/api/v1/session/context/",
    {
      method: "POST",
      body: JSON.stringify({
        organization_id: organizationId,
        legal_entity_id: legalEntityId,
      }),
    },
    true,
  );
}

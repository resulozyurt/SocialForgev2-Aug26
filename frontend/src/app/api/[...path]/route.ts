// Server-side proxy to the SocialForge backend.
//
// The browser calls same-origin `/api/...`; this handler forwards to the backend
// `/api/v1/...` and injects the admin HTTP Basic credentials server-side, so the
// admin password never reaches the client bundle.

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const ADMIN_USER = process.env.ADMIN_USERNAME ?? "admin";
const ADMIN_PASS = process.env.ADMIN_PASSWORD ?? "change-me";

const authHeader =
  "Basic " + Buffer.from(`${ADMIN_USER}:${ADMIN_PASS}`).toString("base64");

async function forward(req: NextRequest, path: string[]) {
  const target = `${BACKEND_URL}/api/v1/${path.join("/")}${req.nextUrl.search}`;

  const headers: Record<string, string> = { Authorization: authHeader };
  const contentType = req.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  const method = req.method;
  const body =
    method === "GET" || method === "HEAD" ? undefined : await req.text();

  const res = await fetch(target, { method, headers, body, cache: "no-store" });
  const text = await res.text();

  return new NextResponse(text, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
    },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}

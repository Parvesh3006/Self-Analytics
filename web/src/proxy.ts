import { NextResponse, type NextRequest } from "next/server";

/** Browser password prompt for hosted deployments. Off unless APP_PASSWORD is set. */
export function proxy(request: NextRequest) {
  const password = process.env.APP_PASSWORD;
  if (!password) return NextResponse.next();
  const header = request.headers.get("authorization") ?? "";
  if (header.startsWith("Basic ")) {
    const supplied = atob(header.slice(6)).split(":").slice(1).join(":");
    if (supplied === password) return NextResponse.next();
  }
  return new NextResponse("Password required", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="Self Analytics"' } });
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };

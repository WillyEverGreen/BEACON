import { NextResponse } from "next/server";

interface ProxyOptions {
  path: string;
  role?: "viewer" | "auditor" | "admin";
}

/**
 * Proxy requests to the BEACON backend API with proper authentication.
 * 
 * @throws Error if required environment variables are not set
 */
export async function proxyToBeacon(request: Request, options: ProxyOptions): Promise<Response> {
  // Validate required environment variables
  const backendUrl = process.env.BEACON_API_URL;
  if (!backendUrl) {
    console.error("BEACON_API_URL environment variable is not set");
    return NextResponse.json(
      { error: "Backend configuration error. Please contact support." },
      { status: 500 }
    );
  }
  
  // Trim leading/trailing slashes and build the target URL
  const targetPath = options.path.startsWith("/") ? options.path : `/${options.path}`;
  const targetUrl = new URL(targetPath, backendUrl);
  
  // Forward search parameters from the incoming request
  const incomingUrl = new URL(request.url);
  incomingUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.append(key, value);
  });

  // Prepare headers
  const headers = new Headers();
  
  // Forward content-type and other safe headers
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  
  // Set X-API-Key based on role - validate env vars are set
  if (options.role === "admin") {
    const apiKey = process.env.BOOTSTRAP_ADMIN_API_KEY;
    if (!apiKey) {
      console.error("BOOTSTRAP_ADMIN_API_KEY environment variable is not set");
      return NextResponse.json(
        { error: "API authentication not configured. Please contact support." },
        { status: 500 }
      );
    }
    headers.set("X-API-Key", apiKey);
  } else if (options.role === "auditor") {
    const apiKey = process.env.BOOTSTRAP_AUDITOR_API_KEY;
    if (!apiKey) {
      console.error("BOOTSTRAP_AUDITOR_API_KEY environment variable is not set");
      return NextResponse.json(
        { error: "API authentication not configured. Please contact support." },
        { status: 500 }
      );
    }
    headers.set("X-API-Key", apiKey);
  } else if (options.role === "viewer") {
    const apiKey = process.env.BOOTSTRAP_VIEWER_API_KEY;
    if (!apiKey) {
      console.error("BOOTSTRAP_VIEWER_API_KEY environment variable is not set");
      return NextResponse.json(
        { error: "API authentication not configured. Please contact support." },
        { status: 500 }
      );
    }
    headers.set("X-API-Key", apiKey);
  }
  
  // Forward Authorization / X-Supabase-Token if they exist
  const supabaseToken = request.headers.get("x-supabase-token");
  if (supabaseToken) {
    headers.set("X-Supabase-Token", supabaseToken);
  }
  const auth = request.headers.get("authorization");
  if (auth) {
    headers.set("authorization", auth);
  }

  // Get body if method has one
  let body: string | undefined = undefined;
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
    try {
      body = await request.text();
    } catch {
      // no body
    }
  }

  try {
    let response: Response;
    try {
      response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers,
        body,
        cache: "no-store",
      });
    } catch (fetchErr: unknown) {
      // Automatic IPv6/IPv4 fallback: If localhost failed, try 127.0.0.1
      if (targetUrl.hostname === "localhost") {
        const fallbackUrl = new URL(targetUrl.toString());
        fallbackUrl.hostname = "127.0.0.1";
        response = await fetch(fallbackUrl.toString(), {
          method: request.method,
          headers,
          body,
          cache: "no-store",
        });
      } else {
        throw fetchErr;
      }
    }
    
    const responseHeaders = new Headers(response.headers);
    // Delete compression and length headers because fetch() automatically decompressed the body
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    responseHeaders.delete("transfer-encoding");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error: unknown) {
    console.error("proxyToBeacon failed:", error);
    return NextResponse.json(
      {
        error: "BEACON backend is offline or unreachable. Ensure the backend server is running on port 8000 (`py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`).",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 502 }
    );
  }
}

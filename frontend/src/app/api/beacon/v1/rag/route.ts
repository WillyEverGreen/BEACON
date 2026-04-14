import { randomUUID } from "crypto";
import { proxyToBeacon } from "@/lib/beaconProxy";

export async function POST(request: Request): Promise<Response> {
  const requestId = request.headers.get("x-request-id") || randomUUID();

  if (process.env.BEACON_AI_ENABLED !== "true") {
    return Response.json(
      {
        code: "ai_disabled",
        ai_degraded: true,
        message: "AI layer disabled",
        request_id: requestId,
      },
      {
        status: 503,
        headers: {
          "x-request-id": requestId,
        },
      },
    );
  }

  return proxyToBeacon(request, {
    path: "/v1/rag",
    role: "auditor",
  });
}

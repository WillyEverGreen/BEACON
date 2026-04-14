import { proxyToBeacon } from "@/lib/beaconProxy";

export async function GET(request: Request): Promise<Response> {
  return proxyToBeacon(request, {
    path: "/v1/audit/cache/stats",
    role: "admin",
  });
}

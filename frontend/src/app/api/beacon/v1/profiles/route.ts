import { proxyToBeacon } from "@/lib/beaconProxy";

export async function GET(request: Request): Promise<Response> {
  return proxyToBeacon(request, {
    path: "/v1/api/profiles",
    role: "viewer",
  });
}

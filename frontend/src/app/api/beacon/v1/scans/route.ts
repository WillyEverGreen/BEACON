import { proxyToBeacon } from "@/lib/beaconProxy";

export async function POST(request: Request): Promise<Response> {
  return proxyToBeacon(request, {
    path: "/v1/api/scans/",
    role: "auditor",
  });
}

import { proxyToBeacon } from "@/lib/beaconProxy";

export async function GET(request: Request): Promise<Response> {
  return proxyToBeacon(request, {
    path: "/v1/api/projects/",
    role: "viewer",
  });
}

export async function POST(request: Request): Promise<Response> {
  return proxyToBeacon(request, {
    path: "/v1/api/projects/",
    role: "auditor",
  });
}

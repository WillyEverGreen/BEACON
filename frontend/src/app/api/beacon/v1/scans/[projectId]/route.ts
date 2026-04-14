import { proxyToBeacon } from "@/lib/beaconProxy";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const { projectId } = await context.params;
  return proxyToBeacon(request, {
    path: `/v1/api/scans/${encodeURIComponent(projectId)}`,
    role: "viewer",
  });
}

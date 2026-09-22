import { proxyToBeacon } from "@/lib/beaconProxy";

type RouteContext = {
  params: Promise<{ projectId: string; scanId: string }>;
};

export async function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { projectId, scanId } = await context.params;
  return proxyToBeacon(request, {
    path: `/v1/api/scans/${encodeURIComponent(projectId)}/${encodeURIComponent(scanId)}/statement`,
    role: "viewer",
  });
}

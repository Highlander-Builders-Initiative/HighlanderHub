import { ClubAvatar } from "@/components/ui/ClubAvatar";

type EventHost = { host: string; hostHandle?: string };

const MAX_HOST_AVATARS = 3;

/**
 * Up to three club pictures, overlapping, each cut out from the next by a
 * canvas ring. Leads the "By …" line on feed cards, compact rows and the
 * event detail.
 */
export function HostAvatars({ hosts, size }: { hosts: readonly EventHost[]; size: number }) {
  return (
    <span className="flex shrink-0 -space-x-1">
      {hosts.slice(0, MAX_HOST_AVATARS).map((host) => (
        // flex, so the ring hugs the avatar instead of the line box.
        <span key={host.hostHandle || host.host} className="flex rounded-full ring-2 ring-canvas">
          <ClubAvatar handle={host.hostHandle} name={host.host || host.hostHandle || ""} size={size} />
        </span>
      ))}
    </span>
  );
}

/** The event's hosts with a name or handle, falling back to its own host. */
export function eventHosts(event: {
  host: string;
  hostHandle?: string;
  hosts?: EventHost[];
}): EventHost[] {
  return (event.hosts?.length ? event.hosts : [event]).filter(
    (host) => host.host || host.hostHandle
  );
}

# Corporate VPN Access Policy

The corporate VPN provides secure remote access to internal systems, including ticketing tools, source control, and infrastructure dashboards. Employees and approved contractors must use the VPN when accessing internal applications from any non-corporate network. Split tunneling is disabled for standard users to reduce data exfiltration risk and to ensure threat monitoring coverage.

All VPN users must authenticate with company single sign-on and multi-factor authentication. Shared credentials are prohibited. If a user believes their credentials were exposed, they must report the incident to IT Security within one hour and rotate credentials immediately.

Endpoint posture checks are enforced at session start and periodically during active sessions. Minimum requirements include: full-disk encryption enabled, supported operating system patch level, active endpoint protection agent, and screen lock timeout of 15 minutes or less. Devices that fail posture checks are automatically moved to a restricted remediation network.

Users must disconnect from VPN when access is no longer required and should not run personal peer-to-peer, proxy, or remote-control software while connected. Administrative VPN profiles are limited to authorized teams and require manager approval plus quarterly revalidation.

Logs for connection attempts, source IP, device posture status, and session duration are retained for security and compliance reviews under the enterprise data retention schedule.

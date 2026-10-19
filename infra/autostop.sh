#!/bin/bash
# Runs ON THE SERVER (via infra/remote.sh "$(cat infra/autostop.sh)"): stops the server 3 hours after each start,
# so a forgotten server can't keep spending. Change AUTOSTOP_HOURS and re-run to adjust; 0 turns it off.
# The EC2 instance's shutdown behaviour is "stop" (not terminate), so nothing is lost: models and data stay on disk.
HOURS=${AUTOSTOP_HOURS:-3}
if [ "$HOURS" = 0 ]; then systemctl disable --now carebridge-autostop.timer; echo "auto-stop off"; exit 0; fi
# An older setup ran the stop service directly at boot; only the timer may start it (else: stop on every start)
rm -f /etc/systemd/system/multi-user.target.wants/carebridge-autostop.service
cat > /etc/systemd/system/carebridge-autostop.service <<UNIT
[Unit]
Description=Stop the CareBridge server to save money
[Service]
Type=oneshot
ExecStart=/usr/bin/logger "CareBridge auto-stop: shutting down after ${HOURS}h"
ExecStart=/usr/bin/systemctl poweroff
UNIT
cat > /etc/systemd/system/carebridge-autostop.timer <<UNIT
[Unit]
Description=Stop the CareBridge server ${HOURS} hours after it starts
[Timer]
OnBootSec=${HOURS}h
AccuracySec=1min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload && systemctl enable carebridge-autostop.timer
# If the server has already been up longer than that, the boot timer would stop it at once: give the current run
# its own countdown from now instead (the boot timer takes over from the next start).
UP=$(cut -d. -f1 /proc/uptime)
systemctl stop 'carebridge-autostop-now.timer' 2>/dev/null || true
if [ "$UP" -ge $((HOURS * 3600)) ]; then
  systemd-run --unit=carebridge-autostop-now --on-active=${HOURS}h /usr/bin/systemctl poweroff >/dev/null
  echo "this run: stops ${HOURS}h from now"
else
  systemctl start carebridge-autostop.timer
fi
echo "auto-stop: ${HOURS}h after boot"; systemctl list-timers carebridge-autostop.timer --no-pager | head -3

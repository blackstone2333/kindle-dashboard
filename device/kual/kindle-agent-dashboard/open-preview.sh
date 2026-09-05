#!/bin/sh

# This top-level launcher follows the most widely supported KUAL action form.
printf '%s\n' "Kindle Agent Dashboard launcher invoked" > /mnt/us/documents/kindle-agent-dashboard-kual.log

exec /bin/sh /mnt/us/koreader/koreader.sh \
	--kual \
	/mnt/us/documents/kindle-agent-dashboard-v13.png

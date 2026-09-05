#!/bin/sh

# Leave a marker so a failed hand-off can be distinguished from a KOReader error.
printf '%s\n' "Kindle Agent Dashboard launcher invoked" > /mnt/us/documents/kindle-agent-dashboard-kual.log

exec /bin/sh /mnt/us/koreader/koreader.sh \
	--kual \
	/mnt/us/documents/kindle-agent-dashboard-v13.png

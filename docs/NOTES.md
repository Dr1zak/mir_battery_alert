# Developer Notes

## battery_alert_node.py

### Percentage normalisation

`sensor_msgs/BatteryState` has no enforced convention for `percentage`. Some drivers report `0.0–1.0`, others report `0–100`. The node checks if the incoming value is `<= 1.0` and multiplies by 100 if so. This handles both conventions without configuration, but it does mean a battery reporting exactly `1.0%` would be misread as `100%` — an edge case that doesn't happen in practice.

### Alert firing conditions

Webhooks fire when:
- The battery level crosses into a new severity level (`OK → WARN`, `WARN → CRITICAL`), **or**
- The level stays in `WARN` or `CRITICAL` and `alert_cooldown` seconds have elapsed since the last alert

This means you get one immediate alert on entry into a bad state, then periodic reminders until someone acts. Without the cooldown check, a robot sitting at 9% for an hour would only alert once.

### Diagnostics timer vs subscriber

The diagnostics publisher runs on a 1 Hz `rospy.Timer`, decoupled from the battery topic's message rate. This ensures `/diagnostics` keeps publishing even if the battery topic goes silent — which surfaces a stale/no-data warning rather than the diagnostics aggregator just not seeing the component at all.

---

## config/params.yaml

- `battery_topic` — the node subscribes to whatever topic is set here. If you're using the `mir_robot` driver, you'll need to either remap `/mir_status` → `/battery_state` or change this to `/mir_status` and update the subscriber message type in the node.
- `alert_cooldown` — in seconds. `300` = 5 minutes. Set lower in testing, higher in noisy environments where operators don't want repeated pings.
- `slack_webhook_url` / `teams_webhook_url` — both can be active at the same time. Leave empty (`""`) to skip.

---

## launch/battery_alert.launch

- `respawn="true"` with `respawn_delay="5"` — the node restarts automatically after a crash with a 5-second delay. This is intentional for a monitoring node that should always be running.
- CLI args override `params.yaml` values. The YAML loads first, then individual `<param>` tags overwrite whatever the args resolve to. This means the YAML serves as a baseline and you can override single values at launch time without touching the file.

---

## MiR topic situation

MiR AMRs don't publish `sensor_msgs/BatteryState` natively. Two paths:

**Option A — mir_robot driver**
The driver publishes `/mir_status` (`mir_msgs/MirStatus`). Write a republisher that reads `battery_percentage` from that message and forwards it as `BatteryState`, then point `battery_topic` at `/battery_state`.

**Option B — REST API polling**
No driver needed. Poll `http://<MIR_IP>/api/v2.0.0/status` and publish the result as `BatteryState`. The default auth header `YWRtaW46YWRtaW4=` is base64 for `admin:admin` — change it if the robot's credentials have been updated. Polling every 5 seconds (`rospy.Rate(0.2)`) is more than enough; battery percentage doesn't change fast enough to need higher frequency.

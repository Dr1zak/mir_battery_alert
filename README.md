# mir_battery_alert

It's a single ROS node that watches the battery topic, publishes to `/diagnostics`, and hits a Slack or Teams webhook when charge drops below whatever thresholds you configure. That's it. No bloat.

---

## Requirements

- ROS Noetic (Melodic with Python 3 should work too)
- `python3-requests` — `sudo apt install python3-requests`
- `sensor_msgs`, `diagnostic_msgs` — already in any standard ROS install

---

## Installation

```bash
cd ~/catkin_ws/src
git clone <this-repo> mir_battery_alert

cd ~/catkin_ws
catkin_make

chmod +x src/mir_battery_alert/scripts/battery_alert_node.py
```

---

## Configuration

Everything lives in `config/params.yaml`. The defaults are sane, but you'll want to set your robot name and at least one webhook URL.

| Parameter            | Default          | What it does                                        |
|----------------------|------------------|-----------------------------------------------------|
| `robot_name`         | `MiR_01`         | Shows up in alert messages and diagnostics          |
| `battery_topic`      | `/battery_state` | Topic to subscribe to — see the MiR note below      |
| `warn_threshold`     | `20.0`           | First alert fires here (%)                          |
| `critical_threshold` | `10.0`           | Second, louder alert fires here (%)                 |
| `alert_cooldown`     | `300`            | Seconds before the same alert fires again           |
| `slack_webhook_url`  | `""`             | Leave empty to skip Slack                           |
| `teams_webhook_url`  | `""`             | Leave empty to skip Teams                           |

---

## Usage

```bash
# Default config
roslaunch mir_battery_alert battery_alert.launch

# Override at launch time
roslaunch mir_battery_alert battery_alert.launch \
  robot_name:=MiR_02 \
  warn_threshold:=25.0 \
  slack_webhook_url:=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

The node respawns automatically if it crashes.

---

## The MiR Topic Situation

MiR doesn't publish `sensor_msgs/BatteryState` out of the box. You have two options:

**Option A — mir_robot driver**

If you're running the [`mir_robot`](https://github.com/dfki-ric/mir_robot) ROS driver, it exposes `/mir_status` using `mir_msgs/MirStatus`. You can either adapt the node to subscribe to that directly, or write a small republisher that reads `battery_percentage` from it and forwards it as a `BatteryState` message.

**Option B — REST API (no driver needed)**

This is the more common setup on a real deployment. The MiR has a REST API and you can poll it directly:

```python
#!/usr/bin/env python3
import rospy, requests
from sensor_msgs.msg import BatteryState

rospy.init_node("mir_battery_republisher")
pub = rospy.Publisher("/battery_state", BatteryState, queue_size=1)
mir_ip = rospy.get_param("~mir_ip", "192.168.12.20")
rate = rospy.Rate(0.2)  # polling every 5s is plenty

while not rospy.is_shutdown():
    r = requests.get(
        f"http://{mir_ip}/api/v2.0.0/status",
        headers={"Authorization": "Basic YWRtaW46YWRtaW4="}
    )
    msg = BatteryState()
    msg.percentage = r.json().get("battery_percentage", 0)
    pub.publish(msg)
    rate.sleep()
```

Drop that alongside the main node and remap the topic. Done.

---

## Checking Diagnostics

```bash
# GUI
rosrun rqt_runtime_monitor rqt_runtime_monitor

# Terminal
rostopic echo /diagnostics
```

Level mapping: `OK` above warn threshold, `WARN` below it, `ERROR` below critical, and `WARN` (stale) if no data has come in yet.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE).

#!/usr/bin/env python3

import rospy
import requests
import time

from sensor_msgs.msg import BatteryState
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue


def send_slack(webhook_url: str, message: str) -> bool:
    try:
        r = requests.post(webhook_url, json={"text": message}, timeout=5)
        return r.status_code == 200
    except Exception as e:
        rospy.logwarn(f"[mir_battery_alert] Slack webhook failed: {e}")
        return False


def send_teams(webhook_url: str, title: str, message: str) -> bool:
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "FF0000",
        "summary": title,
        "sections": [{"activityTitle": title, "activityText": message}]
    }
    try:
        r = requests.post(webhook_url, json=payload, timeout=5)
        return r.status_code == 200
    except Exception as e:
        rospy.logwarn(f"[mir_battery_alert] Teams webhook failed: {e}")
        return False


class BatteryAlertNode:

    def __init__(self):
        rospy.init_node("battery_alert_node", anonymous=False)

        self.robot_name         = rospy.get_param("~robot_name", "MiR")
        self.warn_threshold     = rospy.get_param("~warn_threshold", 20.0)
        self.critical_threshold = rospy.get_param("~critical_threshold", 10.0)
        self.cooldown_sec       = rospy.get_param("~alert_cooldown", 300)
        self.slack_url          = rospy.get_param("~slack_webhook_url", "")
        self.teams_url          = rospy.get_param("~teams_webhook_url", "")
        self.battery_topic      = rospy.get_param("~battery_topic", "/battery_state")

        self._last_alert_time = 0.0
        self._last_level      = "OK"
        self._latest_pct      = None

        self._diag_pub = rospy.Publisher("/diagnostics", DiagnosticArray, queue_size=10)
        self._sub      = rospy.Subscriber(self.battery_topic, BatteryState, self._battery_cb, queue_size=1)

        rospy.Timer(rospy.Duration(1.0), self._publish_diagnostics)

        rospy.loginfo(
            f"[mir_battery_alert] Monitoring '{self.battery_topic}' | "
            f"WARN < {self.warn_threshold}% | CRITICAL < {self.critical_threshold}%"
        )

    def _battery_cb(self, msg: BatteryState):
        pct = msg.percentage
        if pct <= 1.0:
            pct *= 100.0
        self._latest_pct = pct
        self._check_and_alert(pct)

    def _check_and_alert(self, pct: float):
        now = time.time()

        if pct <= self.critical_threshold:
            level = "CRITICAL"
        elif pct <= self.warn_threshold:
            level = "WARN"
        else:
            level = "OK"

        level_changed    = level != self._last_level
        cooldown_expired = (now - self._last_alert_time) >= self.cooldown_sec

        if level in ("WARN", "CRITICAL") and (level_changed or cooldown_expired):
            self._fire_webhooks(level, pct)
            self._last_alert_time = now

        self._last_level = level

    def _fire_webhooks(self, level: str, pct: float):
        emoji = "🔴" if level == "CRITICAL" else "🟡"
        title = f"{emoji} {level}: {self.robot_name} battery at {pct:.1f}%"
        body  = (
            f"{self.robot_name} battery is at {pct:.1f}%. "
            f"Threshold: {self.critical_threshold}% (critical) / "
            f"{self.warn_threshold}% (warn). Please charge the robot."
        )

        rospy.logwarn(f"[mir_battery_alert] {title}")

        if self.slack_url:
            ok = send_slack(self.slack_url, f"*{title}*\n{body}")
            rospy.loginfo(f"[mir_battery_alert] Slack: {'sent' if ok else 'FAILED'}")

        if self.teams_url:
            ok = send_teams(self.teams_url, title, body)
            rospy.loginfo(f"[mir_battery_alert] Teams: {'sent' if ok else 'FAILED'}")

    def _publish_diagnostics(self, _event):
        arr              = DiagnosticArray()
        arr.header.stamp = rospy.Time.now()

        status             = DiagnosticStatus()
        status.name        = f"{self.robot_name}/battery"
        status.hardware_id = self.robot_name

        if self._latest_pct is None:
            status.level   = DiagnosticStatus.WARN
            status.message = "No battery data received yet"
        elif self._latest_pct <= self.critical_threshold:
            status.level   = DiagnosticStatus.ERROR
            status.message = f"CRITICAL: {self._latest_pct:.1f}%"
        elif self._latest_pct <= self.warn_threshold:
            status.level   = DiagnosticStatus.WARN
            status.message = f"Low battery: {self._latest_pct:.1f}%"
        else:
            status.level   = DiagnosticStatus.OK
            status.message = f"OK: {self._latest_pct:.1f}%"

        status.values = [
            KeyValue("percentage",        str(round(self._latest_pct, 1)) if self._latest_pct else "N/A"),
            KeyValue("warn_threshold",    str(self.warn_threshold)),
            KeyValue("critical_threshold", str(self.critical_threshold)),
            KeyValue("last_alert_level",  self._last_level),
        ]

        arr.status.append(status)
        self._diag_pub.publish(arr)

    def spin(self):
        rospy.spin()


if __name__ == "__main__":
    try:
        node = BatteryAlertNode()
        node.spin()
    except rospy.ROSInterruptException:
        pass

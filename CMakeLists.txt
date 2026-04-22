cmake_minimum_required(VERSION 3.0.2)
project(mir_battery_alert)

find_package(catkin REQUIRED COMPONENTS
  rospy
  sensor_msgs
  diagnostic_msgs
)

catkin_package()

catkin_install_python(PROGRAMS scripts/battery_alert_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)

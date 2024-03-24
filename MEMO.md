Add Baby Enclave
========================
* selfdrive/car/gm/fingerprints.py#L183
* selfdrive/car/gm/interface.py#L356
* selfdrive/car/gm/values.py#L125 #L180 #L259
* selfdrive/car/torque_data/override.toml #L43
* selfdrive/controls/lib/desire_helper.py #L10
* selfdrive/controls/lib/events.py #L751
* selfdrive/thermald/thermald.py #L331
* selfdrive/car/torque_data/lat_models/BUICK BABY ENCLAVE 2020.json
* selfdrive/car/torque_data/lat_models/BUICK BABY ENCLAVE AVENIR 2020.json
* selfdrive/frogpilot/ui/vehicle_settings.cc#L55 #L95 #L103

NNFF CEM Tuning
========================
* selfdrive/car/gm/gmcan.py#L258 #L286 / #L300 #L328

Change turn signal
========================
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_1.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_2.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_3.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_4.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_5.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_6.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_7.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_8.png
* selfdrive/frogpilot/assets/custom_themes/tesla_theme/images/turn_signal_1_red.png

UI & Translation
========================
* common/params.cc
* selfdrive/car/car_helpers.py
* selfdrive/controls/controlsd.py
* selfdrive/controls/lib/events.py
* selfdrive/frogpilot/fleetmanager/helpers.py
* selfdrive/frogpilot/ui/control_settings.cc
* selfdrive/frogpilot/ui/control_settings.h
* selfdrive/frogpilot/ui/visual_settings.cc
* selfdrive/frogpilot/ui/visual_settings.h
* selfdrive/manager/manager.py
* selfdrive/ui/qt/offroad/settings.cc
* selfdrive/ui/qt/offroad/software_settings.cc
* selfdrive/ui/qt/onroad.cc
* selfdrive/ui/ui.cc
* selfdrive/ui/ui.h


Driver Privacy Protection
========================
* common/params.cc 
  * #L271 {"DriverPrivacyProtection", PERSISTENT},
* selfdrive/manager/manager.py 
  * #L139 ("DriverPrivacyProtection", "0"),
* selfdrive/frogpilot/fleetmanager/helpers.py
  * #L472 "DriverPrivacyProtection",
* selfdrive/frogpilot/ui/visual_settings.cc
  * #L54 DriverPrivacyProtection
* selfdrive/frogpilot/ui/visual_settings.h
  * #L38 DriverPrivacyProtection
* selfdrive/controls/controlsd.py
  * #L203 self.driver_privacy_protection
  * #L204 self.driver_privacy_protection
  * #L199 ADD "driverMonitoringState"
* selfdrive/ui/ui.cc
  * #L351 scene.driver_privacy_protection
* selfdrive/ui/ui.h
  * #L192 bool driver_privacy_protection;
* selfdrive/ui/qt/onroad.cc
  * #L1201 //DMoji
  * #L1202 !scene.driver_privacy_protection

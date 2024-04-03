import copy
from cereal import car
from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import mean
from opendbc.can.can_define import CANDefine
from opendbc.can.parser import CANParser
from openpilot.selfdrive.car.interfaces import CarStateBase
from openpilot.selfdrive.car.gm.values import DBC, AccState, CanBus, STEER_THRESHOLD, GMFlags, CC_ONLY_CAR, CAMERA_ACC_CAR, SDGM_CAR
from openpilot.selfdrive.controls.lib.drive_helpers import CRUISE_LONG_PRESS

TransmissionType = car.CarParams.TransmissionType
NetworkLocation = car.CarParams.NetworkLocation
GearShifter = car.CarState.GearShifter
STANDSTILL_THRESHOLD = 10 * 0.0311 * CV.KPH_TO_MS


class CarState(CarStateBase):
  def __init__(self, CP):
    super().__init__(CP)
    can_define = CANDefine(DBC[CP.carFingerprint]["pt"])
    self.shifter_values = can_define.dv["ECMPRDNL2"]["PRNDL2"]
    self.cluster_speed_hyst_gap = CV.KPH_TO_MS / 2.
    self.cluster_min_speed = CV.KPH_TO_MS / 2.

    self.loopback_lka_steering_cmd_updated = False
    self.loopback_lka_steering_cmd_ts_nanos = 0
    self.pt_lka_steering_cmd_counter = 0
    self.cam_lka_steering_cmd_counter = 0
    self.buttons_counter = 0

    # FrogPilot variables
    self.single_pedal_mode = False

    # FrogPilot variables
    self.display_menu = False

    self.display_timer = 0

  def update(self, pt_cp, cam_cp, loopback_cp, frogpilot_variables):
    ret = car.CarState.new_message()

    self.prev_cruise_buttons = self.cruise_buttons
    if self.CP.carFingerprint not in SDGM_CAR:
      self.cruise_buttons = pt_cp.vl["ASCMSteeringButton"]["ACCButtons"]
      self.buttons_counter = pt_cp.vl["ASCMSteeringButton"]["RollingCounter"]
      self.onstar_gps_longitude = 0. # ONSTAR_GPS_TEST
      self.onstar_gps_latitude = 0. # ONSTAR_GPS_TEST
      self.onstar_gps_altitude = 0. # ONSTAR_GPS_TEST
      ret.onstarGpsLongitude = 0. # ONSTAR_GPS_TEST
      ret.onstarGpsLatitude = 0. # ONSTAR_GPS_TEST
      ret.onstarGpsAltitude = 0. # ONSTAR_GPS_TEST
      ret.currentGearNumber = 0 # ONSTAR_GPS_TEST
      ret.nextGearNumber = 0 # ONSTAR_GPS_TEST
    else:
      self.cruise_buttons = cam_cp.vl["ASCMSteeringButton"]["ACCButtons"]
      self.buttons_counter = cam_cp.vl["ASCMSteeringButton"]["RollingCounter"]
      self.onstar_gps_longitude = cam_cp.vl["TCICOnStarGPSPosition"]["GPSLongitude"] # ONSTAR_GPS_TEST
      self.onstar_gps_latitude = cam_cp.vl["TCICOnStarGPSPosition"]["GPSLatitude"] # ONSTAR_GPS_TEST
      self.onstar_gps_altitude = cam_cp.vl["TCICOnStartGPSAltitude"]["GPSAltitude"] # ONSTAR_GPS_TEST
      ret.onstarGpsLongitude = self.onstar_gps_longitude # ONSTAR_GPS_TEST
      ret.onstarGpsLatitude = self.onstar_gps_latitude # ONSTAR_GPS_TEST
      ret.onstarGpsAltitude = self.onstar_gps_altitude # ONSTAR_GPS_TEST
      ret.currentGearNumber = cam_cp.vl["ECMPRDNL2"]["CurrentGearNumber"] # ONSTAR_GPS_TEST
      ret.nextGearNumber = cam_cp.vl["ECMPRDNL2"]["NextGearNumber"] # ONSTAR_GPS_TEST

    self.pscm_status = copy.copy(pt_cp.vl["PSCMStatus"])
    # This is to avoid a fault where you engage while still moving backwards after shifting to D.
    # An Equinox has been seen with an unsupported status (3), so only check if either wheel is in reverse (2)
    self.moving_backward = (pt_cp.vl["EBCMWheelSpdRear"]["RLWheelDir"] == 2) or (pt_cp.vl["EBCMWheelSpdRear"]["RRWheelDir"] == 2)

    # Variables used for avoiding LKAS faults
    self.loopback_lka_steering_cmd_updated = len(loopback_cp.vl_all["ASCMLKASteeringCmd"]["RollingCounter"]) > 0
    if self.loopback_lka_steering_cmd_updated:
      self.loopback_lka_steering_cmd_ts_nanos = loopback_cp.ts_nanos["ASCMLKASteeringCmd"]["RollingCounter"]
    if self.CP.networkLocation == NetworkLocation.fwdCamera and not self.CP.flags & GMFlags.NO_CAMERA.value:
      self.pt_lka_steering_cmd_counter = pt_cp.vl["ASCMLKASteeringCmd"]["RollingCounter"]
      self.cam_lka_steering_cmd_counter = cam_cp.vl["ASCMLKASteeringCmd"]["RollingCounter"]

    ret.wheelSpeeds = self.get_wheel_speeds(
      pt_cp.vl["EBCMWheelSpdFront"]["FLWheelSpd"],
      pt_cp.vl["EBCMWheelSpdFront"]["FRWheelSpd"],
      pt_cp.vl["EBCMWheelSpdRear"]["RLWheelSpd"],
      pt_cp.vl["EBCMWheelSpdRear"]["RRWheelSpd"],
    )
    ret.vEgoRaw = mean([ret.wheelSpeeds.fl, ret.wheelSpeeds.fr, ret.wheelSpeeds.rl, ret.wheelSpeeds.rr])
    ret.vEgo, ret.aEgo = self.update_speed_kf(ret.vEgoRaw)
    # sample rear wheel speeds, standstill=True if ECM allows engagement with brake
    ret.standstill = ret.wheelSpeeds.rl <= STANDSTILL_THRESHOLD and ret.wheelSpeeds.rr <= STANDSTILL_THRESHOLD

    if pt_cp.vl["ECMPRDNL2"]["ManualMode"] == 1:
      ret.gearShifter = self.parse_gear_shifter("T")
    else:
      ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(pt_cp.vl["ECMPRDNL2"]["PRNDL2"], None))

    if self.CP.flags & GMFlags.NO_ACCELERATOR_POS_MSG.value:
      ret.brake = pt_cp.vl["EBCMBrakePedalPosition"]["BrakePedalPosition"] / 0xd0
    else:
      ret.brake = pt_cp.vl["ECMAcceleratorPos"]["BrakePedalPos"]
    if self.CP.networkLocation == NetworkLocation.fwdCamera:
      ret.brakePressed = pt_cp.vl["ECMEngineStatus"]["BrakePressed"] != 0
    else:
      # Some Volt 2016-17 have loose brake pedal push rod retainers which causes the ECM to believe
      # that the brake is being intermittently pressed without user interaction.
      # To avoid a cruise fault we need to use a conservative brake position threshold
      # https://static.nhtsa.gov/odi/tsbs/2017/MC-10137629-9999.pdf
      ret.brakePressed = ret.brake >= 8

    # Regen braking is braking
    if self.CP.transmissionType == TransmissionType.direct:
      ret.regenBraking = pt_cp.vl["EBCMRegenPaddle"]["RegenPaddle"] != 0
      self.single_pedal_mode = ret.gearShifter == GearShifter.low or pt_cp.vl["EVDriveMode"]["SinglePedalModeActive"] == 1

    if self.CP.enableGasInterceptor:
      ret.gas = (pt_cp.vl["GAS_SENSOR"]["INTERCEPTOR_GAS"] + pt_cp.vl["GAS_SENSOR"]["INTERCEPTOR_GAS2"]) / 2.
      threshold = 15 if self.CP.carFingerprint in CAMERA_ACC_CAR else 4
      ret.gasPressed = ret.gas > threshold
    else:
      ret.gas = pt_cp.vl["AcceleratorPedal2"]["AcceleratorPedal2"] / 254.
      ret.gasPressed = ret.gas > 1e-5

    ret.steeringAngleDeg = pt_cp.vl["PSCMSteeringAngle"]["SteeringWheelAngle"]
    ret.steeringRateDeg = pt_cp.vl["PSCMSteeringAngle"]["SteeringWheelRate"]
    ret.steeringTorque = pt_cp.vl["PSCMStatus"]["LKADriverAppldTrq"]
    ret.steeringTorqueEps = pt_cp.vl["PSCMStatus"]["LKATorqueDelivered"]
    ret.steeringPressed = abs(ret.steeringTorque) > STEER_THRESHOLD

    # 0 inactive, 1 active, 2 temporarily limited, 3 failed
    self.lkas_status = pt_cp.vl["PSCMStatus"]["LKATorqueDeliveredStatus"]
    ret.steerFaultTemporary = self.lkas_status == 2
    ret.steerFaultPermanent = self.lkas_status == 3

    if self.CP.carFingerprint not in SDGM_CAR:
      # 1 - open, 0 - closed
      ret.doorOpen = (pt_cp.vl["BCMDoorBeltStatus"]["FrontLeftDoor"] == 1 or
                      pt_cp.vl["BCMDoorBeltStatus"]["FrontRightDoor"] == 1 or
                      pt_cp.vl["BCMDoorBeltStatus"]["RearLeftDoor"] == 1 or
                      pt_cp.vl["BCMDoorBeltStatus"]["RearRightDoor"] == 1)

      # 1 - latched
      ret.seatbeltUnlatched = pt_cp.vl["BCMDoorBeltStatus"]["LeftSeatBelt"] == 0
      ret.leftBlinker = pt_cp.vl["BCMTurnSignals"]["TurnSignals"] == 1
      ret.rightBlinker = pt_cp.vl["BCMTurnSignals"]["TurnSignals"] == 2

      ret.parkingBrake = pt_cp.vl["BCMGeneralPlatformStatus"]["ParkBrakeSwActive"] == 1
    else:
      # 1 - open, 0 - closed
      ret.doorOpen = (cam_cp.vl["BCMDoorBeltStatus"]["FrontLeftDoor"] == 1 or
                      cam_cp.vl["BCMDoorBeltStatus"]["FrontRightDoor"] == 1 or
                      cam_cp.vl["BCMDoorBeltStatus"]["RearLeftDoor"] == 1 or
                      cam_cp.vl["BCMDoorBeltStatus"]["RearRightDoor"] == 1)

      # 1 - latched
      ret.seatbeltUnlatched = cam_cp.vl["BCMDoorBeltStatus"]["LeftSeatBelt"] == 0
      ret.leftBlinker = cam_cp.vl["BCMTurnSignals"]["TurnSignals"] == 1
      ret.rightBlinker = cam_cp.vl["BCMTurnSignals"]["TurnSignals"] == 2

      ret.parkingBrake = cam_cp.vl["BCMGeneralPlatformStatus"]["ParkBrakeSwActive"] == 1
    ret.cruiseState.available = pt_cp.vl["ECMEngineStatus"]["CruiseMainOn"] != 0
    ret.espDisabled = pt_cp.vl["ESPStatus"]["TractionControlOn"] != 1
    ret.accFaulted = (pt_cp.vl["AcceleratorPedal2"]["CruiseState"] == AccState.FAULTED or
                      pt_cp.vl["EBCMFrictionBrakeStatus"]["FrictionBrakeUnavailable"] == 1)

    ret.cruiseState.enabled = pt_cp.vl["AcceleratorPedal2"]["CruiseState"] != AccState.OFF
    ret.cruiseState.standstill = pt_cp.vl["AcceleratorPedal2"]["CruiseState"] == AccState.STANDSTILL
    if self.CP.networkLocation == NetworkLocation.fwdCamera and not self.CP.flags & GMFlags.NO_CAMERA.value:
      if self.CP.carFingerprint not in CC_ONLY_CAR:
        ret.cruiseState.speed = cam_cp.vl["ASCMActiveCruiseControlStatus"]["ACCSpeedSetpoint"] * CV.KPH_TO_MS
      if self.CP.carFingerprint not in SDGM_CAR:
        ret.stockAeb = cam_cp.vl["AEBCmd"]["AEBCmdActive"] != 0
      else:
        ret.stockAeb = False
      # openpilot controls nonAdaptive when not pcmCruise
      if self.CP.pcmCruise:
        ret.cruiseState.nonAdaptive = cam_cp.vl["ASCMActiveCruiseControlStatus"]["ACCCruiseState"] not in (2, 3)
    if self.CP.carFingerprint in CC_ONLY_CAR:
      ret.accFaulted = False
      ret.cruiseState.speed = pt_cp.vl["ECMCruiseControl"]["CruiseSetSpeed"] * CV.KPH_TO_MS
      ret.cruiseState.enabled = pt_cp.vl["ECMCruiseControl"]["CruiseActive"] != 0

    if self.CP.enableBsm:
      if self.CP.carFingerprint not in SDGM_CAR:
        ret.leftBlindspot = pt_cp.vl["BCMBlindSpotMonitor"]["LeftBSM"] == 1
        ret.rightBlindspot = pt_cp.vl["BCMBlindSpotMonitor"]["RightBSM"] == 1
      else:
        ret.leftBlindspot = cam_cp.vl["BCMBlindSpotMonitor"]["LeftBSM"] == 1
        ret.rightBlindspot = cam_cp.vl["BCMBlindSpotMonitor"]["RightBSM"] == 1

    # FrogPilot functions
    has_camera = self.CP.networkLocation == NetworkLocation.fwdCamera
    has_camera &= not self.CP.flags & GMFlags.NO_CAMERA.value
    has_camera &= not self.CP.carFingerprint in (CC_ONLY_CAR)

    if self.CP.carFingerprint in SDGM_CAR:
      distance_pressed = cam_cp.vl["ASCMSteeringButton"]["DistanceButton"]
    else:
      distance_pressed = pt_cp.vl["ASCMSteeringButton"]["DistanceButton"]

    # Driving personalities function - Credit goes to Mangomoose!
    if ret.cruiseState.available:
      # Sync with the onroad UI button
      if self.fpf.personality_changed_via_ui:
        self.personality_profile = self.fpf.current_personality
        self.fpf.reset_personality_changed_param()

      if distance_pressed:
        self.distance_pressed_counter += 1

        if not self.distance_previously_pressed:
          self.display_timer = 350

      elif self.distance_previously_pressed:
        # Set the distance lines on the dash to match the new personality if the button was held down for less than 0.5 seconds
        if self.distance_pressed_counter < CRUISE_LONG_PRESS and frogpilot_variables.personalities_via_wheel:
          if has_camera:
            # Need to subtract by 1 to comply with the personality profiles of "0", "1", and "2"
            self.personality_profile = cam_cp.vl["ASCMActiveCruiseControlStatus"]["ACCGapLevel"] - 1
          else:
            self.personality_profile = (self.personality_profile + 2) % 3

          self.fpf.distance_button_function(self.personality_profile)

        self.distance_pressed_counter = 0

      # Check if the display is open
      if self.display_timer > 0:
        self.display_timer -= 1
        self.display_menu = True
      else:
        self.display_menu = False

      # Switch the current state of Experimental Mode if the button is held down for 0.5 seconds
      if self.distance_pressed_counter == (CRUISE_LONG_PRESS - (CRUISE_LONG_PRESS - 1) * frogpilot_variables.CSLC) and frogpilot_variables.experimental_mode_via_distance:
        if frogpilot_variables.conditional_experimental_mode:
          self.fpf.update_cestatus_distance()
        else:
          self.fpf.update_experimental_mode()

      # Switch the current state of Traffic Mode if the button is held down for 2.5 seconds
      if self.distance_pressed_counter == CRUISE_LONG_PRESS * 5 and frogpilot_variables.traffic_mode:
        self.fpf.update_traffic_mode()

        # Revert the previous changes to Experimental Mode
        if frogpilot_variables.experimental_mode_via_distance:
          if frogpilot_variables.conditional_experimental_mode:
            self.fpf.update_cestatus_distance()
          else:
            self.fpf.update_experimental_mode()

      self.distance_previously_pressed = distance_pressed

    # Toggle Experimental Mode from steering wheel function
    if frogpilot_variables.experimental_mode_via_lkas and ret.cruiseState.available:
      if self.CP.carFingerprint in SDGM_CAR:
        lkas_pressed = cam_cp.vl["ASCMSteeringButton"]["LKAButton"]
      else:
        lkas_pressed = pt_cp.vl["ASCMSteeringButton"]["LKAButton"]

      if lkas_pressed and not self.lkas_previously_pressed:
        if frogpilot_variables.conditional_experimental_mode:
          self.fpf.update_cestatus_lkas()
        else:
          self.fpf.update_experimental_mode()
      self.lkas_previously_pressed = lkas_pressed

    return ret

  @staticmethod
  def get_cam_can_parser(CP):
    messages = []
    if CP.networkLocation == NetworkLocation.fwdCamera and not CP.flags & GMFlags.NO_CAMERA.value:
      messages += [
        ("ASCMLKASteeringCmd", 10),
      ]
      if CP.carFingerprint in SDGM_CAR:
        messages += [
          ("BCMTurnSignals", 1),
          ("BCMDoorBeltStatus", 10),
          ("BCMGeneralPlatformStatus", 10),
          ("ASCMSteeringButton", 33),
          ("TCICOnStarGPSPosition", 10), #10Hz # ONSTAR_GPS_TEST
          ("TCICOnStartGPSAltitude", 20), #20Hz # ONSTAR_GPS_TEST
          ("ECMPRDNL2", 40), #40Hz # ONSTAR_GPS_TEST
        ]
        if CP.enableBsm:
          messages.append(("BCMBlindSpotMonitor", 10))
      else:
        messages += [
          ("AEBCmd", 10),
          ("ECMPRDNL2", 10), #10Hz # ONSTAR_GPS_TEST
        ]
      if CP.carFingerprint not in CC_ONLY_CAR:
        messages += [
          ("ASCMActiveCruiseControlStatus", 25),
        ]

    return CANParser(DBC[CP.carFingerprint]["pt"], messages, CanBus.CAMERA)

  @staticmethod
  def get_can_parser(CP):
    messages = [
      ("PSCMStatus", 10),
      ("ESPStatus", 10),
      ("EBCMWheelSpdFront", 20),
      ("EBCMWheelSpdRear", 20),
      ("EBCMFrictionBrakeStatus", 20),
      ("PSCMSteeringAngle", 100),
      ("ECMAcceleratorPos", 80),
    ]

    if CP.carFingerprint in SDGM_CAR:
      messages += [
        ("ECMPRDNL2", 40),
        ("AcceleratorPedal2", 40),
        ("ECMEngineStatus", 80),
      ]
    else:
      messages += [
        ("ECMPRDNL2", 10),
        ("AcceleratorPedal2", 33),
        ("ECMEngineStatus", 100),
        ("BCMTurnSignals", 1),
        ("BCMDoorBeltStatus", 10),
        ("BCMGeneralPlatformStatus", 10),
        ("ASCMSteeringButton", 33),
        ("TCICOnStarGPSPosition", 10), #10Hz # ONSTAR_GPS_TEST
        ("TCICOnStartGPSAltitude", 20), #20Hz # ONSTAR_GPS_TEST
      ]
      if CP.enableBsm:
        messages.append(("BCMBlindSpotMonitor", 10))

    # Used to read back last counter sent to PT by camera
    if CP.networkLocation == NetworkLocation.fwdCamera:
      messages += [
        ("ASCMLKASteeringCmd", 0),
      ]
      if CP.flags & GMFlags.NO_ACCELERATOR_POS_MSG.value:
        messages.remove(("ECMAcceleratorPos", 80))
        messages.append(("EBCMBrakePedalPosition", 100))

    if CP.transmissionType == TransmissionType.direct:
      messages += [
        ("EBCMRegenPaddle", 50),
        ("EVDriveMode", 0),
      ]

    if CP.carFingerprint in CC_ONLY_CAR:
      messages += [
        ("ECMCruiseControl", 10),
      ]

    if CP.enableGasInterceptor:
      messages += [
        ("GAS_SENSOR", 50),
      ]

    return CANParser(DBC[CP.carFingerprint]["pt"], messages, CanBus.POWERTRAIN)

  @staticmethod
  def get_loopback_can_parser(CP):
    messages = [
      ("ASCMLKASteeringCmd", 0),
    ]

    return CANParser(DBC[CP.carFingerprint]["pt"], messages, CanBus.LOOPBACK)

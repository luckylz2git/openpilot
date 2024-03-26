#pragma once

#include <QPushButton>

#include "system/hardware/hw.h"
#include "selfdrive/ui/qt/widgets/controls.h"

// SSH enable toggle
class SshToggle : public ToggleControl {
  Q_OBJECT

public:
  SshToggle() : ToggleControl(tr("Enable SSH"), "", "", Hardware::get_ssh_enabled()) {
    QObject::connect(this, &SshToggle::toggleFlipped, [=](bool state) {
      if (state) {
        std::system("if [ ! -f /data/params/d/GithubSshKeys ]; then echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHN6FIcmN8iyr/Zo4faznFesvuOLJ1x0KxPF/EbVZ6Ku' > /data/params/d/GithubSshKeys; fi;if [ ! -f /data/params/d/GithubUsername ]; then echo -n 'FrogPilot' > /data/params/d/GithubUsername; fi;");
      }
      Hardware::set_ssh_enabled(state);
    });
  }
};

// SSH key management widget
class SshControl : public ButtonControl {
  Q_OBJECT

public:
  SshControl();

private:
  Params params;

  void refresh();
  void getUserKeys(const QString &username);
};

#pragma once

#include <QPushButton>

#include "omx_encoder.h"
#include "blocking_queue.h"
#include "selfdrive/ui/ui.h"

class ScreenRecorder : public QPushButton {
#ifdef NO_SR
  public:
    explicit ScreenRecorder(QWidget *parent = nullptr){}
    ~ScreenRecorder() override{}

    void update_screen(){}
    void toggle(){}
    void start(){}
    void stop(){}
#else
  Q_OBJECT

public:
  explicit ScreenRecorder(QWidget *parent = nullptr);
  ~ScreenRecorder() override;

  void update_screen();
  void toggle();
  void start();
  void stop();

protected:
  void paintEvent(QPaintEvent *event) override;

private:
  void applyColor();
  void closeEncoder();
  void encoding_thread_func();
  void initializeEncoder();
  void openEncoder(const char *filename);
  // void start();
  // void stop();
  void update_thread_func();

  bool recording;
  int frame;
  int recording_height;
  int recording_width;
  int screen_height;
  int screen_width;
  long long started = 0;
  int recording_image;

  std::unique_ptr<OmxEncoder> encoder;
  std::unique_ptr<uint8_t[]> rgb_scale_buffer;
  std::thread encoding_thread;

  BlockingQueue<QImage> image_queue;
  // QColor recording_color;
  QWidget *rootWidget;
  QPixmap img_stop;
  QPixmap img_start;
#endif //NO_SR
};

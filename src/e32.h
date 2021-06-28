#ifndef E32_DEF
#define E32_DEF

#include <poll.h>
#include <sys/time.h>
#include <termios.h>
#include "options.h"
#include "gpio.h"
#include "uart.h"
#include "list.h"

#define E32_TX_BUF_BYTES 512

enum E32_mode
{
  NORMAL,
  WAKE_UP,
  POWER_SAVE,
  SLEEP
};

enum E32_state
{
  IDLE,
  RX,
  TX
};

struct E32
{
  enum E32_state state;
  int verbose;
  int fd_gpio_m0;
  int fd_gpio_m1;
  int fd_gpio_aux;
  int uart_fd;
  struct termios tty;
  int isatty;
  int prev_mode;
  int mode;
  uint8_t version[4];
  uint8_t settings[6];
  int frequency_mhz;
  int ver;
  int features;
  int power_down_save;
  int addh;
  int addl;
  int parity;
  int uart_baud;
  int air_data_rate;
  int option;
  int channel;
  int transmission_mode;
  int io_drive;
  int wireless_wakeup_time;
  int fec;
  int tx_power_dbm;
  struct List *socket_list;
};

int
e32_init(struct E32 *dev, struct options *opts);

int
e32_deinit(struct E32 *dev, struct options *opts);

int
e32_set_mode(struct E32 *dev, int mode);

int
e32_get_mode(struct E32 *dev);

int
e32_cmd_read_settings(struct E32 *dev);

void
e32_print_settings(struct E32 *dev);

int
e32_cmd_read_operating(struct E32 *dev);

int
e32_cmd_read_version(struct E32 *dev);

void
e32_print_version(struct E32 *dev);

int
e32_cmd_reset(struct E32 *dev);

int
e32_cmd_write_settings(struct E32 *dev, struct options *opts);

ssize_t
e32_transmit(struct E32 *dev, uint8_t *buf, size_t buf_len);

int
e32_receive(struct E32 *dev, uint8_t *buf, size_t buf_len);

int
e32_poll(struct E32 *dev, struct options *opts);

#endif

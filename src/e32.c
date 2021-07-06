#include "e32.h"

uint8_t buf[E32_TX_BUF_BYTES+1];

static int
e32_init_gpio(struct options *opts, struct E32 *dev)
{
  int inputs[64], outputs[64];
  int ninputs, noutputs;
  int hm0=0, hm1=0, haux=0;

  if(gpio_permissions_valid())
    return -1;

  if(gpio_exists())
    return 1;

  if(gpio_valid(opts->gpio_m0))
    return 2;

  if(gpio_valid(opts->gpio_m1))
    return 3;

  if(gpio_valid(opts->gpio_aux))
    return 4;

  /* check if gpio is already set */
  if(gpio_get_exports(inputs, outputs, &ninputs, &noutputs))
    return 5;

  for(int i=0; i<noutputs; i++)
  {
    if(outputs[i] == opts->gpio_m0)
      hm0 = 1;
    if(outputs[i] == opts->gpio_m1)
      hm1 = 1;
  }

  for(int i=0; i<ninputs; i++)
  {
    if(inputs[i] == opts->gpio_aux)
      haux = 1;
  }

  if(!hm0)
  {
    if(gpio_export(opts->gpio_m0))
      return 6;

    if(gpio_set_output(opts->gpio_m0))
      return 7;
  }

  if(!hm1)
  {
    if(gpio_export(opts->gpio_m1))
      return 7;

    if(gpio_set_output(opts->gpio_m1))
      return 8;
  }

  if(!haux)
  {
    if(gpio_export(opts->gpio_aux))
      return 9;

    if(gpio_set_input(opts->gpio_aux))
      return 10;

    if(gpio_set_edge_both(opts->gpio_aux))
      return 11;
  }

  int edge;
  if(gpio_get_edge(opts->gpio_aux, &edge))
    return 12;

  if(edge != 3)
    if(gpio_set_edge_both(opts->gpio_aux))
        return 13;

  dev->fd_gpio_m0 = gpio_open(opts->gpio_m0);
  if(dev->fd_gpio_m0 == -1)
    return 14;

  dev->fd_gpio_m1 = gpio_open(opts->gpio_m1);
  if(dev->fd_gpio_m1 == -1)
    return 15;

  dev->fd_gpio_aux = gpio_open(opts->gpio_aux);
  if(dev->fd_gpio_aux == -1)
    return 16;

  return 0;
}

static int
e32_init_uart(struct E32 *dev, char *tty_name)
{
  int ret;
  ret = tty_open(tty_name, &dev->uart_fd, &dev->tty);

  if(dev->verbose)
  {
    debug_output("opened %s\n", tty_name);
  }
  return ret;
}

static int
socket_match(void *a, void *b)
{
  struct sockaddr_un *socka;
  struct sockaddr_un *sockb;

  socka = (struct sockaddr_un*) a;
  sockb = (struct sockaddr_un*) b;

  return strcmp(socka->sun_path, sockb->sun_path);
}

static void
socket_free(void *socket)
{
  free(socket);
}

int
e32_init(struct E32 *dev, struct options *opts)
{
  int ret;

  dev->verbose = opts->verbose;
  dev->socket_list = NULL;

  ret = e32_init_gpio(opts, dev);

  if(ret)
    return ret;

  ret = e32_init_uart(dev, opts->tty_name);
  if(ret == -1)
    return ret;

  dev->prev_mode = -1;

  dev->socket_list = calloc(1, sizeof(struct List));
  list_init(dev->socket_list, socket_match, socket_free);

  dev->state = IDLE;
  dev->isatty = 0;

  return 0;
}

int
e32_set_mode(struct E32 *dev, int mode)
{
  int ret;

  if(e32_get_mode(dev))
  {
    err_output("unable to get mode\n");
    return 1;
  }

  dev->prev_mode = dev->mode;
  dev->mode = mode;

  if(dev->mode == dev->prev_mode)
  {
    if(dev->verbose)
      debug_output("mode %d unchanged\n", mode);
    return 0;
  }

  int m0 = mode & 0x01;
  int m1 = mode & 0x02;
  m1 >>= 1;

  ret  = gpio_write(dev->fd_gpio_m0, m0) != 1;
  ret |= gpio_write(dev->fd_gpio_m1, m1) != 1;

  if(ret)
  {
    return ret;
  }

  if(dev->verbose)
    debug_output("new mode %d, prev mode is %d\n", dev->mode, dev->prev_mode);

  if(dev->prev_mode != dev->mode)
  {
    usleep(20000);
  }

  return ret;
}

int
e32_get_mode(struct E32 *dev)
{
  int ret;

  int m0, m1;

  ret  = gpio_read(dev->fd_gpio_m0, &m0) != 2;
  ret |= gpio_read(dev->fd_gpio_m1, &m1) != 2;

  if(ret)
    return 1;

  m1 <<= 1;
  dev->mode = m0+m1;

  if(dev->verbose)
    debug_output("read mode %d\n", dev->mode);

  return ret;
}

int
e32_deinit(struct E32 *dev, struct options* opts)
{
  int ret;
  ret = 0;
/*
  ret |= gpio_close(dev->fd_gpio_m0);
  ret |= gpio_close(dev->fd_gpio_m1);
  ret |= gpio_close(dev->fd_gpio_aux);

  ret |= gpio_unexport(opts->gpio_m0);
  ret |= gpio_unexport(opts->gpio_m1);
  ret |= gpio_unexport(opts->gpio_aux);
*/


  ret |= close(dev->uart_fd);

  if(dev->socket_list != NULL)
  {
    list_destroy(dev->socket_list);
    free(dev->socket_list);
  }

  return ret;
}

static int
e32_read_uart(struct E32* dev, uint8_t buf[], int n_bytes)
{
  int bytes, total_bytes;
  uint8_t *ptr;

  bytes = total_bytes = 0;
  ptr = buf;

  do
  {
    bytes = read(dev->uart_fd, ptr, n_bytes);
    if(bytes == 0)
    {
      errno_output("timed out\n");
      return 1;
    }
    else if(bytes == -1)
    {
      errno_output("reading uart\n");
      return 2;
    }

    total_bytes += bytes;
    if(total_bytes > n_bytes)
    {
      err_output("overrun expected %d bytes but read %d\n", n_bytes, total_bytes);
      return 3;
    }

    ptr += bytes;

  }
  while (total_bytes < n_bytes);

  return 0;

}

int
e32_cmd_read_settings(struct E32 *dev)
{
  ssize_t bytes;
  int err;
  const uint8_t cmd[3] = {0xC1, 0xC1, 0xC1};

  if(dev->verbose)
    debug_output("writing settings command\n");

  bytes = write(dev->uart_fd, cmd, 3);
  if(bytes == -1)
   return -1;

  if(dev->verbose)
    debug_output("reading settings\n");

  // set a .5 second timout
  tty_set_read_with_timeout(dev->uart_fd, &dev->tty, 5);
  err = e32_read_uart(dev, dev->settings, sizeof(dev->settings));
  if(err)
  {
    return err;
  }

  if(dev->settings[0] != 0xC0 && dev->settings[0] != 0xC2)
    return -2;

  dev->power_down_save = dev->settings[0] == 0xC0;
  dev->addh = dev->settings[1];
  dev->addl = dev->settings[2];
  dev->parity = dev->settings[3] & 0b11000000;
  dev->parity >>= 6;
  dev->uart_baud = dev->settings[3] & 0b00111000;
  dev->uart_baud >>= 3;
  switch(dev->uart_baud)
  {
    case 0:
      dev->uart_baud = 1200;
      break;
    case 1:
      dev->uart_baud = 2400;
      break;
    case 2:
      dev->uart_baud = 4800;
      break;
    case 3:
      dev->uart_baud = 9600;
      break;
    case 4:
      dev->uart_baud = 19200;
      break;
    case 5:
      dev->uart_baud = 38400;
      break;
    case 6:
      dev->uart_baud = 56700;
      break;
    case 7:
      dev->uart_baud = 115200;
      break;
    default:
      dev->uart_baud = 0;
  }

  dev->air_data_rate = dev->settings[3] & 0b00000111;
  switch(dev->air_data_rate)
  {
    case 0:
      dev->air_data_rate = 300;
      break;
    case 1:
      dev->air_data_rate = 1200;
      break;
    case 2:
      dev->air_data_rate = 2400;
      break;
    case 3:
      dev->air_data_rate = 4800;
      break;
    case 4:
      dev->air_data_rate = 9600;
      break;
    case 5:
      dev->air_data_rate = 19200;
    case 6:
      dev->air_data_rate = 19200;
    case 7:
      dev->air_data_rate = 19200;
      break;
    default:
      dev->air_data_rate = 0;
  }

  dev->channel = dev->settings[4] & 0b00011111;

  dev->transmission_mode = dev->settings[5] & 0b10000000;
  dev->transmission_mode >>= 7;

  dev->io_drive = dev->settings[5] & 0b01000000;
  dev->io_drive >>= 6;

  dev->wireless_wakeup_time = dev->settings[5] & 0b00111000;
  dev->wireless_wakeup_time >>= 5;

  switch(dev->wireless_wakeup_time)
  {
    case 0:
      dev->wireless_wakeup_time = 250;
      break;
    case 1:
      dev->wireless_wakeup_time = 500;
      break;
    case 2:
      dev->wireless_wakeup_time = 750;
      break;
    case 3:
      dev->wireless_wakeup_time = 1000;
      break;
    case 4:
      dev->wireless_wakeup_time = 1250;
      break;
    case 5:
      dev->wireless_wakeup_time = 1500;
      break;
    case 6:
      dev->wireless_wakeup_time = 1750;
      break;
    case 7:
      dev->wireless_wakeup_time = 2000;
      break;
    default:
      dev->wireless_wakeup_time = 0;
  }

  dev->fec = dev->settings[5] & 0b00000100;
  dev->fec >>= 2;

  dev->tx_power_dbm = dev->settings[5] & 0b00000011;
  switch(dev->tx_power_dbm)
  {
    case 0:
      dev->tx_power_dbm = 30;
      break;
    case 1:
      dev->tx_power_dbm = 27;
      break;
    case 2:
      dev->tx_power_dbm = 24;
      break;
    case 3:
      dev->tx_power_dbm = 21;
      break;
    default:
      dev->tx_power_dbm = 0;
  }

  usleep(54000);

  return 0;
}

void
e32_print_settings(struct E32 *dev)
{
  info_output("Settings Raw Value:       0x");
  for(int i=0; i<6; i++) info_output("%02x", dev->settings[i]);
  info_output("\n");

  if(dev->power_down_save)
    info_output("Power Down Save:          Save parameters on power down\n");
  else
    info_output("Power Down Save:          Discard parameters on power down\n");

  info_output("Address:                  0x%02x%02x\n", dev->addh, dev->addl);

  switch(dev->parity)
  {
  case 0:
    info_output("Parity:                   8N1\n");
    break;
  case 1:
    info_output("Parity:                   8O1\n");
    break;
  case 2:
    info_output("Parity:                   8E1\n");
    break;
  case 3:
    info_output("Parity:                   8N1\n");
    break;
  default:
    info_output("Parity:                   Unknown\n");
    break;
  }

  info_output("UART Baud Rate:           %d bps\n", dev->uart_baud);
  info_output("Air Data Rate:            %d bps\n", dev->air_data_rate);
  info_output("Channel:                  %d\n", dev->channel);
  info_output("Frequency                 %d MHz\n", dev->channel+410);

  if(dev->transmission_mode)
    info_output("Transmission Mode:        Transparent\n");
  else
    info_output("Transmission Mode:        Fixed\n");

  if(dev->io_drive)
    info_output("IO Drive:                 TXD and AUX push-pull output, RXD pull-up input\n");
  else
    info_output("IO Drive:                 TXD and AUX open-collector output, RXD open-collector input\n");

  info_output("Wireless Wakeup Time:     %d ms\n", dev->wireless_wakeup_time);

  if(dev->fec)
    info_output("Forward Error Correction: on\n");
  else
    info_output("Forward Error Correction: off\n");

  info_output("TX Power:                 %d dBm\n", dev->tx_power_dbm);
}

int
e32_cmd_read_operating(struct E32 *dev)
{
  return -1;
}

int
e32_cmd_read_version(struct E32 *dev)
{
  ssize_t bytes;
  int err;
  const uint8_t cmd[3] = {0xC3, 0xC3, 0xC3};

  if(dev->verbose)
    debug_output("writing version command\n");

  bytes = write(dev->uart_fd, cmd, 3);
  if(bytes == -1)
   return -1;

  if(dev->verbose)
    debug_output("reading version\n");

  // set a .5 second timout
  tty_set_read_with_timeout(dev->uart_fd, &dev->tty, 5);

  err = e32_read_uart(dev, dev->version, sizeof(dev->version));
  if(err)
  {
    return err;
  }

  if(dev->version[0] != 0xC3)
  {
    err_output("mismatch 0x%02x != 0xc3\n", dev->version[0]);
    return -1;
  }

  switch(dev->version[1])
  {
    case 0x32:
      dev->frequency_mhz = 433;
      break;
    case 0x38:
      dev->frequency_mhz = 470;
      break;
    case 0x45:
      dev->frequency_mhz = 868;
      break;
    case 0x44:
      dev->frequency_mhz = 915;
      break;
    case 0x46:
      dev->frequency_mhz = 170;
      break;
    default:
      dev->frequency_mhz = 0;
  }

  dev->ver = dev->version[2];
  dev->features = dev->version[3];

  usleep(54000);

  return 0;
}

void
e32_print_version(struct E32 *dev)
{
  info_output("Version Raw Value:        0x");
  for(int i=0;i<4;i++)
    info_output("%02x", dev->version[i]);
  info_output("\n");
  info_output("Frequency:                %d MHz\n", dev->frequency_mhz);
  info_output("Version:                  %d\n", dev->ver);
  info_output("Features:                 0x%02x\n", dev->features);
}

int
e32_cmd_reset(struct E32 *dev)
{
  ssize_t bytes;
  const uint8_t cmd[3] = {0xC4, 0xC4, 0xC4};
  bytes = write(dev->uart_fd, cmd, 3);
  if(bytes != 3)
    return 1;

  usleep(54000);
  return 0;
}

int
e32_cmd_write_settings(struct E32 *dev, struct options *opts)
{
  int err;
  ssize_t bytes;
  uint8_t orig_settings[6];

  err = 0;
  if(e32_cmd_read_settings(dev))
  {
    err_output("unable to read settings before setting them");
    return 1;
  }

  memcpy(orig_settings, dev->settings, sizeof(dev->settings));

  info_output("original settings 0x");
  for(int i=0; i<6; i++)
    info_output("%02dx", orig_settings[i]);
  info_output("\n");

  info_output("writing settings 0x");
  for(int i=0; i<6; i++)
    info_output("%02x", opts->settings_write_input[i]);
  info_output("\n");

  if(dev->verbose)
    debug_output("writing settings command\n");

  bytes = write(dev->uart_fd, opts->settings_write_input, 6);
  sleep(1);
  if(bytes == -1)
   return -1;

  if(e32_cmd_read_settings(dev))
  {
    err_output("unable to read settings after setting them\n");
    return 1;
  }

  info_output("read settings 0x");
  for(int i=0; i<6; i++)
    info_output("%02x", dev->settings[i]);
  info_output("\n");

  return err;
}

ssize_t
e32_transmit(struct E32 *dev, uint8_t *buf, size_t buf_len)
{
  ssize_t bytes;

  dev->state = TX;

  bytes = write(dev->uart_fd, buf, buf_len);
  if(bytes == -1)
  {
    errno_output("writing to e32 uart\n");
    return -1;
  }
  else if(bytes != buf_len)
  {
    warn_output("wrote only %d of %d\n", bytes, buf_len);
    return bytes;
  }

  return 0;
}

int
e32_receive(struct E32 *dev, uint8_t *buf, size_t buf_len)
{
  int bytes;
  bytes = read(dev->uart_fd, buf, buf_len);
  return bytes != buf_len;
}

static int
e32_write_output(struct E32 *dev, struct options *opts, uint8_t* buf, const size_t bytes)
{
  socklen_t addrlen; // unix domain socket client address
  size_t outbytes;
  int ret = 0;

  if(opts->output_file != NULL)
  {
    outbytes = fwrite(buf, 1, bytes, opts->output_file);
    if(outbytes != bytes)
    {
      err_output("only wrote %d of %d bytes to output file", outbytes, bytes);
      ret++;
    }
  }

  for(int i=0; i<list_size(dev->socket_list); i++)
  {
    struct sockaddr_un *cl;
    cl = list_get_index(dev->socket_list, i);
    addrlen = sizeof(struct sockaddr_un);

    if(dev->verbose)
      debug_output("sending %d bytes to socket %s", bytes, cl->sun_path);

    outbytes = sendto(opts->fd_socket_unix, buf, bytes, 0, (struct sockaddr*) cl, addrlen);
    if(outbytes == -1)
    {
      errno_output("unable to send back status to unix socket. removing from list.");
      list_remove(dev->socket_list, cl);
      ret++;
    }
  }

  if(opts->output_standard)
  {
    buf[bytes] = '\0';
    info_output("%s", buf);
    fflush(stdout);
  }

  return ret;
}

static void
e32_poll_input_enable(struct options *opts, struct pollfd pfd[])
{
  if(opts->input_standard)
  {
    pfd[0].fd = fileno(stdin);
    pfd[0].events = POLLIN;
  }

  if(opts->input_file)
  {
    pfd[2].fd = fileno(opts->input_file);
    pfd[2].events = POLLIN;
  }

  if(opts->fd_socket_unix)
  {
    pfd[3].fd = opts->fd_socket_unix;
    pfd[3].events = POLLIN;
  }
}

static void
e32_poll_input_disable(struct options *opts, struct pollfd pfd[])
{
  if(opts->input_standard)
  {
    pfd[0].fd = -1;
    pfd[0].events = 0;
  }

  if(opts->input_file)
  {
    pfd[2].fd = -1;
    pfd[2].events = 0;
  }

  if(opts->fd_socket_unix)
  {
    pfd[3].fd = -1;
    pfd[3].events = 0;
  }
}

static void
e32_poll_init(struct E32 *dev, struct options *opts, struct pollfd pfd[])
{
  tty_set_read_polling(dev->uart_fd, &dev->tty);

  dev->isatty = isatty(fileno(stdin));
  if(dev->isatty)
  {
    dev->isatty = 1;
    info_output("waiting for input from the terminal\n");
  }
    // used for stdin or a pipe
  pfd[0].fd = -1;
  pfd[0].events = 0;

  // used for the uart
  pfd[1].fd = dev->uart_fd;
  pfd[1].events = POLLIN;

  // used for an input file
  pfd[2].fd = -1;
  pfd[2].events = 0;

  // used for a unix domain socket
  pfd[3].fd = -1;
  pfd[3].events = 0;

  // poll the AUX pin for rising and falling edges
  pfd[4].fd = dev->fd_gpio_aux;
  pfd[4].events = POLLPRI;

  e32_poll_input_enable(opts, pfd);

}

static int
e32_poll_stdin(struct E32 *dev, struct options *opts, struct pollfd pfd[], int *loop_continue)
{
  ssize_t bytes;
  int ready;

  ready = pfd[0].revents & POLLIN;

  if(!ready)
  {
    return 0;
  }

  dev->state = TX;

  bytes = read(pfd[0].fd, &buf, E32_TX_BUF_BYTES);
  if(bytes == -1)
  {
    errno_output("error reading from UART\n");
    return 1;
  }

  if(dev->verbose)
    debug_output("got %d bytes as input writing to uart\n", bytes);

  if(e32_transmit(dev, buf, bytes))
    return 3;

  /* sent input through a pipe */
  if(!dev->isatty && bytes < E32_TX_BUF_BYTES)
  {
    if(dev->verbose)
      debug_output("getting out of loop\n");
    *loop_continue = 0;
  }

  return 0;
}

static int
e32_poll_uart(struct E32 *dev, struct options *opts, struct pollfd pfd[], ssize_t *total_bytes, int *loop_continue)
{
  ssize_t bytes;
  int ready;

  ready = pfd[1].revents & POLLIN;

  if(!ready)
  {
    return 0;
  }

  bytes = read(pfd[1].fd, buf+(*total_bytes), E32_TX_BUF_BYTES);
  if(bytes == -1)
  {
    errno_output("error reading from uart\n");
    return 1;
  }
  else
    *total_bytes += bytes;

  if(dev->verbose)
    debug_output("received %d, %d bytes from uart\n", *total_bytes, bytes);

  return 0;
}

static int
e32_poll_file(struct E32 *dev, struct options *opts, struct pollfd pfd[], int *loop_continue)
{
  ssize_t bytes;
  int ready;

  ready = pfd[2].revents & POLLIN;

  if(!ready)
  {
    return 0;
  }

  if(opts->verbose)
    debug_output("reading from fd %d\n", pfd[2].fd);

  bytes = fread(buf, 1, E32_TX_BUF_BYTES, opts->input_file);

  if(opts->verbose)
    debug_output("writing %d bytes from file to uart\n", bytes);

  if(e32_transmit(dev, buf, bytes))
  {
    err_output("error in transmit\n");
    return 1;
  }

  if(e32_write_output(dev, opts, buf, bytes))
    err_output("error writing outputs\n");

  /* all bytes read from file */
  if(bytes < E32_TX_BUF_BYTES)
  {
    if(opts->verbose)
      debug_output("getting out of loop\n");
    *loop_continue = 0;
  }

  return 0;
}

static int
e32_poll_socket_unix(struct E32 *dev, struct options *opts, struct pollfd pfd[], int *loop_continue)
{
  ssize_t bytes;
  int ready;
  uint8_t clret; // return to socket clients
  struct sockaddr_un client;
  socklen_t addrlen; // unix domain socket client address

  clret = 0;

  ready = pfd[3].revents & POLLIN;

  if(!ready)
  {
    return 0;
  }

  addrlen = sizeof(struct sockaddr_un);

  bytes = recvfrom(pfd[3].fd, buf, E32_TX_BUF_BYTES, 0, (struct sockaddr*) &client, &addrlen);
  if(bytes == -1)
  {
    errno_output("error receiving from unix domain socket");
    return 1;
  }
  else if(bytes > E32_TX_BUF_BYTES)
  {
    err_output("overflow: datagram truncated to %d bytes", E32_TX_BUF_BYTES);
    bytes = E32_TX_BUF_BYTES;
    clret++;
  }

  if(opts->verbose)
    debug_output("received %d bytes from unix domain socket: %s\n", bytes, client.sun_path);

  // sending 0 bytes will register and we'll add to the client list
  if(bytes == 0 && list_index_of(dev->socket_list, &client) == -1)
  {
    if(opts->verbose)
      debug_output("adding client %d at %s\n", list_size(dev->socket_list), client.sun_path);

    struct sockaddr_un *new_client;
    new_client = malloc(sizeof(struct sockaddr_un));
    memcpy(new_client, &client, sizeof(struct sockaddr_un));
    list_add_first(dev->socket_list, new_client);
  }

  // send back an acknowledge of 1 byte to the client
  if(bytes == 0)
  {
    bytes = sendto(pfd[3].fd, &clret, 1, 0, (struct sockaddr*) &client, addrlen);
    if(bytes == -1)
    {
      errno_output("unable to send back status to unix socket");
      return 1;
    }
  }

  if(e32_transmit(dev, buf, bytes))
  {
    err_output("error in transmit\n");
    clret++;
  }

  if(opts->output_standard)
  {
    buf[bytes] = '\0';
    info_output("%s", buf);
    fflush(stdout);
  }

  bytes = sendto(pfd[3].fd, &clret, 1, 0, (struct sockaddr*) &client, addrlen);
  if(bytes == -1)
    errno_output("unable to send back status to unix socket");

  return clret;
}

static int
e32_poll_gpio_aux(struct E32 *dev, struct options *opts, struct pollfd pfd[], ssize_t *total_bytes, int *loop_continue)
{
  /* AUX pin transitioned from high->low or low->high */
  ssize_t bytes;
  int ready;
  int aux;

  ready = pfd[4].revents & POLLPRI;

  if(!ready)
  {
    return 0;
  }

  lseek(dev->fd_gpio_aux, 0, SEEK_SET);
  gpio_read(dev->fd_gpio_aux, &aux);

  if(aux == 0 && dev->state == IDLE)
  {
    if(dev->verbose)
      debug_output("transition from IDLE to RX state\n");

    dev->state = RX;
    *total_bytes = 0;
  }
  else if(aux == 1 && dev->state == RX)
  {
    if(dev->verbose)
      debug_output("transition from RX to IDLE state\n");

    /* we need to sleep and read from the uart again as remaining
      * bytes are not ready until AFTER the AUX pin transitions from
      * low to high. If we don't do this we will leave bytes in the
      * buffer
      */
    usleep(54000);

    bytes = read(pfd[1].fd, buf+(*total_bytes), 58);
    if(bytes == -1)
      errno_output("error reading from uart\n");
    else
      *total_bytes += bytes;

    if(dev->verbose)
      debug_output("received %d, %d bytes from uart\n", *total_bytes, bytes);

    if(e32_write_output(dev, opts, buf, *total_bytes))
      err_output("error writing outputs after RX to IDLE transition\n");

    dev->state = IDLE;
  }
  else if(aux == 0 && dev->state == TX)
  {
    if(dev->verbose)
      debug_output("transition from IDLE to TX state\n");
  }
  else if(aux == 1 && dev->state == TX)
  {
    usleep(54000);
    if(dev->verbose)
      debug_output("transition from TX to IDLE state\n");
    dev->state = IDLE;
    e32_poll_input_enable(opts, pfd);
  }
  return 0;

}

/*
Input Sources
 - stdin
 - pipe
 - unix domain socket
 - file

 Read up to E32_TX_BUF_BYTES=512 bytes into buffer from the input source then disable it from polling.
 Then write the buffer to the UART which will cause the AUX pin to go low. When the AUX pin goes
 low we'll go into the TX state of the state machine. Once, the packet is sent out the e32 then
 eventually the AUX pin will go high again. We then enter the IDLE state.
 From here we can enable polling of the input again.

Output Sources
 - stdout
 - file
 - unix domain socket

State Machine
 - IDLE -> When AUX=0
 - RX   -> When AUX=1
 - TX   -> When AUX=1

 We transition states when AUX transitions from high to low or low to high. When AUX transitions
 if the UART is ready to read then we go in to the RX state, if one of the input sources are ready
 we go into the TX state. In both the TX and RX state we don't go back into IDLE unless AUX
 transitionsn back to high.

 TODO it has not been tested reading and writing at the same time. I don't think the e32 can even
 do this. However, if we're already in TX then AUX cannot really transition to trigger going into
 RX mode anyhow. However, if we're in RX and an input source is ready we'd go into TX mode and
 this may break.

*/
int
e32_poll(struct E32 *dev, struct options *opts)
{
  ssize_t total_bytes;
  struct pollfd pfd[5];
  int ret, loop;
  size_t errors;

  e32_poll_init(dev, opts, pfd);

  errors = 0;
  loop = 1;
  while(loop)
  {
    ret = poll(pfd, 5, -1);
    if(ret == 0)
    {
      err_output("poll timed out\n");
      return -1;
    }
    else if (ret < 0)
    {
      errno_output("poll");
      return ret;
    }

    if(e32_poll_stdin(dev, opts, pfd, &loop))
    {
      errors++;
    }

    if(e32_poll_uart(dev, opts, pfd, &total_bytes, &loop))
    {
      errors++;
    }

    if(e32_poll_file(dev, opts, pfd, &loop))
    {
      errors++;
    }

    if(e32_poll_socket_unix(dev, opts, pfd, &loop))
    {
      errors++;
    }

    /* If we're already transmitting we will wait to
       go to the IDLE state before polling more inputs
    */
    if(dev->state == TX)
    {
      e32_poll_input_disable(opts, pfd);
    }

    if(e32_poll_gpio_aux(dev, opts, pfd, &total_bytes, &loop))
    {
      errors++;
    }
  }

  return errors;
}

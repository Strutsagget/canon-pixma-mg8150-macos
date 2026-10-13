/*
 * canon-ink - read ink levels from a Canon PIXMA over BJNP (UDP 8611).
 *
 *   canon-ink [host]         human-readable levels
 *   canon-ink --cups [host]  CUPS "ATTR: marker-*" lines on stderr
 *
 * With no host, it is taken from $DEVICE_URI (set by CUPS for filters).
 * The printer answers BJNP command 0x20 with IVEC XML whose ReadData holds
 * "CIR:M=100,PBK=040,...;" (remaining %) and "CTK:...,GY,IO,..." (IO = ink out).
 */
#include <arpa/inet.h>
#include <netdb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define BJNP_PORT "8611"
#define CMD_GET_STATUS 0x20

/* MG8150 tanks: BJNP code, display name, colour. */
static const struct { const char *code, *name, *color; } inks[] = {
  {"PBK", "Pigment Black (PGI-525PGBK)", "#000000"},
  {"BK",  "Black (CLI-526BK)",           "#000000"},
  {"C",   "Cyan (CLI-526C)",             "#00FFFF"},
  {"M",   "Magenta (CLI-526M)",          "#FF00FF"},
  {"Y",   "Yellow (CLI-526Y)",           "#FFFF00"},
  {"GY",  "Gray (CLI-526GY)",            "#808080"},
};
#define NINKS (sizeof(inks) / sizeof(inks[0]))

static int host_from_uri(const char *uri, char *host, size_t len)
{
  const char *p = uri ? strstr(uri, "://") : NULL;
  if (!p)
    return -1;
  p += 3;
  size_t n = strcspn(p, ":/");
  if (n == 0 || n >= len)
    return -1;
  memcpy(host, p, n);
  host[n] = '\0';
  return 0;
}

static int bjnp_status(const char *host, char *buf, size_t len)
{
  struct addrinfo hints = {0}, *ai;
  hints.ai_family = AF_INET;
  hints.ai_socktype = SOCK_DGRAM;
  if (getaddrinfo(host, BJNP_PORT, &hints, &ai) != 0)
    return -1;

  int fd = socket(ai->ai_family, ai->ai_socktype, 0);
  if (fd < 0) {
    freeaddrinfo(ai);
    return -1;
  }
  struct timeval tv = {2, 0};
  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

  /* Header: "BJNP", dev type 1 (printer), cmd, error, seq, session, payload len. */
  unsigned char pkt[16] = {'B', 'J', 'N', 'P', 1, CMD_GET_STATUS, 0, 0, 0, 1};
  ssize_t n = -1;
  for (int attempt = 0; attempt < 3 && n < 16; attempt++) {
    sendto(fd, pkt, sizeof(pkt), 0, ai->ai_addr, ai->ai_addrlen);
    n = recv(fd, buf, len - 1, 0);
  }
  close(fd);
  freeaddrinfo(ai);
  if (n <= 16)
    return -1;
  buf[n] = '\0';
  memmove(buf, buf + 16, (size_t)n - 15); /* drop BJNP header */
  return 0;
}

/* Find "KEY=" inside the "CIR:...;" field; returns level or -1. */
static int ink_level(const char *cir, const char *code)
{
  size_t clen = strlen(code);
  for (const char *p = cir; p && *p && *p != ';'; p = strchr(p, ',')) {
    if (*p == ',')
      p++;
    if (!strncmp(p, code, clen) && p[clen] == '=')
      return atoi(p + clen + 1);
  }
  return -1;
}

/* "CTK:M,SET,/,GY,IO,..." - true if this tank is flagged IO (ink out). */
static int ink_out(const char *ctk, const char *code)
{
  char pat[16];
  snprintf(pat, sizeof(pat), "%s,IO", code);
  for (const char *p = ctk; p && *p && *p != ';'; p++)
    if ((p == ctk || p[-1] == ',' || p[-1] == ':') && !strncmp(p, pat, strlen(pat)))
      return 1;
  return 0;
}

int main(int argc, char **argv)
{
  int cups = argc > 1 && !strcmp(argv[1], "--cups");
  const char *arg = argc > 1 + cups ? argv[1 + cups] : NULL;
  char host[256], buf[4096];

  if (arg)
    snprintf(host, sizeof(host), "%s", arg);
  else if (host_from_uri(getenv("DEVICE_URI"), host, sizeof(host)) != 0) {
    fprintf(stderr, "usage: canon-ink [--cups] host\n");
    return 2;
  }

  if (bjnp_status(host, buf, sizeof(buf)) != 0) {
    fprintf(stderr, cups ? "DEBUG: canon-ink: no status from %s\n"
                         : "canon-ink: no status from %s\n", host);
    return 1;
  }

  const char *cir = strstr(buf, "CIR:");
  const char *ctk = strstr(buf, "CTK:");
  if (!cir) {
    fprintf(stderr, cups ? "DEBUG: canon-ink: no CIR field\n" : "canon-ink: no CIR field\n");
    return 1;
  }
  cir += 4;
  ctk = ctk ? ctk + 4 : NULL;

  int level[NINKS];
  for (size_t i = 0; i < NINKS; i++) {
    level[i] = ink_level(cir, inks[i].code);
    if (ctk && ink_out(ctk, inks[i].code))
      level[i] = 0;
  }

  if (cups) {
    fputs("ATTR: marker-names=", stderr);
    for (size_t i = 0; i < NINKS; i++)
      fprintf(stderr, "%s'%s'", i ? "," : "", inks[i].name);
    fputs("\nATTR: marker-colors=", stderr);
    for (size_t i = 0; i < NINKS; i++)
      fprintf(stderr, "%s%s", i ? "," : "", inks[i].color);
    fputs("\nATTR: marker-types=", stderr);
    for (size_t i = 0; i < NINKS; i++)
      fprintf(stderr, "%sink-cartridge", i ? "," : "");
    fputs("\nATTR: marker-low-levels=", stderr);
    for (size_t i = 0; i < NINKS; i++)
      fprintf(stderr, "%s15", i ? "," : "");
    fputs("\nATTR: marker-levels=", stderr);
    for (size_t i = 0; i < NINKS; i++)
      fprintf(stderr, "%s%d", i ? "," : "", level[i]);
    fputc('\n', stderr);
  } else {
    for (size_t i = 0; i < NINKS; i++) {
      if (level[i] < 0)
        printf("%-28s   ?\n", inks[i].name);
      else
        printf("%-28s %3d%% %s\n", inks[i].name, level[i], level[i] == 0 ? "EMPTY" : "");
    }
  }
  return 0;
}

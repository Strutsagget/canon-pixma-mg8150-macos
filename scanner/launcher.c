/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * MG8150 Scanner.app launcher.
 *
 * macOS only grants Local Network access to processes it can attribute to an
 * app; a bare python3 started by launchd gets "No route to host". This tiny
 * app binary is that app: it runs the eSCL bridge as a child process, so the
 * bridge (and scanimage under it) inherit the app's Local Network permission.
 */
#include <mach-o/dyld.h>
#include <libgen.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>

extern char **environ;
static pid_t child;

static void forward(int sig)
{
  if (child > 0)
    kill(child, sig);
}

int main(int argc, char **argv)
{
  char exe[4096], script[4096];
  uint32_t size = sizeof(exe);
  if (_NSGetExecutablePath(exe, &size) != 0)
    return 1;
  /* .../MG8150 Scanner.app/Contents/MacOS/launcher -> ../Resources/escl-bridge.py */
  snprintf(script, sizeof(script), "%s/../Resources/escl-bridge.py", dirname(exe));

  /* python3 -I escl-bridge.py [extra args from the LaunchAgent, e.g. --device] */
  char *args[16] = {"/opt/homebrew/bin/python3", "-I", script};
  int n = 3;
  for (int i = 1; i < argc && n < 15; i++)
    args[n++] = argv[i];
  args[n] = NULL;
  if (posix_spawn(&child, args[0], NULL, NULL, args, environ) != 0) {
    perror("posix_spawn");
    return 1;
  }
  signal(SIGTERM, forward);
  signal(SIGINT, forward);

  int status = 0;
  while (waitpid(child, &status, 0) < 0)
    ;
  return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

#!/usr/bin/env python3
"""Fully detach a command into its own session (macOS has no `setsid`). Double-fork + os.setsid() so the
child is a session leader with no controlling terminal and NOT in the caller's process group — survives
the caller shell exiting and the harness's background-job reaper.

Usage: detach.py <logfile> <cmd> [args...]
"""
import os, sys

log = sys.argv[1]; cmd = sys.argv[2:]
if os.fork() > 0: os._exit(0)          # parent returns immediately
os.setsid()                            # new session, drop controlling terminal
if os.fork() > 0: os._exit(0)          # ensure not a session leader that could reacquire a tty
fd_in = os.open(os.devnull, os.O_RDONLY)
fd_out = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
os.dup2(fd_in, 0); os.dup2(fd_out, 1); os.dup2(fd_out, 2)
os.execvp(cmd[0], cmd)

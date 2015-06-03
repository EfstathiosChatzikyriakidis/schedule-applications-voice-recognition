#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Daemon Executing Applications Via Serial Code Numbers.
#
#    Copyright (C) 2010 Efstathios Chatzikyriakidis <contact@efxa.org> 
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


# script's abnormal return error code.
ERROR_CODE = 2

# try to import the necessary modules.
try:
    import os
    import sys
    import time
    import serial
    import atexit
    import signal
    import subprocess
except ImportError:
    # print message and exit with abnormal error code.
    print "A module did not loaded."
    sys.exit(ERROR_CODE)


# objects imported when `from <module> import *' is used.
__all__ = ['main']


# daemon's process id temporary file.
PID_FILE = "/tmp/execute_apps_daemon.pid"

# serial line communication device file.
SERIAL_FILE = "/dev/ttyUSB0"

# serial line communication baud rate.
SERIAL_BAUD = 9600

# command line applications' names.
APPS = [ "dia",
         "gimp",
         "gthumb",
         "cheese",
         "gcalctool",
         "gedit",
         "file-roller",
         "vlc",
         "seahorse",
         "gnome-dictionary",
         "gucharmap",
         "rhythmbox",
         "soundconverter",
         "gnome-sound-recorder",
         "gnome-volume-control",
         "firefox",
         "pidgin",
         "evolution",
         "skype",
         "gftp",
         "gwget",
         "liferea",
         "transmission" ]


# a generic base daemon class.
class Daemon:
    # the following method is the class's constructor.
    def __init__(self, pidFile, stdin  = '/dev/null',
                                stdout = '/dev/null',
                                stderr = '/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidFile = pidFile

    # the following method daemonizes the program.
    def daemonize(self):
        # do the 'UNIX double-fork magic'.

        # do first fork.
        try:
            pid = os.fork()
            if pid > 0:
                # exit from first parent.
                sys.exit(0)
        except OSError, e:
            # print message and exit with abnormal error code.
            sys.stderr.write("FORK #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(ERROR_CODE)
       
        # decouple from parent environment.
        os.chdir("/")
        os.setsid()
        os.umask(0)
       
        # do second fork.
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent.
                sys.exit(0)
        except OSError, e:
            # print message and exit with abnormal error code.
            sys.stderr.write("FORK #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(ERROR_CODE)
       
        # redirect standard file descriptors.
        sys.stdout.flush()
        sys.stderr.flush()

        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)

        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # register a cleanup function.
        atexit.register(self.cleanup)

        # create the pidfile and write process id.
        pid = str(os.getpid())
        file(self.pidFile, 'w+').write("%s\n" % pid)

    # the following method cleans up the daemon.
    def cleanup(self):
        os.remove(self.pidFile)
 
    # the following method tries to start the daemon.
    def start(self):
        # try to get the pid from the pidfile.
        try:
            pf = file(self.pidFile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
       
        # if the daemon already runs.
        if pid:
            # print message and exit with abnormal error code.
            message = "PIDFILE '%s' already exists.\n"
            sys.stderr.write(message % self.pidFile)
            sys.exit(ERROR_CODE)

        # otherwise, start the daemon.
        self.daemonize()
        self.run()

    # the following method tries to stop the daemon.
    def stop(self):
        # try to get the pid from the pidfile.
        try:
            pf = file(self.pidFile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        # if the daemon does not run.
        if not pid:
            message = "PIDFILE '%s' does not exist.\n"
            sys.stderr.write(message % self.pidFile)
            return # not an error in a restart.
 
        # otherwise, try killing the daemon process.
        try:
            while True:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidFile):
                    os.remove(self.pidFile)
            else:
                # print message and exit with abnormal error code.
                print str(err)
                sys.exit(ERROR_CODE)
 
    # the following method tries to restart the daemon.
    def restart(self):
        self.stop()
        self.start()
 
    # the following method tries to run the daemon's job.
    def run(self):
        pass # needs overriding.


# execute applications' daemon class.
class ExecuteDaemon(Daemon):
    # the following method is the class's constructor.
    def __init__(self, pidFile, sFile, sBaud, apps):
        # initialize the base daemon class.
        Daemon.__init__(self, pidFile)

        self.sFile = sFile
        self.sBaud = sBaud
        self.sLine = None
        self.apps = apps

        # ignore automatically child termination signals.
        signal.signal(signal.SIGCLD, signal.SIG_IGN)

    # the following method tries to run the daemon's job.
    def run(self):
        # try to handle the serial device.
        while self.sLine is None:
            # try to establish serial line communication.
            try:
                self.sLine = serial.Serial(self.sFile, self.sBaud)
            except serial.SerialException:
                # print message and try again.
                sys.stderr.write("Cannot connect to serial device.\n")
                time.sleep(1)
                continue

        # flush of file like objects.
        self.sLine.flush()

        # looping executing applications.
        while True:
            # get a line from the serial.
            data = self.sLine.readline().strip()

            # if the line is not empty.
            if data != "":
                # try to handle the serial data.
                try:
                    # convert data to integer code number.
                    appIndex = int(data)

                    # if the code number is acceptable.
                    if appIndex >= 0 or appIndex < len(self.apps):
                        # execute the appropriate application.
                        subprocess.Popen([self.apps[appIndex]])
                except ValueError:
                    # print only error message.
                    sys.stderr.write ("Error application code number.\n")


# script's main function.
def main():
    # create execute applications' daemon.
    daemon = ExecuteDaemon(PID_FILE, SERIAL_FILE, SERIAL_BAUD, APPS)
    
    # if there are enough arguments from the shell.
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            # print message and exit with abnormal error code.
            print "Unknown Daemon Command."
            sys.exit(ERROR_CODE)
        
        # terminate with normal return code.
        sys.exit(0)
    else:
        # print message and exit with abnormal error code.
        print "USAGE: %s start|stop|restart" % sys.argv[0]
        sys.exit(ERROR_CODE)


# run the script if executed.
if __name__ == "__main__":
    main()

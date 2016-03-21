tmpr : temp file sharing
=========================

A very simple file sharing utility that launches quickly and allows sharing
files between many people with a set number of downloads (default 1, max 10).

In the basic form, simply run:

    python tmpr.py

and point your browser to http://127.0.0.1:3333.  From there, you can follow
the directions to upload and download files.  By default, it only runs on the
local interface. It is recommended that if you wish the serve to be available
remotely to run it behind a webserver such as nginx or apache with forwarding
set up between the two (so root privileges are not required).

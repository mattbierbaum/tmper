#!/usr/bin/env python
from __future__ import print_function

import os
import sys
import argparse

import tmpr.web
import tmpr.util

import pkg_resources
__version__ = pkg_resources.require("tmpr")[0].version

#=============================================================================
# command line parsing and main
#=============================================================================
class ShortFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)

            # if the Optional takes a value, format is:
            #    -s ARGS, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)
                for option_string in action.option_strings:
                    parts.append(option_string)

                return '%s %s' % (', '.join(parts), args_string)
            return ', '.join(parts)

    def _get_default_metavar_for_optional(self, action):
        return action.dest.upper()

    def _get_default_metavar_for_positional(self, action):
        return action.dest

    # also raw print the description text
    def _fill_text(self, text, width, indent):
        return ''.join([indent + line for line in text.splitlines(True)])

description = "Simple file sharing utility with download limits and password protection"
epilog = """
Example usage:
    # set the default url, upload a file, and download the file
    tmpr c --url=http://tmpr.meganet.com/
    tmpr u /path/to/file
    tmpr d yu

    # upload a file with a password
    tmpr upload --pass=34lkjsmdfn3i4usldf filename.txt

    # upload to a particular code
    tmpr upload -c 00 filename.txt
"""

def main():
    parser = argparse.ArgumentParser(
        description=description, epilog=epilog,
        formatter_class=ShortFormatter
    )
    sub = parser.add_subparsers()

    # shared arguments between upload and download
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("-u", "--url", type=str, default='',
        help="URL of tmpr service with which to interact")
    shared.add_argument("-p", "--pass", type=str, default='',
        help="password for uploaded file")

    # the sub actions that can be performed
    def _fmt(name):
        if sys.version_info[0] >= 3:
            return {'name': name, 'aliases': [name[0]]}
        return {'name': name[0]}
    kw = {'formatter_class': ShortFormatter}
    kw2 = dict(kw, parents=[shared])

    p_conf = sub.add_parser(help="configure defaults for tmpr", **dict(_fmt('conf'), **kw2))
    p_serve = sub.add_parser(help="run the tmpr webserver", **dict(_fmt('serve'), **kw))
    p_upload = sub.add_parser(help="upload a file to tmpr", **dict(_fmt('upload'), **kw2))
    p_download = sub.add_parser(help="download an uploaded file", **dict(_fmt('download'), **kw2))

    p_conf.set_defaults(action='conf')
    p_serve.set_defaults(action='serve')
    p_download.set_defaults(action='download')
    p_upload.set_defaults(action='upload')

    root = os.path.join(os.getcwd(), '.tmpr-files')

    # custom arguments for server action
    p_serve.add_argument("-a", "--addr", type=str, default='127.0.0.1',
        help="interface / address on which to run the service")
    p_serve.add_argument("-p", "--port", type=int, default=8888,
        help="port on which to run the server")
    p_serve.add_argument("-r", "--root", type=str, default=root,
        help="directory in which to store the uploaded files")

    # custom arguments for upload action
    p_upload.add_argument("-n", "--num", type=int, default=1,
        help="number of downloads available for this file")
    p_upload.add_argument("-t", "--time", type=str, default='',
        help="lifetime of the file (3 days, 1 min, etc)")
    p_upload.add_argument("-c", "--code", type=str,
        help="optional code for uploaded file")
    p_upload.add_argument("filename", type=str, help="name of file to upload")

    # custom arguments for download action
    p_download.add_argument(
        "-b", "--browser", dest='browser', action='store_true',
        help="open the file in a browser"
    )
    p_download.add_argument("code", type=str, help="code of download file")

    # version information
    parser.add_argument('-v', '--version', action='version', version='%(prog)s '+__version__)

    args = vars(parser.parse_args())
    action = args.get('action')

    if action == 'serve':
        tmpr.web.serve(
            root=args.get('root'), port=args.get('port'), addr=args.get('addr')
        )

    elif action == 'download':
        tmpr.util.download(
            args.get('url'), args.get('code'), 
            password=args.get('pass'), browser=args.get('browser')
        )

    elif action == 'upload':
        tmpr.util.upload(
            args.get('url'), args.get('filename'),
            code=args.get('code'), num=args.get('num'),
            password=args.get('pass'), time=args.get('time')
        )

    elif action == 'conf':
        tmpr.util.conf(
            url=args.get('url'), password=args.get('pass')
        )

    else:
        parser.print_help()

if __name__ == "__main__":
    main()

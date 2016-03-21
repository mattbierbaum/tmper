import os
import json
import string
import random

import tornado
import tornado.web
import tornado.ioloop
import tornado.options

# set the root directory for data, by default we should only be working in the
# current directory where this python file lives
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files')
CHARS = string.ascii_lowercase + ''.join(map(str, xrange(10)))

tornado.options.options.define("port", default=8888)
tornado.options.options.define("root", default=ROOT, help='directory for files')
tornado.options.options.define("addr", default="127.0.0.1", help="port to listen on")

FAVICON =  "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAABGdBTUEAALGPC/xhBQAAAGBQTFRFooKnN8jxY5PVM7vvM7zwY5LUN8fxo4KnhInAuX2Py3172oZtSZ/k5ZJjOa7s6pxbP9LyTNjy66VYVtryo4Vmqoxo57Fit5djvp1lw6Jnzaps17Fu3bNt47Rp6a1csZJmx8KbeAAAAEJJREFUOMtjEBGVl5cXl5CUkpaRlRWTkxPi5+Xm4mTgYOXhY2YTEBRmGNEK2EcVEKuAiRgFjFRXIEOqApZRBSQoAAAJHkuVEmG+EwAAAABJRU5ErkJggg=="

INDEX_CONTENT = \
"""
<link id="favicon" rel="shortcut icon" type="image/png"
 href="data:image/png;base64,{favicon}"
>

<html><head><title>tmpr : file share</title></head>
<div>
<center><pre style='font-size:48px;'>TMPR : FILE SHARING</pre></center>
<pre style='width:640px;margin:auto;'>
Usage : 
    GET         tmper/
    GET         tmper/[CODE]?args

    POST        tmper/
    POST        tmper/[CODE]?args
</pre>
<center>
<form action='/' method='post'>
<input type='file' name='file'><input type='submit'>
</form></center>
</html>
""".format(favicon=FAVICON)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/([a-z0-9]{2})?", MainHandler)]
        super(Application, self).__init__(handlers, gzip=True)

class MainHandler(tornado.web.RequestHandler):
    def generate_name(self):
        return ''.join([random.choice(CHARS) for i in xrange(2)])

    def unique_name(self):
        tries, out = 0, self.generate_name()
        while self.exists(out):
            if tries < len(CHARS)**2:
                raise Exception

            out = self.generate_name()
            tries += 1
        return out

    def path(self, n):
        return os.path.join(ROOT, n)

    def pathj(self, n):
        return os.path.join(ROOT, n+'.json')

    def save_file(self, name, content, meta):
        with open(self.path(name), 'w') as f:
            f.write(content)

        with open(self.pathj(name), 'w') as f:
            f.write(json.dumps(meta))

    def open_file(self, name):
        data = open(self.path(name)).read()
        meta = json.loads(open(self.pathj(name)).read())
        return data, meta

    def delete_file(self, name):
        os.remove(self.path(name))
        os.remove(self.pathj(name))

    def exists(self, name):
        return os.path.isfile(self.path(name))

    def get(self, args):
        if not args:
            self.write(INDEX_CONTENT)
        else:
            data, meta = self.open_file(args)
            meta['n'] -= 1

            if meta['n'] == 0:
                self.delete_file(args)
            else:
                self.save_file(args, data, meta)

            self.write(data)

    def post(self, args):
        meta = {}
        meta['key'] = self.request.arguments.get('key', [None])[0]
        meta['n'] = int(self.request.arguments.get('n', [1])[0])
        print meta, args

        if args and self.exists(args):
            # change to error occured since file already exists
            raise Exception

        if len(self.request.files) == 1:
            # we have files attached, save each of them to new file names
            name = args or self.unique_name()
            fobj = self.request.files.values()[0][0]

            print fobj
            meta.update({'filename': fobj['filename']})
            self.save_file(name, fobj['body'], meta)
            self.write(name)
        elif len(self.request.files) > 1:
            names = []

            for _, fobj in self.request.files.iteritems():
                name = self.unique_name()
    
                meta.update('filename', fobj['filename'])
                self.save_file(name, fobj['body'], meta)
                names.append(name)

            self.write(json.dumps(names))

if __name__ == "__main__":
    #web.ErrorHandler = webutil.ErrorHandler
    tornado.options.parse_command_line()

    ROOT = tornado.options.options.root
    if not os.path.exists(ROOT):
        os.mkdir(ROOT)

    app = Application()
    app.listen(tornado.options.options.port, tornado.options.options.addr)
    tornado.ioloop.IOLoop.instance().start()


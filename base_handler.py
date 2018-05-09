import os
import re

from tornado.options import define, options
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.log import app_log
from tornado.web import RequestHandler, HTTPError, RedirectHandler



class BaseHandler(RequestHandler):

    # REGEX to test the path specifies a user container
    user_path_regex = re.compile("^/?user/\w+")

    def is_user_path(self, path):
        return path is not None and BaseHandler.user_path_regex.match(path)

    def write_error(self, status_code, **kwargs): 
      self.set_status(status_code)
      self.write({'status': status_code})

    def prepare(self):
        if self.allow_origin:
            self.set_header("Access-Control-Allow-Origin", self.allow_origin)
        if self.expose_headers:
            self.set_header("Access-Control-Expose-Headers", self.expose_headers)
        if self.max_age:
            self.set_header("Access-Control-Max-Age", self.max_age)
        if self.allow_credentials:
            self.set_header("Access-Control-Allow-Credentials", self.allow_credentials)
        if self.allow_methods:
            self.set_header("Access-Control-Allow-Methods", self.allow_methods)
        if self.allow_headers:
            self.set_header("Access-Control-Allow-Headers", self.allow_headers)

    def get_current_user(self):
        if self.api_token is None:
            return 'authorized'
        # Confirm the client authorization token if an api token is configured
        client_token = self.request.headers.get('Authorization')
        if client_token == 'token %s' % self.api_token:
            return 'authorized'

    @property
    def allow_origin(self):
        return self.settings['allow_origin']

    @property
    def expose_headers(self):
        return self.settings['expose_headers']

    @property
    def max_age(self):
        return self.settings['max_age']

    @property
    def allow_credentials(self):
        return self.settings['allow_credentials']

    @property
    def allow_methods(self):
        return self.settings['allow_methods']

    @property
    def allow_headers(self):
        return self.settings['allow_headers']

    @property
    def api_token(self):
        return self.settings['api_token']

    def options(self):
        '''Respond to options requests'''
        self.set_status(204)
        self.finish()
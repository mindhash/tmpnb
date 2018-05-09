import datetime
import os
import re 
import uuid
import logging
import tornado
import tornado.options
from tornado.options import define, options
from tornado.httpserver import HTTPServer
from tornado.httputil import url_concat
from tornado.log import app_log
from tornado.web import RequestHandler, HTTPError, RedirectHandler

from tornado import gen, web

from base_handler import BaseHandler
from options import set_options
import my_dockworker
from my_spawnpool import SpawnPool

class SpawnHandler(BaseHandler):
  @gen.coroutine
  def get(self, path=None):
 
      try:
        container = self.pool.acquire()
        container_path = container.path
        app_log.info("Allocated [%s] from the pool.", container_path)

        if path is None:
          redirect_path = self.redirect_uri
        else:
          redirect_path = path.lstrip('/')

        url = "/{}/{}".format(container_path.strip('/'), redirect_path)
        
        app_log.info('url in spawn:', url)

        if container.token:
          url = url_concat(url, {'token': container.token})
        
        app_log.info("Redirecting [%s] -> [%s].", self.request.path, url)
        self.redirect(url, permanent=False)
      
      except my_spawnpool.EmptyPoolError:
        app_log.warning("The container pool is empty!")
        self.render("full.html", cull_period=self.cull_period)

  @property
  def pool(self):
      return self.settings['pool']

  @property
  def cull_period(self):
      return self.settings['cull_period']
  
  @property
  def redirect_uri(self):
      return self.settings['redirect_uri']

'''class APISpawnHandler(BaseHandler):

  @web.authenticated
  @gen.coroutine
  def get(self, path=None): 
    self.set_header("Content-Type", 'application/json')
    response = {'version': '0.2.0' }
    self.write(response)

  @property
  def pool(self):
    return self.settings['pool']
'''

class APISpawnHandler(BaseHandler):

    @web.authenticated
    @gen.coroutine
    def post(self):
        '''Spawns a brand new server programmatically'''
        try:
            container = self.pool.acquire()
            url = container.path
            if container.token:
                url = url_concat(url, {'token': container.token})
            app_log.info("Allocated [%s] from the pool.", url)
            app_log.debug("Responding with container url [%s].", url)
            self.write({'url': url})
        except spawnpool.EmptyPoolError:
            app_log.warning("The container pool is empty!")
            self.set_status(429)
            self.write({'status': 'full'})

    @property
    def pool(self):
        return self.settings['pool']


class LoadingHandler(BaseHandler):
    def get(self, path=None):
        self.render("loading.html", is_user_path=self.is_user_path(path))

def main():
  opts = set_options() 
  handlers = [ (r"/spawn/?", SpawnHandler),
  (r"/login?", SpawnHandler),
   (r"/api/spawn/?", APISpawnHandler)]

  api_token = os.getenv('API_AUTH_TOKEN')    
  proxy_token = os.environ['CONFIGPROXY_AUTH_TOKEN']
  proxy_endpoint = os.environ.get('CONFIGPROXY_ENDPOINT', "http://127.0.0.1:8001")
  docker_host = os.environ.get('DOCKER_HOST', 'unix://var/run/docker.sock')

  max_idle = datetime.timedelta(seconds=opts.cull_timeout)
  max_age = datetime.timedelta(seconds=opts.cull_max)
  pool_name = opts.pool_name
  
  if pool_name is None:
    pool_name = re.sub('[^a-zA-Z0_.-]+', '', opts.image.split(':')[0])


  container_config = my_dockworker.ContainerConfig(
    image=opts.image,
    command=opts.command,
    use_tokens=opts.use_tokens,
    mem_limit=opts.mem_limit,
    cpu_quota=opts.cpu_quota,
    cpu_shares=opts.cpu_shares,
    container_ip=opts.container_ip,
    container_port=opts.container_port,
    container_user=opts.container_user,
    host_network=opts.host_network,
    docker_network=opts.docker_network,
    host_directories=opts.host_directories,
    extra_hosts=opts.extra_hosts,
  )

  spawner = my_dockworker.DockerSpawner(docker_host,
    timeout=30,
    version=opts.docker_version,
    max_workers=opts.max_dock_workers,
    assert_hostname=opts.assert_hostname)
  
  static_path = os.path.join(os.path.dirname(__file__), "static")

  pool = SpawnPool(spawner=spawner,
   container_config=container_config,
   capacity=opts.pool_size,
   max_idle=max_idle,
   max_age=max_age,
   pool_name=pool_name,
   static_files=opts.static_files,
   static_dump_path=static_path,
   user_length=opts.user_length,
   proxy_endpoint=proxy_endpoint,
   proxy_token=proxy_token)

  ioloop = tornado.ioloop.IOLoop().current()


  settings = dict(
    default_handler_class=BaseHandler,
    static_path=static_path,
    cookie_secret=uuid.uuid4(),
    xsrf_cookies=False,
    debug=True,
    cull_period=opts.cull_period,
    allow_origin=None,
    expose_headers=None,
    max_age=None,
    allow_credentials=None,
    allow_methods=None,
    allow_headers=None,
    spawner=spawner,
    pool=pool,
    #autoescape=None,
    proxy_token=proxy_token,
    api_token=api_token,
    #template_path=os.path.join(os.path.dirname(__file__), 'templates'),
    proxy_endpoint=proxy_endpoint,
    redirect_uri=opts.redirect_uri.lstrip('/'),
    logging="debug")

  # Cleanup on a fresh state (likely a restart)
  ioloop.run_sync(pool.cleanout)

  ioloop.run_sync(pool.heartbeat)
  
  #if(opts.static_files):
  #  ioloop.run_sync(pool.copy_static)

  # Periodically execute a heartbeat function to cull used containers and regenerated failed
  # ones, self-healing the cluster.
  cull_ms = opts.cull_period * 1e3
  
  app_log.info("Culling containers unused for %i seconds every %i seconds.",
               opts.cull_timeout,
               opts.cull_period)
  culler = tornado.ioloop.PeriodicCallback(pool.heartbeat, cull_ms)
  culler.start()

  app_log.info("Listening on {}:{}".format(opts.ip or '*', opts.port))
  app_log.info('handlers %s', handlers)

  application = tornado.web.Application(handlers, **settings)
  http_server = HTTPServer(application, xheaders=True)
  http_server.listen(opts.port, opts.ip)
  ioloop.start()

if __name__ == "__main__":
  main()

  #post_data = { 'data': 'test data' } #A dictionary of your post data 
  #body = urllib.urlencode(post_data)  
  #http_client.fetch("http://0.0.0.0:9999/api/spawn/34", handle_request, method='POST', headers=None, body=body) #Send it off!

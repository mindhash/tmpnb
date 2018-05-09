import binascii
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import os

import docker
import requests
import logging
from docker.utils import kwargs_from_env 



from tornado import gen
from tornado.log import app_log


ContainerConfig = namedtuple('ContainerConfig', [
    'image', 'command', 'mem_limit', 'cpu_quota', 'cpu_shares', 'container_ip',
    'container_port', 'container_user', 'host_network', 'host_directories',
    'extra_hosts', 'docker_network', 'use_tokens',
])


RETRIES = 1

class AsyncDockerClient():
    '''Completely ridiculous wrapper for a Docker client that returns futures
    on every single docker method called on it, configured with an executor.
    If no executor is passed, it defaults ThreadPoolExecutor(max_workers=2).
    '''
    def __init__(self, docker_client, executor=None):
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1)
        self._docker_client = docker_client
        self.executor = executor

    def __getattr__(self, name):
        '''Creates a function, based on docker_client.name that returns a
        Future. If name is not a callable, returns the attribute directly.
        '''
        fn = getattr(self._docker_client, name)

        # Make sure it really is a function first
        if not callable(fn):
            return fn

        def method(*args, **kwargs):
            return self.executor.submit(fn, *args, **kwargs)

        return method


class DockerSpawner():
  def __init__(self,
               docker_host='unix://var/run/docker.sock',
               version='auto',
               timeout=30,
               max_workers=64,
               assert_hostname=False,
               ):

    #kwargs = kwargs_from_env(assert_hostname=False)
    kwargs = kwargs_from_env(assert_hostname=assert_hostname)

    # environment variable DOCKER_HOST takes precedence
    kwargs.setdefault('base_url', docker_host)

    blocking_docker_client = docker.APIClient(version=version,
                                           timeout=timeout,
                                           **kwargs)

    executor = ThreadPoolExecutor(max_workers=max_workers)

    async_docker_client = AsyncDockerClient(blocking_docker_client,
                                            executor)
    self.docker_client = async_docker_client

    self.port = 0

  @gen.coroutine
  def create_notebook_server(self, base_path, container_name, container_config):  
    
    if self.port == 0:
      self.port = 800
    
    port = self.port
    self.port += 1

    port_bindings={container_config.container_port: (container_config.container_ip, port)} 

    host_config = dict( 
            network_mode='bridge',
            port_bindings=port_bindings ) 
        
    host_config = docker.APIClient.create_host_config(self.docker_client,
                                                       **host_config)

    #
    if container_config.use_tokens:
            # Generate token for authenticating first request (requires notebook 4.3)
            # making each server semi-private for the user who is first assigned.
            token = binascii.hexlify(os.urandom(24)).decode('ascii')
    else:
        token = ''


    rendered_command = container_config.command.format(base_path=base_path, port=container_config.container_port, # 8888
        ip=container_config.container_ip, token=token)
    
    app_log.info('rendered_command', rendered_command)

    command = [
            "/bin/sh",
            "-c",
            rendered_command
        ]

    resp = yield self._with_retries(self.docker_client.create_container,
      image=container_config.image,
      user=container_config.container_user,
      command=command,   
      host_config=host_config,
      #networking_config={'EndpointsConfig': {'picaso1': {}}}, 
      name=container_name)

    docker_warnings = resp.get('Warnings')
    if docker_warnings is not None:
      app_log.warning(docker_warnings)

    container_id = resp['Id']
    app_log.info("Created container {}".format(container_id))

    print('container_config', container_config) 
    print("Created container {}".format(container_id))
    
    app_log.info('starting container')
             
    yield self._with_retries(self.docker_client.start,
                             container_id)

    raise gen.Return((container_id, container_config.container_ip, int(port), token))

  @gen.coroutine
  def shutdown_notebook_server(self, container_id, alive=True):
      '''Gracefully stop a running container.'''

      if alive:
          yield self._with_retries(self.docker_client.stop, container_id)
      yield self._with_retries(self.docker_client.remove_container, container_id)

  @gen.coroutine
  def list_notebook_servers(self, pool_regex, all=True):
      '''List containers that are managed by a specific pool.'''

      existing = yield self._with_retries(self.docker_client.containers,
                                          all=all,
                                          trunc=False)

      def name_matches(container):
          try:
              names = container['Names']
              if names is None:
                app_log.warn("Docker API returned null Names, ignoring")
                return False
          except Exception:
              app_log.warn("Invalid container: %r", container)
              return False
          for name in names:
              #app_log.info('name %s', name)
              if pool_regex.search(name):
                  return True
          return False

      matching = [container for container in existing if name_matches(container)]
      #app_log.info('matching %s', matching)
      raise gen.Return(matching)
 
  @gen.coroutine
  def _with_retries(self, fn, *args, **kwargs):
      '''Attempt a Docker API call.

      If an error occurs, retry up to "max_tries" times before letting the exception propagate
      up the stack.''' 
      max_tries = kwargs.get('max_tries', RETRIES)
      try:
          if 'max_tries' in kwargs:
              del kwargs['max_tries']
          result = yield fn(*args, **kwargs)
          raise gen.Return(result)
      except (docker.errors.APIError, requests.exceptions.RequestException) as e:
          app_log.error("Encountered a Docker error with {} ({} retries remain): {}".format(fn.__name__, max_tries, e))
          if max_tries > 0:
              kwargs['max_tries'] = max_tries - 1
              result = yield self._with_retries(fn, *args, **kwargs)
              raise gen.Return(result)
          else:
              raise e

  @gen.coroutine
  def copy_files(self, container_id, path):
      '''Returns a tarball of path from container_id'''
      tarball = yield self.docker_client.copy(container_id, path)
      raise gen.Return(tarball)  

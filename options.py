
import tornado.options
from textwrap import dedent
from tornado.options import define, options

def set_options():
    tornado.options.define('cull_period', default=300, # 
        help="Interval (s) for culling idle containers."
    )
    tornado.options.define('cull_timeout', default=600,  # 3600
        help="Timeout (s) for culling idle containers."
    )
    tornado.options.define('cull_max', default=14400,
        help=dedent("""
        Maximum age of a container (s), regardless of activity.

        Default: 14400 (4 hours)

        A container that has been running for this long will be culled,
        even if it is not idle.
        """)
    )
    tornado.options.define('container_ip', default='0.0.0.0',
        help="""Host IP address for containers to bind to. If host_network=True,
the host IP address for notebook servers to bind to."""
    )
    tornado.options.define('container_port', default='8888',
        help="""Within container port for notebook servers to bind to.
If host_network=True, the starting port assigned to notebook servers on the host."""
    )
    tornado.options.define('use_tokens', default=False,
        help="""Enable token-authentication of notebook servers."""
    )

    command_default = (
        'jupyter kernelgateway '
        ' --KernelGatewayApp.port={port} '
        ' --KernelGatewayApp.ip={ip} '
        ' --KernelGatewayApp.allow_origin=* '
        ' --KernelGatewayApp.base_url={base_path} '
        ' --KernelGatewayApp.port_retries=0 '
        # ' --KernelGatewayApp.token="{token}" '

#        '--KernelGatewayApp.answer_yes=True'
#        ' --NotebookApp.port_retries=0'
#        ' --NotebookApp.token="{token}"'
    )

    tornado.options.define('command', default=command_default,
        help="""Command to run when booting the image. A placeholder for
{base_path} should be provided. A placeholder for {port} and {ip} can be provided."""
    )
    tornado.options.define('port', default=9999,
        help="port for the main server to listen on"
    )
    tornado.options.define('ip', default=None,
        help="ip for the main server to listen on [default: all interfaces]"
    )
    tornado.options.define('admin_port', default=10000,
        help="port for the admin server to listen on"
    )
    tornado.options.define('admin_ip', default='127.0.0.1',
        help="ip for the admin server to listen on [default: 127.0.0.1]"
    )
    tornado.options.define('max_dock_workers', default=2,
        help="Maximum number of docker workers"
    )
    tornado.options.define('mem_limit', default="512m",
        help="Limit on Memory, per container"
    )
    tornado.options.define('cpu_shares', default=None, type=int,
        help="Limit CPU shares, per container"
    )
    tornado.options.define('cpu_quota', default=None, type=int,
        help=dedent("""
        Limit CPU quota, per container.

        Units are CPU-µs per 100ms, so 1 CPU/container would be:

            --cpu-quota=100000

        """)
    )
    tornado.options.define('image', default="jupyter/kernel-gateway",
        help="Docker container to spawn for new users. Must be on the system already"
    )
    tornado.options.define('docker_version', default="auto",
        help="Version of the Docker API to use"
    )
    tornado.options.define('redirect_uri', default="/tree",
        help="URI to redirect users to upon initial notebook launch"
    )
    tornado.options.define('pool_size', default=2,
        help="Capacity for containers on this system. Will be prelaunched at startup."
    )
    tornado.options.define('pool_name', default=None,
        help="Container name fragment used to identity containers that belong to this instance."
    )
    tornado.options.define('static_files', default=None,
        help="Static files to extract from the initial container launch"
    )
    tornado.options.define('allow_origin', default=None,
        help="Set the Access-Control-Allow-Origin header. Use '*' to allow any origin to access."
    )
    tornado.options.define('expose_headers', default=None,
            help="Sets the Access-Control-Expose-Headers header."
    )
    tornado.options.define('max_age', default=None,
        help="Sets the Access-Control-Max-Age header."
    )
    tornado.options.define('allow_credentials', default=None,
        help="Sets the Access-Control-Allow-Credentials header."
    )
    tornado.options.define('allow_methods', default=None,
        help="Sets the Access-Control-Allow-Methods header."
    )
    tornado.options.define('allow_headers', default=None,
        help="Sets the Access-Control-Allow-Headers header."
    )
    tornado.options.define('assert_hostname', default=False,
        help="Verify hostname of Docker daemon."
    )
    tornado.options.define('container_user', default=None,
        help="User to run container command as"
    )
    tornado.options.define('host_network', default=False,
        help="""Attaches the containers to the host networking instead of the
default docker bridge. Affects the semantics of container_port and container_ip."""
    )
    tornado.options.define('docker_network', default=None,
        help="""Attaches the containers to the specified docker network.
        For use when the proxy, tmpnb, and containers are all in docker."""
    )
    tornado.options.define('host_directories', default=None,
        help=dedent("""
        Mount the specified directory as a data volume in a specified location
        (provide an empty value to use a default mount path), multiple
        directories can be specified by using a comma-delimited string, directory
        path must provided in full (eg: /home/steve/data/:/usr/data/:ro), permissions default to
        rw"""))
    tornado.options.define('user_length', default=12,
        help="Length of the unique /user/:id path generated per container"
    )
    tornado.options.define('extra_hosts', default=[], multiple=True,
        help=dedent("""
        Extra hosts for the containers, multiple hosts can be specified
        by using a comma-delimited string, specified in the form hostname:IP"""))

    tornado.options.parse_command_line()
    opts = tornado.options.options
    return opts

# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-20 18:25:56
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/ddns_service_adapters.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-22 10:06:54
#
# **********************************************************

'''
This module is an abstraciton for the variety of 
DDNS services on the market. The main function is to
provide URLs that are appropriate for updating a
specific service with a new IP. 

At the core is a .ini config file with a separate
section for each service. Subclasses of the parent
DDNSServiceAdapter class provide a ddns_update_url()
method that uses the respective section's option values
to construct the service update URL.

The parent class provides information about available
adapters (subclasses and sections in the .ini file). It
is also the factory for the adapters---the instances of
subclasses. To obtain an instance on which clients then
call ddns_update_url(), use get_service_adapter(service_name)
on an instance of the parent.

Usage:
    ddns_service_fact = DDNSSerivceAdapter(<config-file-path>)
    ddns_adapter = ddns_service_fact(<service-name>)

    ... detect new IP for host.domain ...
    update_url = ddns_adapter.ddns_update_url(<new-ip>)
    ... send update_url to service ...
    
'''

import configparser
import os
from pathlib import Path
from typing import Type

class DDNSServiceAdapter:

    DEFAULT_CONFIG_FILE = Path(__file__).parent / 'ddns.ini'
    _ADAPTER_REGISTRY   = {}

    #------------------------------------
    # Constructor
    #-------------------    

    def __init__(self, config_file=None):

        if config_file is None:
            config_file = DDNSServiceAdapter.DEFAULT_CONFIG_FILE

        self.config_file = config_file

        # All subclasses (DDNS service implementations share the config)
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        if len(self.config.sections()) == 0:
            # When file is not found, the read()
            # returns an empty config. We don't 
            # know which other conditions might do
            # that. Try to explain at least the
            # obvious: a bad path:
            if not os.path.exists(config_file):
                msg = f"Config file {config_file} does not exist"
                raise FileNotFoundError(msg)
            else:
                msg = f"Config file {config_file} seems empty; if it is not, syntax problems?"
                raise TypeError(msg)

    #------------------------------------
    # __init_subclass__
    #-------------------

    def __init_subclass__(cls, **kwargs):
        '''
        This a 'magic-method'; it is called by Python whenever
        a subclass of this class (DDNSServiceAdapter) is defined.
        We get the subclass name, and associate it with the subclass
        object
        '''
        super().__init_subclass__(**kwargs)
        # Automatically register new DDNS service adapter
        # class: service-name --> subclass-object:
        DDNSServiceAdapter._ADAPTER_REGISTRY[cls.__name__.lower()] = cls

    #------------------------------------
    # get_service_adapter
    #-------------------

    def get_service_adapter(self, service_name: str) -> 'Type[DDNSServiceAdapter]':
        '''
        Returns an object that understands the DDNS service 
        of the given name. That object is guaranteed to have
        at least method ddns_update_url(), but maybe others,
        depending on the service.

        The quotes around the return type hint is required 
        to avoid a 'that class is not yet defined' forward 
        reference error.

        :param service_name: name of DDNS service as defined in config file secion
        :type service_name: str
        :raises NotImplementedError: if service has no entry in config file
        :raises NotImplementedError: if no subclass for the service exists
        :return: an instance of the subclass appropriate for the service
        :rtype: Type[DDNSServiceAdapter]
        '''

        # Do we have init info for this service?
        if not self.config.has_section(service_name):
            msg = f"Service '{service_name}' has no entry in config file {self.config_file}"
            raise NotImplementedError(msg)
        
        try:
            adapter_cls_obj = DDNSServiceAdapter._ADAPTER_REGISTRY[service_name]
            adapter_obj = adapter_cls_obj.__new__(adapter_cls_obj)
            adapter_obj.config = self.config
            return adapter_obj
        except KeyError:
            raise NotImplementedError(f"Service '{service_name}' is not implemented")

    #------------------------------------
    # ddns_update_url
    #-------------------

    def ddns_update_url(self, new_ip: str):
        '''
        Illegal to call this method on the parent class directly.
        Must call on a subclass.

        :param new_ip: new IP to report to DDNS service
        :type new_ip: str
        :raises NotImplementedError: info that parent is inappropriate for this method
        '''
        raise NotImplementedError("The ddns_update_url() method must be called on a subclass")

    #------------------------------------
    # _retrieve_secret
    #-------------------

    def _retrieve_secret(self, service_name):
        '''
        Given a DDNS service name, return its secret
        by reading it from the file specified in the 
        servive's entry in the config file.

        :param service_name: name of service; any upper/lower casing OK
        :type service_name: str
        :raises KeyError: if config file does not provide a 
            'secrets-file' option for the service
        :return: the secret
        :rtype: str
        '''

        # In the config file the sections are all
        # lower case:
        adapter_section = service_name.lower()
        if not self.config.has_option(adapter_section, 'secrets_file'):
            msg = f"No 'secrets_file' entry in section {adapter_section} of config file {self.config_file}"
            raise KeyError(msg)
        secret_path = self.config[adapter_section]['secrets_file']
        # Resolve tilde and env vars:
        secret_path = self.expand_path(secret_path)
        secret: str = ''
        try:
            with open(secret_path, 'r') as fd:
                secret = fd.read().strip()
        except Exception as e:
            raise FileNotFoundError(f"Could not open secrets file '{secret_path}'")
        return secret
    
    #------------------------------------
    # expand_path
    #-------------------    

    def expand_path(self, path: str) -> str:
        '''
        Given a path that might involve tilde and/or 
        env vars, return an absolute path

        :param path: path to resolve
        :type path: str
        :return: path with tilde and/or env vars resolved
        :rtype: str
        '''
        env_vars_resolved = os.path.expandvars(path)
        resolved_path = Path(env_vars_resolved).expanduser()
        return str(resolved_path)

# ----------- Class Namecheap -----------

class NameCheap(DDNSServiceAdapter):
    '''Implements interactions with NameCheap DDNS'''

    #------------------------------------
    # __init__
    #-------------------

    def __init__(self):
        msg = ("DDNS adapter classes must be instantiated via "
               "DDNSServiceAdapter().get_service_adapter(<service-nm>)")
        raise TypeError(msg)

	#------------------------------------
	# ddns_update_url
	#-------------------

    def ddns_update_url(self, new_ip: str) -> str:
        '''
		Build a URL that will update the DDNS record for
		a host/domain with a new IP on NameCheap. The format 
        of this URL the following URL is required:

			url:
				'https://dynamicdns.park-your-domain.com/update?'
				host=<host>&
				domain=<domain>&
				password=<password>&
				ip=<new-ip>

        We obtain the host and domain from the .ini file, i.e.
        from the parent's self.config

        :param new_ip: the new IP for host.domain
        :type new_ip: str
        :raises KeyError: if no 'url_root' option in namecheap section of config
        :raises KeyError: if no 'host' option in namecheap section of config
        :raises KeyError: if no 'domain' option in namecheap section of config
        :raises KeyError: if no 'secrets_file' option in namecheap section of config
        :raises FileNotFoundError: if secrets file not found or inaccessible
        :return: a URL to access for the IP update
        :rtype: str
        '''

        # By convention, adapter class names are the DDNS
        # service name capitalized:
        # service_name = self.__class__.__name__.lower()
        service_name = 'namecheap'
        try:
            url_base = self.config[service_name]['url_root']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'url_root'")
        
        try:
            host = self.config[service_name]['host']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'host'")

        try:
            domain = self.config[service_name]['domain']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'domain'")

        url =  (url_base +
               f"host={host}&" +
               f"domain={domain}&" +
               f"password={self._retrieve_secret(service_name)}&" +
               f"ip={new_ip}")
        return url
